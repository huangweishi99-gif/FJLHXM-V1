from __future__ import annotations

import math
from pathlib import Path

import pandas as pd


REQUIRED_COLUMNS = {"date", "open", "high", "low", "close", "volume"}
FUTURES_MIN_PRICE = 1e-6
FUTURES_MAX_PRICE = 1e8
FUTURES_MAX_OHLC_RATIO = 100.0


def read_csv_strict(path: str | Path) -> pd.DataFrame:
    """Read CSV; fail clearly on empty/truncated files (common during data sync)."""
    csv_path = Path(path)
    if not csv_path.exists():
        raise FileNotFoundError(f"CSV file not found: {csv_path}")
    if csv_path.stat().st_size <= 5:
        raise ValueError(f"CSV file is empty or incomplete: {csv_path}")
    try:
        return pd.read_csv(csv_path)
    except pd.errors.EmptyDataError as exc:
        raise ValueError(f"CSV file has no parseable columns: {csv_path}") from exc


def parse_tq_datetime_series(series: pd.Series) -> pd.Series:
  """Parse Tianqin kline ``datetime`` (usually nanoseconds since epoch)."""
  numeric = pd.to_numeric(series, errors="coerce")
  if numeric.notna().any() and float(numeric.max(skipna=True)) > 1e14:
    return pd.to_datetime(numeric, unit="ns", errors="coerce")
  return pd.to_datetime(series, errors="coerce")


def valid_futures_price_mask(
  frame: pd.DataFrame,
  *,
  min_price: float = FUTURES_MIN_PRICE,
  max_price: float = FUTURES_MAX_PRICE,
  max_ohlc_ratio: float = FUTURES_MAX_OHLC_RATIO,
) -> pd.Series:
  """Return a conservative mask for domestic futures OHLC price sanity.

  Tianqin has occasionally returned corrupted rows whose values are finite and
  positive but physically impossible, for example tiny subnormal prices mixed
  with huge highs.  Basic OHLC relation checks are not enough for those rows.
  """
  index = frame.index
  required = ["open", "high", "low", "close"]
  missing = [column for column in required if column not in frame.columns]
  if missing:
    return pd.Series(False, index=index)

  prices = frame[required].apply(pd.to_numeric, errors="coerce")
  finite = prices.apply(lambda column: column.map(lambda value: math.isfinite(float(value))))
  mask = finite.all(axis=1)
  mask &= (prices >= min_price).all(axis=1)
  mask &= (prices <= max_price).all(axis=1)
  mask &= prices["high"] >= prices[["open", "close", "low"]].max(axis=1)
  mask &= prices["low"] <= prices[["open", "close", "high"]].min(axis=1)

  min_ohlc = prices.min(axis=1)
  max_ohlc = prices.max(axis=1)
  ratio = max_ohlc / min_ohlc.replace(0, pd.NA)
  mask &= ratio <= max_ohlc_ratio
  return mask.fillna(False)


def filter_valid_futures_ohlcv(frame: pd.DataFrame, min_close: float = 100.0) -> pd.DataFrame:
  out = frame.copy()
  out["date"] = pd.to_datetime(out["date"], errors="coerce")
  for column in ["open", "high", "low", "close", "volume"]:
    if column in out.columns:
      out[column] = pd.to_numeric(out[column], errors="coerce")
  if "volume" not in out.columns:
    out["volume"] = 0.0
  out = out.dropna(subset=["date", "open", "high", "low", "close"])
  out = out[(out["date"] >= pd.Timestamp("2020-01-01")) & (out["date"] <= pd.Timestamp("2031-12-31"))]
  out = out[valid_futures_price_mask(out) & (out["high"] > out["low"]) & (out["close"] >= min_close)]
  return out.sort_values("date").drop_duplicates("date", keep="last").reset_index(drop=True)


def load_tq_futures_kline_csv(path: str | Path, min_close: float = 100.0) -> pd.DataFrame:
  """Load domestic Tianqin pump CSV (datetime + OHLC columns)."""
  frame = read_csv_strict(path)
  frame.columns = [str(column).strip().lower() for column in frame.columns]
  if "datetime" in frame.columns:
    parsed = parse_tq_datetime_series(frame["datetime"])
    if "date" in frame.columns:
      fallback = pd.to_datetime(frame["date"], errors="coerce")
      if fallback.notna().sum() > parsed.notna().sum():
        parsed = fallback
    frame["date"] = parsed
  elif "date" in frame.columns:
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
  else:
    raise ValueError(f"CSV must contain date or datetime column: {path}")
  required = ["open", "high", "low", "close"]
  missing = [column for column in required if column not in frame.columns]
  if missing:
    raise ValueError(f"CSV is missing required columns: {', '.join(missing)}")
  cleaned = filter_valid_futures_ohlcv(frame[["date", *required, *(["volume"] if "volume" in frame.columns else [])]], min_close=min_close)
  if cleaned.empty:
    raise ValueError(f"CSV has no valid futures OHLCV rows after cleaning: {path}")
  if "volume" not in cleaned.columns:
    cleaned["volume"] = 0.0
  return cleaned[["date", "open", "high", "low", "close", "volume"]]


def load_ohlcv_csv(path: str | Path) -> pd.DataFrame:
    """Load and validate OHLCV data from CSV."""
    csv_path = Path(path)
    frame = read_csv_strict(csv_path)
    frame.columns = [column.strip().lower() for column in frame.columns]
    if "date" not in frame.columns:
        for candidate in ["timestamp", "datetime", "time"]:
            if candidate in frame.columns:
                frame = frame.rename(columns={candidate: "date"})
                break

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
