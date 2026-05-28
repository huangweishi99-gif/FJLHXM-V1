from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd


def bool_text(value: bool) -> str:
    return "PASS" if value else "FAIL"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", required=True)
    parser.add_argument("--symbol", default="")
    parser.add_argument("--tail", type=int, default=12)
    parser.add_argument("--atr-window", type=int, default=14)
    parser.add_argument("--gap", type=int, default=3)
    parser.add_argument("--extreme-atr-tol", type=float, default=0.80)
    args = parser.parse_args()

    root = Path.cwd()
    sys.path.insert(0, str(root / "src"))

    from quant.data import load_ohlcv_for_engine
    from backtest_ds05 import DS05BacktestConfig, build_os_frame, run_ds05_backtest
    from quant.ds05 import has_price_gap_with_prev, make_ds05_signal
    from quant.futures_specs import get_futures_spec

    csv_path = Path(args.csv)
    df = load_ohlcv_for_engine(csv_path, args.atr_window).reset_index(drop=True)
    os_df, engine = build_os_frame(df, args.gap)
    config = DS05BacktestConfig(
        atr_window=args.atr_window,
        gap=args.gap,
        extreme_atr_tol=args.extreme_atr_tol,
        futures_mode=True,
        spec=get_futures_spec(csv_path),
    )
    result = run_ds05_backtest(df, config)
    trades = result["trades"]

    symbol = args.symbol or csv_path.stem
    print(f"SYMBOL {symbol}")
    print(f"CSV {csv_path}")
    print(f"ROWS {len(os_df)} START {os_df['date'].iloc[0]} END {os_df['date'].iloc[-1]}")
    print(f"HARDENED_NODES {len(engine.hardened_nodes)} IDENTITY_NODES {len(engine.identity_nodes)} TURNS {len(engine.turns)}")
    print("")
    cols = ["date", "open", "high", "low", "close", "atr", "camp", "active_high", "active_low"]
    print("LATEST_ROWS")
    print(os_df[cols].tail(args.tail).to_string(index=True))
    print("")

    print("RECENT_DS05_SIGNALS")
    signal_rows = []
    for i in range(len(os_df)):
        signal = make_ds05_signal(os_df, i, args.extreme_atr_tol)
        if signal is not None:
            signal_rows.append(
                {
                    "idx": i,
                    "date": os_df.iloc[i]["date"],
                    "side": "long" if signal.side == 1 else "short",
                    "entry": signal.entry_price,
                    "stop": signal.initial_stop,
                    "k1": signal.k1,
                    "k2": signal.k2,
                    "k3": signal.k3,
                    "camp": signal.signal_camp,
                    "active_extreme": signal.active_extreme,
                }
            )
    if signal_rows:
        print(pd.DataFrame(signal_rows).tail(20).to_string(index=False))
    else:
        print("NONE")
    print("")

    print("RECENT_BACKTEST_TRADES")
    if not trades.empty:
        keep = ["trade_no", "direction", "entry_date", "entry_price", "initial_stop", "k1", "k2", "k3", "camp_k2", "camp_k3"]
        print(trades[keep].tail(20).to_string(index=False))
    else:
        print("NONE")
    print("")

    print("DS05_WINDOW_AUDIT")
    start = max(4, len(os_df) - args.tail)
    for i in range(start, len(os_df)):
        k1_idx, k2_idx, k3_idx = i - 2, i - 1, i
        k1 = os_df.iloc[k1_idx]
        k2 = os_df.iloc[k2_idx]
        k3 = os_df.iloc[k3_idx]
        camp_k2 = int(k2["camp"])
        camp_k3 = int(k3["camp"])
        signal_camp = camp_k3 if camp_k2 == camp_k3 else 0
        gap_ok = not has_price_gap_with_prev(os_df, k2_idx)
        long_checks = {
            "camp_red_k2k3": camp_k2 == 1 and camp_k3 == 1,
            "no_gap_k2": gap_ok,
            "k2_low_lt_k1_low": float(k2["low"]) < float(k1["low"]),
            "k2_low_4bar_min": float(k2["low"]) == float(os_df["low"].iloc[k2_idx - 3 : k2_idx + 1].min()),
            "k3_low_ge_k2_low": float(k3["low"]) >= float(k2["low"]),
            "k3_high_gt_k2_high": float(k3["high"]) > float(k2["high"]),
        }
        short_checks = {
            "camp_blue_k2k3": camp_k2 == -1 and camp_k3 == -1,
            "no_gap_k2": gap_ok,
            "k2_high_gt_k1_high": float(k2["high"]) > float(k1["high"]),
            "k2_high_4bar_max": float(k2["high"]) == float(os_df["high"].iloc[k2_idx - 3 : k2_idx + 1].max()),
            "k3_high_le_k2_high": float(k3["high"]) <= float(k2["high"]),
            "k3_low_lt_k2_low": float(k3["low"]) < float(k2["low"]),
        }
        signal = make_ds05_signal(os_df, i, args.extreme_atr_tol)
        print(f"idx={i} date={k3['date']} k1={k1['date']} k2={k2['date']} k3={k3['date']} camp_k2={camp_k2} camp_k3={camp_k3} signal={'LONG' if signal and signal.side == 1 else 'SHORT' if signal and signal.side == -1 else 'NONE'}")
        print(f"  k1 H/L={float(k1['high'])}/{float(k1['low'])} k2 H/L={float(k2['high'])}/{float(k2['low'])} k3 H/L={float(k3['high'])}/{float(k3['low'])} atr_k2={float(k2['atr'])} candidate_low={float(k2['low'])} candidate_high={float(k2['high'])}")
        print("  LONG  " + " ".join(f"{name}={bool_text(val)}" for name, val in long_checks.items()))
        print("  SHORT " + " ".join(f"{name}={bool_text(val)}" for name, val in short_checks.items()))


if __name__ == "__main__":
    main()
