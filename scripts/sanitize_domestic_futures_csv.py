from __future__ import annotations

import argparse
import math
import shutil
from pathlib import Path
from typing import Any

import pandas as pd


try:
    from fengji_core.data import parse_tq_datetime_series, valid_futures_price_mask
except Exception:
    def parse_tq_datetime_series(series: pd.Series) -> pd.Series:
        numeric = pd.to_numeric(series, errors="coerce")
        if numeric.notna().any() and float(numeric.max(skipna=True)) > 1e14:
            return pd.to_datetime(numeric, unit="ns", errors="coerce")
        return pd.to_datetime(series, errors="coerce")

    def valid_futures_price_mask(frame: pd.DataFrame) -> pd.Series:
        required = ["open", "high", "low", "close"]
        prices = frame[required].apply(pd.to_numeric, errors="coerce")
        mask = prices.apply(lambda column: column.map(lambda value: math.isfinite(float(value)))).all(axis=1)
        mask &= (prices >= 1e-6).all(axis=1)
        mask &= (prices <= 1e8).all(axis=1)
        mask &= prices["high"] >= prices[["open", "close", "low"]].max(axis=1)
        mask &= prices["low"] <= prices[["open", "close", "high"]].min(axis=1)
        ratio = prices.max(axis=1) / prices.min(axis=1).replace(0, pd.NA)
        mask &= ratio <= 100.0
        return mask.fillna(False)


def finite_number(value: Any) -> bool:
    try:
        return math.isfinite(float(value))
    except (TypeError, ValueError):
        return False


def clean_frame(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    out.columns = [str(column).strip().lower() for column in out.columns]
    if "datetime" in out.columns:
        parsed = parse_tq_datetime_series(out["datetime"])
        if "date" in out.columns:
            fallback = pd.to_datetime(out["date"], errors="coerce")
            if fallback.notna().sum() > parsed.notna().sum():
                parsed = fallback
        out["date"] = parsed
    elif "date" in out.columns:
        out["date"] = pd.to_datetime(out["date"], errors="coerce")
    else:
        out["date"] = pd.to_datetime(out.iloc[:, 0], errors="coerce")

    for column in ["open", "high", "low", "close", "volume"]:
        if column in out.columns:
            out[column] = pd.to_numeric(out[column], errors="coerce")

    required = ["date", "open", "high", "low", "close"]
    missing = [column for column in required if column not in out.columns]
    if missing:
        return pd.DataFrame(columns=out.columns)

    mask = out["date"].notna()
    mask &= out["date"] >= pd.Timestamp("2020-01-01")
    mask &= out["date"] <= pd.Timestamp.now() + pd.Timedelta(days=1)
    for column in ["open", "high", "low", "close"]:
        mask &= out[column].map(finite_number)
    mask &= valid_futures_price_mask(out)
    out = out.loc[mask].sort_values("date").drop_duplicates("date", keep="last").reset_index(drop=True)
    if not out.empty:
        out["date"] = pd.to_datetime(out["date"]).dt.strftime("%Y-%m-%d %H:%M:%S")
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", default="data", type=Path)
    parser.add_argument("--backup-dir", default=None, type=Path)
    parser.add_argument("--symbols", default="")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    data_dir = args.data_dir
    backup_dir = args.backup_dir
    if args.apply and backup_dir is None:
        backup_dir = Path("runtime") / f"futures_csv_backup_{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}"

    changed = 0
    total_dropped = 0
    symbols = {item.strip().upper() for item in str(args.symbols).replace(";", ",").split(",") if item.strip()}
    for timeframe in ["1d", "1h", "15m"]:
        for path in sorted((data_dir / timeframe).glob("*.csv")):
            stem = path.stem.upper()
            base = stem[:-4] if stem.endswith("USDT") else stem
            if symbols and stem not in symbols and base not in symbols:
                continue
            try:
                frame = pd.read_csv(path)
            except Exception as exc:
                print(f"SKIP {path} read_error={exc}")
                continue
            cleaned = clean_frame(frame)
            dropped = len(frame) - len(cleaned)
            if dropped <= 0:
                continue
            changed += 1
            total_dropped += dropped
            print(f"{'CLEANED' if args.apply else 'WOULD_CLEAN'} {path} rows={len(frame)} kept={len(cleaned)} dropped={dropped}")
            if args.apply:
                target_backup = backup_dir / path.relative_to(data_dir)
                target_backup.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(path, target_backup)
                tmp = path.with_suffix(path.suffix + ".tmp")
                cleaned.to_csv(tmp, index=False, encoding="utf-8")
                tmp.replace(path)

    print(f"files_changed={changed} rows_dropped={total_dropped} apply={args.apply}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
