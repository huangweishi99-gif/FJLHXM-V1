from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "packages" / "fengji_core") not in sys.path:
    sys.path.insert(0, str(ROOT / "packages" / "fengji_core"))
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from backtest_ds07 import build_os_detail_frame  # noqa: E402
from fengji_total_radar import load_ohlcv  # noqa: E402
from quant.ds03 import make_ds03_signal, resolve_ds03_attack  # noqa: E402


def fmt(value: object) -> str:
    if pd.isna(value):
        return "nan"
    if isinstance(value, float):
        return f"{value:.10g}"
    return str(value)


def main() -> None:
    csv_path = ROOT / "data" / "1d" / "IOUSDT.csv"
    raw = load_ohlcv(csv_path, atr_window=14, tail_rows=520)
    os_df, _ = build_os_detail_frame(raw, gap=3)
    dates = pd.to_datetime(os_df["date"], errors="coerce").dt.strftime("%Y-%m-%d")
    matches = os_df.index[dates == "2026-05-26"].tolist()
    if not matches:
        raise SystemExit("NO_2026_05_26_ROW")
    i = matches[-1]
    if i <= 0:
        raise SystemExit("NO_PREVIOUS_ROW")
    prev = os_df.iloc[i - 1]
    cur = os_df.iloc[i]
    attack = resolve_ds03_attack(os_df, i)
    signal = make_ds03_signal(os_df, i)
    camp = int(prev.get("camp", 0))
    if camp == 1:
        side = "long"
        trigger = float(prev["active_high"])
        crossed = float(cur["high"]) > trigger
        distance = (trigger - float(cur["close"])) / float(cur["close"])
        stop = min(float(prev["low"]), float(cur["low"]))
    elif camp == -1:
        side = "short"
        trigger = float(prev["active_low"])
        crossed = float(cur["low"]) < trigger
        distance = (float(cur["close"]) - trigger) / float(cur["close"])
        stop = max(float(prev["high"]), float(cur["high"]))
    else:
        side = "none"
        trigger = float("nan")
        crossed = False
        distance = float("nan")
        stop = float("nan")

    cols = [
        "date",
        "open",
        "high",
        "low",
        "close",
        "camp",
        "active_high",
        "active_low",
        "red_peak_idx",
        "blue_peak_idx",
        "red_peak_price",
        "red_ext_price",
        "blue_peak_price",
        "blue_ext_price",
        "last_failed_high_idx",
        "last_failed_high_price",
        "last_failed_low_idx",
        "last_failed_low_price",
    ]
    print("CSV", csv_path)
    print("INDEX", i)
    print("PREV_ROW")
    for col in cols:
        if col in prev.index:
            print(f"{col}={fmt(prev[col])}")
    print("CUR_ROW")
    for col in cols:
        if col in cur.index:
            print(f"{col}={fmt(cur[col])}")
    print("DS03_CHECK")
    print(f"side={side}")
    print(f"trigger={fmt(trigger)}")
    print(f"crossed={crossed}")
    print(f"stop={fmt(stop)}")
    print(f"distance_to_trigger_vs_close={fmt(distance)}")
    print(f"resolve_ds03_attack={attack}")
    print(f"make_ds03_signal={signal}")


if __name__ == "__main__":
    main()
