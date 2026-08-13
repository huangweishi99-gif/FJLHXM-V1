#!/usr/bin/env python3
"""补拉 crypto 缺失 15m：优先 Binance，无现货交易对时回退 OKX。"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "services"))

from crypto_ingest import ingest_crypto_timeframe_csv  # noqa: E402

# Binance 无现货源或 1d/1h 增量为空，改走 OKX 的品种（与 data_manager 跳过列表对齐）
OKX_ONLY_SYMBOLS = {"HYPEUSDT", "ATHUSDT"}
OKX_15M_SYMBOLS = OKX_ONLY_SYMBOLS
MANIFEST_PATH = ROOT / "data" / "15m" / "_okx_15m_manifest.json"

TIMEFRAME_SPEC = {
    "M15": {"folder": "15m", "ingest": "M15", "default_days": 90, "os_tail": 960, "hbb": False},
    "D1": {"folder": "1d", "ingest": "D1", "default_days": 1825, "os_tail": 1095, "hbb": True},
    "H1": {"folder": "1h", "ingest": "H1", "default_days": 365, "os_tail": 2400, "hbb": False},
}


def _normalize_symbol(symbol: str) -> str:
    text = symbol.strip().upper().replace("-", "").replace("_", "")
    return text if text.endswith("USDT") else f"{text}USDT"


def sync_binance_15m(symbol: str, *, base_dir: Path) -> dict:
    from binance.client import Client
    from data_manager import atomic_save_csv, read_existing_klines

    file_path = base_dir / "15m" / f"{symbol}.csv"
    file_path.parent.mkdir(parents=True, exist_ok=True)
    existing = read_existing_klines(str(file_path))
    start_str = str(int(existing.index[-1].timestamp() * 1000)) if existing is not None else "5 years ago UTC"
    client = Client()
    klines = client.get_historical_klines(symbol, Client.KLINE_INTERVAL_15MINUTE, start_str)
    if not klines:
        return {"symbol": symbol, "source": "binance", "status": "noop", "rows": len(existing) if existing is not None else 0}
    cols = [
        "timestamp", "open", "high", "low", "close", "volume",
        "close_time", "quote_av", "trades", "tb_base_av", "tb_quote_av", "ignore",
    ]
    frame = pd.DataFrame(klines, columns=cols)
    frame["timestamp"] = pd.to_datetime(frame["timestamp"], unit="ms")
    frame.set_index("timestamp", inplace=True)
    numeric = ["open", "high", "low", "close", "volume"]
    frame[numeric] = frame[numeric].astype(float)
    frame = frame[numeric]
    if existing is not None:
        combined = pd.concat([existing, frame])
        combined = combined[~combined.index.duplicated(keep="last")]
    else:
        combined = frame
    atomic_save_csv(combined, str(file_path))
    time.sleep(0.5)
    return {
        "symbol": symbol,
        "source": "binance",
        "status": "ok",
        "rows": len(combined),
        "path": str(file_path),
    }


def sync_okx_timeframe(symbol: str, *, timeframe: str, root: Path, days: int | None = None) -> dict:
    tf = timeframe.strip().upper()
    if tf not in TIMEFRAME_SPEC:
        raise ValueError(f"unsupported timeframe: {timeframe}")
    spec = TIMEFRAME_SPEC[tf]
    out_dir = root / "data" / spec["folder"]
    meta = ingest_crypto_timeframe_csv(
        symbol,
        timeframe=str(spec["ingest"]),
        days=int(days or spec["default_days"]),
        out_dir=out_dir,
    )
    return {
        "symbol": meta["symbol"],
        "timeframe": tf,
        "source": "okx",
        "status": "ok",
        "rows": meta["rows"],
        "start": meta["start"],
        "end": meta["end"],
        "inst_id": meta["inst_id"],
        "path": meta["path"],
    }


def sync_okx_15m(symbol: str, *, days: int | None = None, root: Path | None = None) -> dict:
    return sync_okx_timeframe(symbol, timeframe="M15", root=root or ROOT, days=days)


def sync_symbol_15m(symbol: str, *, base_dir: Path, force_okx: bool = False, days: int | None = None, root: Path | None = None) -> dict:
    symbol = _normalize_symbol(symbol)
    if force_okx or symbol in OKX_ONLY_SYMBOLS:
        return sync_okx_15m(symbol, days=days, root=root)
    try:
        return sync_binance_15m(symbol, base_dir=base_dir)
    except Exception as exc:
        name = type(exc).__name__
        code = getattr(exc, "code", None)
        if name == "BinanceAPIException" and code == -1121:
            return sync_okx_15m(symbol, days=days)
        if "Invalid symbol" in str(exc):
            return sync_okx_15m(symbol, days=days)
        raise


def update_manifest(results: list[dict]) -> None:
    payload: dict = {}
    if MANIFEST_PATH.exists():
        try:
            payload = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        except Exception:
            payload = {}
    payload["updated_at"] = datetime.now(timezone.utc).isoformat()
    symbols = payload.setdefault("symbols", {})
    for row in results:
        sym = str(row.get("symbol", "")).upper()
        if not sym:
            continue
        symbols[sym] = {
            "source": row.get("source"),
            "path": row.get("path"),
            "rows": row.get("rows"),
            "end": row.get("end"),
            "status": row.get("status"),
        }
    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def fix_os_state(symbols: list[str], *, root: Path, timeframes: list[str]) -> list[dict]:
    """增量刷新指定品种 OS state（与 rebuild_os_state_all 同引擎）。"""
    sys.path.insert(0, str(root / "scripts"))
    from rebuild_os_state_all import (  # noqa: WPS433
        discover_sources,
        parse_input_spec,
        rebuild_one,
        state_symbol,
    )

    os.environ["FENGJI_MARKET"] = "crypto"
    wanted = {_normalize_symbol(s) for s in symbols}
    state_dir = root / "runtime" / "fengji_os_state"
    out: list[dict] = []
    for tf in timeframes:
        tf_key = tf.strip().upper()
        spec_meta = TIMEFRAME_SPEC.get(tf_key)
        if not spec_meta:
            continue
        folder = spec_meta["folder"]
        spec = parse_input_spec(f"data/{folder},market=crypto")
        for source in discover_sources(spec):
            key = state_symbol(source.symbol, source.market)
            if key not in wanted and source.symbol not in wanted:
                continue
            row = rebuild_one(
                source,
                state_dir=state_dir,
                gap=3,
                mode="incremental",
                record_hardened_by_bar=bool(spec_meta["hbb"]),
                tail_rows=int(spec_meta["os_tail"]),
            )
            out.append(row)
    return out


def fix_os_state_15m(symbols: list[str], *, root: Path) -> list[dict]:
    return fix_os_state(symbols, root=root, timeframes=["M15"])


def main() -> int:
    parser = argparse.ArgumentParser(description="Sync missing crypto K线 via Binance or OKX fallback.")
    parser.add_argument("--symbols", default="HYPEUSDT,ATHUSDT")
    parser.add_argument("--timeframes", default="M15", help="comma-separated: M15,D1,H1")
    parser.add_argument("--data-dir", default="data")
    parser.add_argument("--root", default=str(ROOT))
    parser.add_argument("--force-okx", action="store_true")
    parser.add_argument("--fix-os", action="store_true", help="Incremental rebuild OS state after sync")
    parser.add_argument("--days", type=int, default=None, help="OKX lookback days override")
    args = parser.parse_args()
    base = Path(args.data_dir)
    root = Path(args.root)
    timeframes = [t.strip().upper() for t in args.timeframes.split(",") if t.strip()]
    results: list[dict] = []
    failed = 0
    for item in args.symbols.split(","):
        sym = item.strip()
        if not sym:
            continue
        sym = _normalize_symbol(sym)
        for tf in timeframes:
            try:
                if tf == "M15" and sym not in OKX_ONLY_SYMBOLS and not args.force_okx:
                    row = sync_symbol_15m(sym, base_dir=base, force_okx=False, days=args.days, root=root)
                elif sym in OKX_ONLY_SYMBOLS or args.force_okx:
                    row = sync_okx_timeframe(sym, timeframe=tf, root=root, days=args.days)
                else:
                    continue
                results.append(row)
                print(row)
            except Exception as exc:  # noqa: BLE001
                failed += 1
                err = {"symbol": sym, "timeframe": tf, "status": "error", "error": str(exc)}
                results.append(err)
                print(err)
    if results and "M15" in timeframes:
        update_manifest([r for r in results if r.get("timeframe", "M15") == "M15"])
        print(f"manifest={MANIFEST_PATH}")
    if args.fix_os and not failed:
        synced = sorted({_normalize_symbol(r["symbol"]) for r in results if r.get("status") == "ok"})
        if synced:
            fix_tfs = [tf for tf in timeframes if tf in TIMEFRAME_SPEC]
            fixed = fix_os_state(synced, root=root, timeframes=fix_tfs)
            for row in fixed:
                print({"os_fix": row.get("state_symbol"), "status": row.get("status"), "last_date": row.get("last_date")})
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
