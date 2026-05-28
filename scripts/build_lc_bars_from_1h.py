"""由国内天勤 1h CSV 合成 1d / 15m（仅在天勤 15m 脏数据时做流水线联调，非实盘数据源）。"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages" / "fengji_core"))

from fengji_core.data import load_tq_futures_kline_csv  # noqa: E402


def resample_bars(h1: pd.DataFrame, rule: str) -> pd.DataFrame:
    indexed = h1.set_index(pd.to_datetime(h1["date"]))
    out = (
        indexed.resample(rule, label="left", closed="left")
        .agg({"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"})
        .dropna(subset=["open", "high", "low", "close"])
        .reset_index()
        .rename(columns={"index": "date"})
    )
    if "date" not in out.columns:
        out = out.rename(columns={out.columns[0]: "date"})
    out["volume"] = out["volume"].fillna(0)
    return out[["date", "open", "high", "low", "close", "volume"]]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--h1-csv", type=Path, required=True)
    parser.add_argument("--out-1d", type=Path, required=True)
    parser.add_argument("--out-15m", type=Path, required=True)
    args = parser.parse_args()

    h1 = load_tq_futures_kline_csv(args.h1_csv)
    d1 = resample_bars(h1, "1D")
    m15 = resample_bars(h1, "15min")
    args.out_1d.parent.mkdir(parents=True, exist_ok=True)
    args.out_15m.parent.mkdir(parents=True, exist_ok=True)
    d1.assign(date=d1["date"].dt.strftime("%Y-%m-%d %H:%M:%S")).to_csv(args.out_1d, index=False)
    m15.assign(date=m15["date"].dt.strftime("%Y-%m-%d %H:%M:%S")).to_csv(args.out_15m, index=False)
    print(f"1h={len(h1)} -> 1d={len(d1)} 15m={len(m15)}")
    print(f"wrote {args.out_1d}")
    print(f"wrote {args.out_15m}")


if __name__ == "__main__":
    main()
