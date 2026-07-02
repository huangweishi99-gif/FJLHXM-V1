from __future__ import annotations

import csv
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT_DIR = ROOT / "data" / "overseas_1d"
TIMEFRAME_CONFIG = {
    "D1": {
        "bar": "1D",
        "days": 1825,
        "max_batches": 20,
        "min_rows": 30,
        "out_dir": ROOT / "data" / "overseas_1d",
        "source": "okx_history_candles_1D",
        "date_only": True,
    },
    "H1": {
        "bar": "1H",
        "days": 365,
        "max_batches": 40,
        "min_rows": 48,
        "out_dir": ROOT / "data" / "1h",
        "source": "okx_history_candles_1H",
        "date_only": False,
    },
    "M15": {
        "bar": "15m",
        "days": 90,
        "max_batches": 40,
        "min_rows": 96,
        "out_dir": ROOT / "data" / "15m",
        "source": "okx_history_candles_15m",
        "date_only": False,
    },
}
TIMEFRAME_ALIASES = {
    "1D": "D1",
    "D": "D1",
    "D1": "D1",
    "DAILY": "D1",
    "1H": "H1",
    "H": "H1",
    "H1": "H1",
    "60M": "H1",
    "15M": "M15",
    "M15": "M15",
}

# OKX bar -> max allowed lag (seconds) between last closed bar open time and UTC now.
BAR_MAX_LAG_SECONDS = {
    "15m": 3600,
    "1H": 7200,
    "1D": 172800,
}


def utc_now() -> datetime:
    """Timezone-aware UTC now. Never strip tzinfo before .timestamp() on CST hosts."""
    return datetime.now(timezone.utc)


def utc_now_ms() -> int:
    return int(utc_now().timestamp() * 1000)


def okx_after_cursor_ms(*, end: datetime | None = None) -> str:
    """OKX history-candles `after` cursor (epoch ms, UTC)."""
    when = end if end is not None else utc_now()
    if when.tzinfo is None:
        raise ValueError("okx_after_cursor_ms requires timezone-aware UTC datetime")
    return str(int(when.timestamp() * 1000))


def validate_okx_freshness(rows: list[dict], *, bar: str) -> None:
    """Fail fast if the newest bar is too old (catches cursor/timezone regressions)."""
    if not rows:
        raise ValueError("empty OKX rows")
    max_lag = BAR_MAX_LAG_SECONDS.get(bar)
    if max_lag is None:
        return
    last_ts = str(rows[-1]["timestamp"])
    if len(last_ts) <= 10:
        last_dt = datetime.strptime(last_ts, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    else:
        last_dt = datetime.strptime(last_ts, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
    lag = utc_now().timestamp() - last_dt.timestamp()
    if lag > max_lag:
        raise ValueError(
            f"OKX {bar} data stale: last={last_ts} lag_sec={int(lag)} max={max_lag}"
        )


def okx_inst_id(symbol: str) -> str:
    sym = symbol.strip().upper().replace("-", "").replace("/", "")
    if not sym.endswith("USDT"):
        sym = f"{sym}USDT"
    base = sym[:-4]
    return f"{base}-USDT"


def _atomic_write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        raise ValueError("refuse to save empty crypto frame")
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    with tmp_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["timestamp", "open", "high", "low", "close", "volume"])
        writer.writeheader()
        writer.writerows(rows)
    os.replace(tmp_path, path)


def normalize_timeframe(timeframe: str) -> str:
    key = timeframe.strip().upper()
    if key not in TIMEFRAME_ALIASES:
        raise ValueError(f"unsupported crypto timeframe: {timeframe}")
    return TIMEFRAME_ALIASES[key]


def fetch_okx_candle_rows(
    inst_id: str,
    *,
    bar: str,
    days: int,
    max_batches: int,
    min_rows: int,
    date_only: bool,
) -> list[dict]:
    """Fetch OKX candles and return chart-bundle-compatible rows."""
    end = utc_now()
    start_ts = end.timestamp() - days * 86400
    cursor = okx_after_cursor_ms(end=end)
    raw_rows: list[list[str]] = []
    url = "https://www.okx.com/api/v5/market/history-candles"

    for _ in range(max_batches):
        params = {"instId": inst_id, "bar": bar, "limit": "300", "after": cursor}
        payload = None
        last_exc: Exception | None = None
        for attempt in range(4):
            try:
                request = Request(f"{url}?{urlencode(params)}", headers={"User-Agent": "Mozilla/5.0"})
                with urlopen(request, timeout=30) as response:
                    payload = json.loads(response.read().decode("utf-8"))
                last_exc = None
                break
            except Exception as exc:  # noqa: BLE001 - caller records user-visible ingest failure
                last_exc = exc
                time.sleep(0.8 * (attempt + 1))
        if last_exc is not None:
            raise last_exc
        if not payload or payload.get("code") != "0":
            raise ValueError(f"OKX error for {inst_id}: {payload}")
        batch = payload.get("data") or []
        if not batch:
            break
        raw_rows.extend(batch)
        oldest_ms = int(batch[-1][0])
        cursor = str(oldest_ms)
        if oldest_ms / 1000 <= start_ts or len(batch) < 300:
            break
        time.sleep(0.08)

    rows_by_timestamp: dict[str, dict] = {}
    for item in raw_rows:
        ts_ms = int(item[0])
        if ts_ms / 1000 < start_ts:
            continue
        dt_obj = datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc)
        dt = dt_obj.strftime("%Y-%m-%d") if date_only else dt_obj.strftime("%Y-%m-%d %H:%M:%S")
        row = {
            "timestamp": dt,
            "open": float(item[1]),
            "high": float(item[2]),
            "low": float(item[3]),
            "close": float(item[4]),
            "volume": float(item[5]),
        }
        if row["high"] < max(row["open"], row["close"]) or row["low"] > min(row["open"], row["close"]):
            raise ValueError(f"invalid OHLC row for {inst_id} {dt}")
        rows_by_timestamp[dt] = row
    rows = [rows_by_timestamp[k] for k in sorted(rows_by_timestamp)]
    if len(rows) < min_rows:
        raise ValueError(f"too few OKX {bar} rows for {inst_id}: {len(rows)}")
    return rows


def fetch_okx_daily_rows(inst_id: str, *, days: int = 1825, max_batches: int = 20) -> list[dict]:
    """Fetch daily OKX candles and return chart-bundle-compatible rows."""
    return fetch_okx_candle_rows(
        inst_id,
        bar="1D",
        days=days,
        max_batches=max_batches,
        min_rows=30,
        date_only=True,
    )


def ingest_crypto_timeframe_csv(
    symbol: str,
    *,
    timeframe: str,
    days: int | None = None,
    out_dir: Path | None = None,
    max_batches: int | None = None,
) -> dict:
    inst_id = okx_inst_id(symbol)
    local_symbol = inst_id.replace("-", "")
    tf = normalize_timeframe(timeframe)
    cfg = TIMEFRAME_CONFIG[tf]
    rows = fetch_okx_candle_rows(
        inst_id,
        bar=str(cfg["bar"]),
        days=int(days or cfg["days"]),
        max_batches=int(max_batches or cfg["max_batches"]),
        min_rows=int(cfg["min_rows"]),
        date_only=bool(cfg["date_only"]),
    )
    validate_okx_freshness(rows, bar=str(cfg["bar"]))
    target_dir = out_dir or cfg["out_dir"]
    out_path = target_dir / f"{local_symbol}.csv"
    _atomic_write_csv(out_path, rows)
    return {
        "symbol": local_symbol,
        "inst_id": inst_id,
        "timeframe": tf,
        "bar": cfg["bar"],
        "rows": len(rows),
        "start": rows[0]["timestamp"],
        "end": rows[-1]["timestamp"],
        "source": cfg["source"],
        "path": str(out_path),
    }


def ingest_crypto_timeframes(symbol: str, *, timeframes: list[str] | None = None) -> dict:
    requested = timeframes or ["D1", "H1", "M15"]
    metas = {}
    for item in requested:
        meta = ingest_crypto_timeframe_csv(symbol, timeframe=item)
        metas[meta["timeframe"]] = meta
    return {
        "symbol": okx_inst_id(symbol).replace("-", ""),
        "inst_id": okx_inst_id(symbol),
        "timeframes": metas,
    }


def crypto_timeframe_csv_path(symbol: str, timeframe: str) -> Path:
    inst_id = okx_inst_id(symbol)
    local_symbol = inst_id.replace("-", "")
    tf = normalize_timeframe(timeframe)
    return TIMEFRAME_CONFIG[tf]["out_dir"] / f"{local_symbol}.csv"


def missing_crypto_timeframes(symbol: str, *, timeframes: list[str] | None = None) -> list[str]:
    requested = timeframes or ["D1", "H1", "M15"]
    missing = []
    for item in requested:
        tf = normalize_timeframe(item)
        if not crypto_timeframe_csv_path(symbol, tf).exists():
            missing.append(tf)
    return missing


def ingest_crypto_daily_csv(symbol: str, *, days: int = 1825, out_dir: Path = DEFAULT_OUT_DIR) -> dict:
    return ingest_crypto_timeframe_csv(symbol, timeframe="D1", days=days, out_dir=out_dir)
