from __future__ import annotations

from pathlib import Path

import pandas as pd


REQUIRED_COLUMNS = {"date", "open", "high", "low", "close", "volume"}


def load_ohlcv_csv(path: str | Path) -> pd.DataFrame:
    """Load and validate OHLCV data from CSV."""
    csv_path = Path(path)
    if not csv_path.exists():
        raise FileNotFoundError(f"CSV file not found: {csv_path}")

    frame = pd.read_csv(csv_path)
    frame.columns = [column.strip().lower() for column in frame.columns]

    missing = REQUIRED_COLUMNS.difference(frame.columns)
    if missing:
        missing_list = ", ".join(sorted(missing))
        raise ValueError(f"CSV is missing required columns: {missing_list}")

    frame["date"] = pd.to_datetime(frame["date"], errors="raise")
    frame = frame.sort_values("date").drop_duplicates("date")
    frame = frame.set_index("date")

    numeric_columns = ["open", "high", "low", "close", "volume"]
    frame[numeric_columns] = frame[numeric_columns].apply(pd.to_numeric, errors="raise")
    frame = frame.dropna(subset=numeric_columns)

    if frame.empty:
        raise ValueError("CSV has no valid OHLCV rows after cleaning.")

    return frame


def add_atr(frame: pd.DataFrame, window: int = 14) -> pd.DataFrame:
    """Add true range and ATR columns."""
    if window <= 0:
        raise ValueError("ATR window must be positive.")

    out = frame.copy()
    prev_close = out["close"].shift(1)
    ranges = pd.concat(
        [
            out["high"] - out["low"],
            (out["high"] - prev_close).abs(),
            (out["low"] - prev_close).abs(),
        ],
        axis=1,
    )
    out["tr"] = ranges.max(axis=1)
    out["atr"] = out["tr"].rolling(window).mean()
    return out


def load_ohlcv_for_engine(path: str | Path, atr_window: int = 14) -> pd.DataFrame:
    """Load OHLCV data with a plain integer index and date column."""
    frame = load_ohlcv_csv(path).reset_index()
    return add_atr(frame, atr_window)
