"""Shared stop-bar IO for crypto + domestic futures pending monitors."""
from __future__ import annotations

import math
from pathlib import Path
from typing import Any

import pandas as pd

from fengji_core.data import parse_tq_datetime_series, valid_futures_price_mask
from fengji_core.os_state_store import find_data_file, is_futures_market, normalize_symbol
from fengji_core.runtime_stop_updater import (
    TIMEFRAME_BY_STRATEGY,
    stop_bar_requires_completed_close,
)


def safe_float(value: Any) -> float | None:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(out):
        return None
    return out


def finite_number(value: Any) -> bool:
    try:
        return math.isfinite(float(value))
    except (TypeError, ValueError):
        return False


def filter_valid_price_rows(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    out["date"] = pd.to_datetime(out["date"], errors="coerce")
    for column in ["open", "high", "low", "close", "volume"]:
        if column in out.columns:
            out[column] = pd.to_numeric(out[column], errors="coerce")
    mask = out["date"].notna()
    mask &= out["date"] >= pd.Timestamp("2020-01-01")
    mask &= out["date"] <= pd.Timestamp.now() + pd.Timedelta(days=1)
    for column in ["open", "high", "low", "close"]:
        mask &= out[column].map(finite_number)
    if is_futures_market():
        mask &= valid_futures_price_mask(out)
    out = out.loc[mask].copy()
    if not out.empty and "volume" in out.columns:
        zero_volume = out["volume"].fillna(0) <= 0
        ohlc_range = out[["open", "high", "low", "close"]].max(axis=1) - out[
            ["open", "high", "low", "close"]
        ].min(axis=1)
        out = out.loc[~(zero_volume & (ohlc_range.abs() <= 1e-12))].copy()
    return out.sort_values("date").drop_duplicates("date", keep="last").reset_index(drop=True)


def read_latest_bar(
    data_dir: Path,
    symbol: str,
    timeframes: list[str],
    *,
    completed_only: bool = False,
) -> dict[str, Any] | None:
    for timeframe in timeframes:
        path = find_data_file(data_dir, symbol, timeframe)
        if not path.exists():
            continue
        try:
            frame = pd.read_csv(path)
        except Exception:
            continue
        if frame.empty:
            continue
        frame.columns = [str(col).strip().lower() for col in frame.columns]
        if "date" not in frame.columns:
            if "datetime" in frame.columns:
                frame["date"] = frame["datetime"]
            else:
                frame["date"] = frame.iloc[:, 0]
        required = {"date", "open", "high", "low", "close"}
        if not required.issubset(set(frame.columns)):
            continue
        frame["date"] = parse_tq_datetime_series(frame["date"])
        frame = filter_valid_price_rows(frame)
        if frame.empty:
            continue
        use_completed = completed_only or stop_bar_requires_completed_close(timeframe)
        if use_completed:
            if len(frame) >= 2:
                row = frame.iloc[-2]
            elif len(frame) == 1:
                row = frame.iloc[-1]
            else:
                continue
        else:
            row = frame.tail(1).iloc[0]
        try:
            return {
                "symbol": normalize_symbol(symbol),
                "timeframe": timeframe,
                "date": str(pd.to_datetime(row["date"]).strftime("%Y-%m-%d %H:%M:%S")),
                "open": float(row["open"]),
                "high": float(row["high"]),
                "low": float(row["low"]),
                "close": float(row["close"]),
            }
        except Exception:
            continue
    return None


def normalize_timeframe(value: Any) -> str | None:
    text = str(value or "").strip().lower()
    if not text:
        return None
    aliases = {
        "d": "1d",
        "day": "1d",
        "daily": "1d",
        "d1": "1d",
        "1day": "1d",
        "h": "1h",
        "h1": "1h",
        "hour": "1h",
        "hourly": "1h",
        "60m": "1h",
        "m15": "15m",
        "15min": "15m",
        "15minute": "15m",
    }
    return aliases.get(text, text)


def stop_timeframe_for_position(position: dict[str, Any]) -> str | None:
    strategy_id = str(position.get("strategy_id", "")).strip().upper()
    if strategy_id in TIMEFRAME_BY_STRATEGY:
        return TIMEFRAME_BY_STRATEGY[strategy_id]
    return normalize_timeframe(position.get("timeframe"))


def read_stop_bar_for_position(
    args: Any, symbol: str, position: dict[str, Any]
) -> dict[str, Any] | None:
    timeframe = stop_timeframe_for_position(position)
    if timeframe is None:
        return None
    completed_only = stop_bar_requires_completed_close(timeframe)
    data_dir = Path(getattr(args, "data_dir", "data"))
    return read_latest_bar(data_dir, symbol, [timeframe], completed_only=completed_only)


def position_side_int(position: dict[str, Any]) -> int:
    side = position.get("side")
    if isinstance(side, str):
        text = side.strip().lower()
        if text in {"long", "1"}:
            return 1
        if text in {"short", "-1"}:
            return -1
    try:
        return int(side or 0)
    except (TypeError, ValueError):
        return 0


def position_stop(position: dict[str, Any]) -> float | None:
    stop = safe_float(position.get("current_stop"))
    if stop is None:
        stop = safe_float(position.get("initial_stop"))
    if stop is None:
        stop = safe_float(position.get("stop_price"))
    if stop is None or stop <= 0:
        return None
    return stop


def stop_crossed(position: dict[str, Any], bar: dict[str, Any]) -> bool:
    stop = position_stop(position)
    if stop is None:
        return False
    side = position_side_int(position)
    if side == 1:
        return float(bar["low"]) <= stop
    if side == -1:
        return float(bar["high"]) >= stop
    return False


def stop_bar_after_entry(position: dict[str, Any], bar: dict[str, Any]) -> bool:
    entry_time = pd.to_datetime(position.get("entry_time") or position.get("created_at"), errors="coerce")
    bar_time = pd.to_datetime(bar.get("date"), errors="coerce")
    if pd.isna(entry_time) or pd.isna(bar_time):
        return True
    return bool(bar_time > entry_time)


def stop_exit_fill(position: dict[str, Any], bar: dict[str, Any]) -> tuple[float, str]:
    """Gap stop when open gaps through stop; otherwise fill at stop."""
    stop = position_stop(position)
    side = position_side_int(position)
    open_px = safe_float(bar.get("open"))
    if stop is None:
        return (open_px if open_px is not None else 0.0), "stop"
    if open_px is None:
        return stop, "stop"
    if side == 1:
        return (open_px, "gap_stop") if open_px <= stop else (stop, "stop")
    if side == -1:
        return (open_px, "gap_stop") if open_px >= stop else (stop, "stop")
    return stop, "stop"
