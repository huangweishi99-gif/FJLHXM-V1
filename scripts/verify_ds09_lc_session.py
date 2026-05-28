"""校验国内期货 LC 的 DS09 夜盘 session_date 映射与雷达候选。"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "packages" / "fengji_core"))

from fengji_core.ds09 import assign_session_date, build_prev_day_boundary_map
from fengji_core.os_state_store import is_futures_market
from backtest_ds09 import DS09BacktestConfig, load_frame, load_m15_frame, run_ds09_backtest
from quant.ds07 import attach_os_detail
from fengji_core.os_engine import FengJiOSIdentityEngine


def load_d1(path: Path) -> pd.DataFrame:
    df = load_frame(path, 14)
    engine = FengJiOSIdentityEngine(gap=3, record_hardened_by_bar=True).run(df)
    return attach_os_detail(df, engine)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--d1-csv", required=True)
    parser.add_argument("--m15-csv", required=True)
    args = parser.parse_args()

    os.environ.setdefault("FENGJI_MARKET", "futures")
    d1_path = Path(args.d1_csv)
    m15_path = Path(args.m15_csv)
    d1 = load_d1(d1_path)
    m15_raw = load_m15_frame(m15_path, 14)
    m15_sess = assign_session_date(m15_raw, d1, futures=is_futures_market())

    night = m15_raw[pd.to_datetime(m15_raw["date"]).dt.hour >= 21].head(5)
    sample = []
    for _, row in night.iterrows():
        idx = row.name
        mapped = m15_sess.loc[m15_sess.index == idx] if idx in m15_sess.index else None
        sample.append(
            {
                "bar": str(row["date"]),
                "hour": int(pd.to_datetime(row["date"]).hour),
                "session_date": str(mapped["session_date"].iloc[0]) if mapped is not None and not mapped.empty else None,
            }
        )

    boundary_days = len(build_prev_day_boundary_map(d1))
    cfg = DS09BacktestConfig(futures_mode=True, gap=3)
    bt = run_ds09_backtest(d1, m15_raw, cfg, symbol="LC")
    trades = int(len(bt["trades"]))
    bad = int(len(bt["bad_trades"]))

    report = {
        "futures_market": is_futures_market(),
        "d1_rows": len(d1),
        "m15_rows": len(m15_raw),
        "m15_mapped_rows": len(m15_sess),
        "boundary_sessions": boundary_days,
        "night_session_samples": sample,
        "ds09_trades": trades,
        "ds09_bad_trades": bad,
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if bad > 0:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
