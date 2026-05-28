from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))
if str(ROOT / "packages" / "fengji_core") not in sys.path:
    sys.path.insert(0, str(ROOT / "packages" / "fengji_core"))

from backtest_ds07 import build_os_detail_frame  # noqa: E402
from fengji_total_radar import load_ohlcv  # noqa: E402
from quant.ds01 import build_lines_from_hardened, count_left_lines  # noqa: E402


def count_and_lines(nodes: list, i: int, price: float, lookback: int = 30) -> tuple[int, list[tuple]]:
    left = max(0, i - lookback)
    lines = []
    for a, b in build_lines_from_hardened(nodes):
        if a.point_idx < left or b.point_idx >= i:
            continue
        if min(a.price, b.price) <= price <= max(a.price, b.price):
            lines.append((a.point_idx, a.confirm_idx, a.raw_type, float(a.price), b.point_idx, b.confirm_idx, b.raw_type, float(b.price)))
    return len(lines), lines


def main() -> None:
    raw = load_ohlcv(ROOT / "data" / "1d" / "IOUSDT.csv", atr_window=14, tail_rows=520)
    os_df, engine = build_os_detail_frame(raw, gap=3)
    dates = pd.to_datetime(os_df["date"], errors="coerce").dt.strftime("%Y-%m-%d")
    i = dates[dates == "2026-05-26"].index[-1]
    prev = os_df.iloc[i - 1]
    cur = os_df.iloc[i]
    visible = engine.hardened_by_bar[i - 1]
    trigger = float(prev["high"])
    high = float(cur["high"])
    print(f"i={i}")
    print(f"prev_date={prev['date']} prev_open={prev['open']} prev_high={prev['high']} prev_low={prev['low']} prev_close={prev['close']} prev_camp={prev['camp']}")
    print(f"cur_date={cur['date']} cur_open={cur['open']} cur_high={cur['high']} cur_low={cur['low']} cur_close={cur['close']} cur_camp={cur['camp']}")
    for label, price in [("trigger_price_prev_high", trigger), ("current_day_high", high)]:
        count, lines = count_and_lines(visible, i, price)
        print(f"{label}={price} left_count={count} direct_count={count_left_lines(visible, i, price, 30)}")
        for line in lines:
            print("line", ",".join(str(x) for x in line))


if __name__ == "__main__":
    main()
