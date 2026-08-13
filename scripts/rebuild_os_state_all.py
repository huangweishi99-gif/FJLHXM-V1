"""Rebuild or incrementally refresh FengJi OS state files for live OHLCV CSVs.

This script is intentionally a state solidifier, not a strategy mutator.  It
uses the current FengJi OS identity engine and writes JSON states that later
runtime code can append from ``processed_len`` instead of recalculating history.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages" / "fengji_core"))

from fengji_core.data import parse_tq_datetime_series, valid_futures_price_mask  # noqa: E402
from fengji_core.os_engine import BLUE, RED, FengJiOSIdentityEngine  # noqa: E402
from fengji_core.os_state_store import (  # noqa: E402
    read_os_state,
    row_fingerprint,
    state_matches_frame,
    write_os_state,
)


TIMEFRAME_ALIASES = {
    "1d": "1d",
    "d1": "1d",
    "day": "1d",
    "daily": "1d",
    "1h": "1h",
    "h1": "1h",
    "60m": "1h",
    "60min": "1h",
    "15m": "15m",
    "m15": "15m",
    "15min": "15m",
}

DEFAULT_TAIL_ROWS = {
    "1d": 1095,
    "1h": 2400,
    "15m": 960,
}


@dataclass(frozen=True)
class InputSpec:
    root: Path
    market: str
    flat_timeframe: str | None = None


@dataclass
class SourceFile:
    path: Path
    symbol: str
    timeframe: str
    market: str


def canonical_timeframe(value: str) -> str:
    key = str(value).strip().lower()
    if key not in TIMEFRAME_ALIASES:
        raise ValueError(f"Unsupported timeframe: {value}")
    return TIMEFRAME_ALIASES[key]


def parse_input_spec(text: str) -> InputSpec:
    parts = [part.strip() for part in str(text).split(",") if part.strip()]
    if not parts:
        raise ValueError("--input cannot be empty")
    root = Path(parts[0])
    options: dict[str, str] = {}
    for item in parts[1:]:
        if "=" not in item:
            raise ValueError(f"Input option must use key=value: {item}")
        key, value = item.split("=", 1)
        options[key.strip().lower()] = value.strip()
    market = options.get("market", "crypto").lower()
    if market not in {"crypto", "futures"}:
        raise ValueError(f"Unsupported market: {market}")
    flat_timeframe = options.get("timeframe")
    return InputSpec(
        root=root,
        market=market,
        flat_timeframe=None if not flat_timeframe else canonical_timeframe(flat_timeframe),
    )


def normalize_columns(frame: pd.DataFrame) -> pd.DataFrame:
    column_map = {
        "时间": "date",
        "日期": "date",
        "开盘": "open",
        "最高": "high",
        "最低": "low",
        "收盘": "close",
        "成交量": "volume",
        "持仓量": "open_interest",
        "结算价": "settlement",
    }
    out = frame.copy()
    out.columns = [str(column).strip().lower() for column in out.columns]
    out = out.rename(columns={column: column_map.get(column, column) for column in out.columns})
    if "date" not in out.columns:
        for candidate in ["datetime", "timestamp", "time"]:
            if candidate in out.columns:
                out = out.rename(columns={candidate: "date"})
                break
    if "date" not in out.columns and len(out.columns) >= 5:
        out = out.rename(
            columns={
                out.columns[0]: "date",
                out.columns[1]: "open",
                out.columns[2]: "high",
                out.columns[3]: "low",
                out.columns[4]: "close",
            }
        )
    if "volume" not in out.columns:
        out["volume"] = 0.0
    return out


def futures_session_placeholder_mask(frame: pd.DataFrame) -> pd.Series:
    """Identify closed-session placeholder bars without deleting valid zero-volume bars."""
    zero_volume = frame["volume"].fillna(0) <= 0
    ohlc_range = frame[["open", "high", "low", "close"]].max(axis=1) - frame[
        ["open", "high", "low", "close"]
    ].min(axis=1)
    flat_ohlc = ohlc_range.abs() <= 1e-12
    return zero_volume & flat_ohlc


def load_ohlcv(path: Path, *, market: str, tail_rows: int = 0) -> pd.DataFrame:
    if path.stat().st_size <= 5:
        raise ValueError("empty_or_incomplete_csv")
    frame = normalize_columns(pd.read_csv(path))
    required = ["date", "open", "high", "low", "close", "volume"]
    missing = [column for column in required if column not in frame.columns]
    if missing:
        raise ValueError(f"missing_columns={missing}")
    frame = frame[required].copy()
    frame["date"] = parse_tq_datetime_series(frame["date"])
    for column in ["open", "high", "low", "close", "volume"]:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    frame = frame.dropna(subset=["date", "open", "high", "low", "close"])
    frame = frame[frame["date"] <= pd.Timestamp.now() + pd.Timedelta(days=1)]
    if market == "futures":
        frame = frame[(frame["date"] >= pd.Timestamp("2020-01-01")) & valid_futures_price_mask(frame)]
        frame = frame[~futures_session_placeholder_mask(frame)]
    else:
        frame = frame[
            (frame["date"] >= pd.Timestamp("2020-01-01"))
            & (frame["high"] >= frame["low"])
            & (frame["close"] > 0)
        ]
    frame = frame.sort_values("date").drop_duplicates("date", keep="last").reset_index(drop=True)
    if tail_rows > 0 and len(frame) > tail_rows:
        frame = frame.tail(tail_rows).reset_index(drop=True)
    if frame.empty:
        raise ValueError("no_valid_ohlcv_rows")
    return frame


def strip_timeframe_suffix(stem: str) -> str:
    text = stem.strip()
    for suffix in ["_1d", "-1d", "_d1", "-d1", "_1h", "-1h", "_h1", "-h1", "_15m", "-15m", "_m15", "-m15"]:
        if text.lower().endswith(suffix):
            return text[: -len(suffix)]
    return text


def infer_timeframe(path: Path, spec: InputSpec) -> str | None:
    if spec.flat_timeframe:
        return spec.flat_timeframe
    for part in reversed(path.parts):
        key = part.lower()
        if key in TIMEFRAME_ALIASES:
            return canonical_timeframe(key)
    stem = path.stem.lower()
    for token in ["1d", "d1", "1h", "h1", "60m", "15m", "m15"]:
        if stem.endswith(f"_{token}") or stem.endswith(f"-{token}"):
            return canonical_timeframe(token)
    return None


def discover_sources(spec: InputSpec) -> list[SourceFile]:
    root = spec.root
    if not root.exists():
        return []
    sources: list[SourceFile] = []
    for path in root.rglob("*.csv"):
        if path.name.lower() in {"radar.csv", "pending_orders.csv"}:
            continue
        timeframe = infer_timeframe(path, spec)
        if timeframe not in {"1d", "1h", "15m"}:
            continue
        symbol = strip_timeframe_suffix(path.stem).upper()
        if spec.market == "crypto" and not symbol.endswith("USDT"):
            continue
        if not symbol:
            continue
        sources.append(SourceFile(path=path, symbol=symbol, timeframe=timeframe, market=spec.market))
    return sorted(sources, key=lambda item: (item.market, item.symbol, item.timeframe, str(item.path)))


def state_symbol(symbol: str, market: str) -> str:
    text = symbol.strip().upper().replace("-", "").replace("_", "")
    if market == "futures":
        return text.removesuffix("USDT")
    return text if text.endswith("USDT") else f"{text}USDT"


def source_preference_key(source: SourceFile) -> tuple[int, str]:
    """Match runtime lookup: domestic futures prefer short-code CSV over USDT aliases."""
    if source.market == "futures" and source.symbol == state_symbol(source.symbol, source.market):
        return (0, str(source.path))
    return (1, str(source.path))


def state_path(state_dir: Path, source: SourceFile) -> Path:
    symbol = state_symbol(source.symbol, source.market).replace("/", "_").replace("\\", "_")
    return state_dir / f"{symbol}_{source.timeframe}.json"


def camp_name(value: int) -> str:
    if value == RED:
        return "red"
    if value == BLUE:
        return "blue"
    return "neutral"


def result_row(
    source: SourceFile,
    *,
    status: str,
    state_file: Path | None = None,
    rows: int = 0,
    engine: FengJiOSIdentityEngine | None = None,
    last_date: Any = "",
    first_date: Any = "",
    error: str = "",
    used_incremental: bool = False,
    record_hardened_by_bar: bool = True,
    tail_rows: int = 0,
) -> dict[str, Any]:
    active_high = active_low = None
    if engine is not None:
        active_high, active_low = engine.active_extremes()
    return {
        "status": status,
        "market": source.market,
        "symbol": source.symbol,
        "state_symbol": state_symbol(source.symbol, source.market),
        "timeframe": source.timeframe,
        "rows": rows,
        "processed_len": 0 if engine is None else engine.processed_len,
        "camp": "" if engine is None else camp_name(int(engine.camp)),
        "camp_confirmed": "" if engine is None else camp_name(int(engine.camp_confirmed)),
        "pending_turn": "" if engine is None else bool(engine.pending_turn),
        "hardened_count": 0 if engine is None else len(engine.hardened_nodes),
        "identity_count": 0 if engine is None else len(engine.identity_nodes),
        "turn_count": 0 if engine is None else len(engine.turns),
        "record_hardened_by_bar": record_hardened_by_bar,
        "tail_rows": tail_rows,
        "active_high": active_high,
        "active_low": active_low,
        "first_date": first_date,
        "last_date": last_date,
        "used_incremental": used_incremental,
        "source_csv": str(source.path),
        "state_file": "" if state_file is None else str(state_file),
        "error": error,
    }


def rebuild_one(
    source: SourceFile,
    *,
    state_dir: Path,
    gap: int,
    mode: str,
    record_hardened_by_bar: bool,
    tail_rows: int,
) -> dict[str, Any]:
    try:
        frame = load_ohlcv(source.path, market=source.market, tail_rows=tail_rows)
        out_state = state_path(state_dir, source)
        previous = read_os_state(out_state) if mode == "incremental" else None
        used_incremental = state_matches_frame(previous, frame, gap, record_hardened_by_bar)
        engine = FengJiOSIdentityEngine(gap=gap, record_hardened_by_bar=record_hardened_by_bar).run_from_state(
            frame,
            previous if used_incremental else None,
        )
        write_os_state(out_state, engine, frame, include_hardened_by_bar=record_hardened_by_bar)
        return result_row(
            source,
            status="ok",
            state_file=out_state,
            rows=len(frame),
            engine=engine,
            first_date=frame.iloc[0]["date"],
            last_date=frame.iloc[-1]["date"],
            used_incremental=used_incremental,
            record_hardened_by_bar=record_hardened_by_bar,
            tail_rows=tail_rows,
        )
    except Exception as exc:  # noqa: BLE001 - audit tool must keep going.
        return result_row(
            source,
            status="error",
            error=f"{type(exc).__name__}: {exc}",
            record_hardened_by_bar=record_hardened_by_bar,
            tail_rows=tail_rows,
        )


def write_outputs(rows: list[dict[str, Any]], out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    frame = pd.DataFrame(rows)
    frame.to_csv(out_dir / "os_state_audit.csv", index=False, encoding="utf-8-sig")
    (out_dir / "os_state_audit.json").write_text(
        json.dumps(rows, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    summary = {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "total": len(rows),
        "ok": sum(1 for row in rows if row["status"] == "ok"),
        "error": sum(1 for row in rows if row["status"] != "ok"),
        "by_market_timeframe": (
            frame.groupby(["market", "timeframe", "status"]).size().reset_index(name="count").to_dict("records")
            if not frame.empty
            else []
        ),
    }
    (out_dir / "os_state_audit_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Rebuild/refresh FengJi OS state for all D1/H1/15m CSVs.")
    parser.add_argument(
        "--input",
        action="append",
        required=True,
        help="CSV root spec: PATH[,market=crypto|futures][,timeframe=1d|1h|15m]. Repeatable.",
    )
    parser.add_argument("--state-dir", default="")
    parser.add_argument("--audit-dir", default="")
    parser.add_argument("--gap", type=int, default=3)
    parser.add_argument(
        "--tail-rows",
        type=int,
        default=0,
        help="Legacy override for all timeframes. 0 uses the agreed per-timeframe windows.",
    )
    parser.add_argument("--d1-tail", type=int, default=1095, help="D1 monitoring window. Default: 1095.")
    parser.add_argument("--h1-tail", type=int, default=2400, help="H1 monitoring window. Default: 2400.")
    parser.add_argument("--m15-tail", type=int, default=960, help="15m monitoring window. Default: 960.")
    parser.add_argument("--mode", choices=["rebuild", "incremental"], default="rebuild")
    parser.add_argument("--no-hardened-by-bar", action="store_true")
    parser.add_argument(
        "--full-intraday-hardened-by-bar",
        action="store_true",
        help="Also store per-bar hardened-line snapshots for 1h/15m. Large and slow; D1 always keeps them unless disabled.",
    )
    args = parser.parse_args()

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    state_dir = Path(args.state_dir) if args.state_dir else ROOT / "runtime" / f"fengji_os_state_rebuild_{stamp}"
    audit_dir = Path(args.audit_dir) if args.audit_dir else state_dir
    keep_hardened_by_bar = not args.no_hardened_by_bar

    specs = [parse_input_spec(item) for item in args.input]
    sources_by_key: dict[tuple[str, str, str], SourceFile] = {}
    for spec in specs:
        for source in discover_sources(spec):
            key = (source.market, state_symbol(source.symbol, source.market), source.timeframe)
            current = sources_by_key.get(key)
            if current is None or source_preference_key(source) < source_preference_key(current):
                sources_by_key[key] = source
    sources = sorted(
        sources_by_key.values(),
        key=lambda item: (item.market, state_symbol(item.symbol, item.market), item.timeframe),
    )

    if not sources:
        raise SystemExit("No D1/H1/15m CSV sources discovered.")

    tail_by_timeframe = {
        "1d": max(int(args.d1_tail or 0), DEFAULT_TAIL_ROWS["1d"]),
        "1h": max(int(args.h1_tail or 0), DEFAULT_TAIL_ROWS["1h"]),
        "15m": max(int(args.m15_tail or 0), DEFAULT_TAIL_ROWS["15m"]),
    }

    rows = []
    for source in sources:
        tail_rows = int(args.tail_rows or 0) or tail_by_timeframe[source.timeframe]
        rows.append(
            rebuild_one(
                source,
                state_dir=state_dir,
                gap=args.gap,
                mode=args.mode,
                record_hardened_by_bar=(
                    keep_hardened_by_bar
                    and (source.timeframe == "1d" or args.full_intraday_hardened_by_bar)
                ),
                tail_rows=tail_rows,
            )
        )
    write_outputs(rows, audit_dir)

    ok = sum(1 for row in rows if row["status"] == "ok")
    errors = len(rows) - ok
    print(f"state_dir={state_dir}")
    print(f"audit_csv={audit_dir / 'os_state_audit.csv'}")
    print(f"ok={ok} error={errors} total={len(rows)}")
    if errors:
        for row in rows:
            if row["status"] != "ok":
                print(f"ERROR {row['market']} {row['symbol']} {row['timeframe']}: {row['error']}")


if __name__ == "__main__":
    os.environ.setdefault("FENGJI_MARKET", "crypto")
    main()
