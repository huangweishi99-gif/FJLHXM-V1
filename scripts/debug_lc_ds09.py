"""Debug LC DS09: count lock / attack / defense / signal stages."""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
os.environ["FENGJI_MARKET"] = "futures"

from backtest_ds09 import build_os_detail_frame, load_frame, load_m15_frame, run_ds09_backtest, DS09BacktestConfig
from fengji_core.ds09 import assign_session_date, build_prev_day_boundary_map, make_ds09_signal


def main() -> None:
    d1_raw = load_frame(ROOT / "data/futures_lc/1d/LC.csv", 14)
    m15_raw = load_m15_frame(ROOT / "data/futures_lc/15m/LC.csv", 14)
    d1_os, _ = build_os_detail_frame(d1_raw, 3)
    m15_os, _ = build_os_detail_frame(m15_raw, 3)
    bm = build_prev_day_boundary_map(d1_os)
    m15s = assign_session_date(m15_os, d1_raw, futures=True)

    locks = 0
    sigs = 0
    day_states: dict = {}
    for i, row in m15s.iterrows():
        sd = pd.to_datetime(row["session_date"]).normalize()
        if sd not in bm:
            continue
        if sd not in day_states:
            day_states[sd] = {
                **bm[sd],
                "lock_idx": None,
                "consumed": False,
                "attack_idx": None,
                "attack_price": None,
                "defense_idx": None,
                "defense_price": None,
            }
        st = day_states[sd]
        if st.get("consumed"):
            continue
        if st.get("lock_idx") is None:
            boundary = float(st["boundary"])
            if st["mode"] == "LONG" and float(row["high"]) > boundary:
                st["lock_idx"] = int(i)
                locks += 1
            elif st["mode"] == "SHORT" and float(row["low"]) < boundary:
                st["lock_idx"] = int(i)
                locks += 1
        else:
            signal = make_ds09_signal(row, st, symbol="LC")
            if signal is not None:
                sigs += 1

    bt = run_ds09_backtest(d1_raw, m15_raw, DS09BacktestConfig(futures_mode=True, gap=3), symbol="LC")
    hours = pd.to_datetime(m15_raw["date"]).dt.hour
    print("m15_rows", len(m15_raw), "night_21plus", int((hours >= 21).sum()), "early_morning_0_6", int(((hours >= 0) & (hours < 7)).sum()))
    print("boundary_sessions", len(bm), "locks", locks, "manual_sigs", sigs, "bt_trades", len(bt["trades"]))


if __name__ == "__main__":
    main()
