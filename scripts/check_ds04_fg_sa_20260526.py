from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from quant.ds04 import candle_body, candle_range, k2_is_weakest, make_ds04_signal, no_price_gap  # noqa: E402


def find_row_by_date(df: pd.DataFrame, date_text: str) -> list[int]:
    dates = pd.to_datetime(df["date"], errors="coerce").dt.strftime("%Y-%m-%d")
    return df.index[dates == date_text].tolist()


def candle_dir(row: pd.Series) -> str:
    if float(row["close"]) > float(row["open"]):
        return "yang"
    if float(row["close"]) < float(row["open"]):
        return "yin"
    return "flat"


def row_text(label: str, idx: int, row: pd.Series) -> str:
    return (
        f"{label} idx={idx} date={row['date']} dir={candle_dir(row)} "
        f"O={float(row['open']):.8g} H={float(row['high']):.8g} "
        f"L={float(row['low']):.8g} C={float(row['close']):.8g} "
        f"body={candle_body(row):.8g} range={candle_range(row):.8g} "
        f"camp={row.get('camp', 'NA')}"
    )


def inspect_k3(df: pd.DataFrame, k3_idx: int) -> None:
    k1_idx, k2_idx = k3_idx - 2, k3_idx - 1
    print(f"\nCHECK_K3 idx={k3_idx} date={df.iloc[k3_idx]['date']}")
    if k1_idx < 1:
        print("FAIL not enough previous bars")
        return
    for label, idx in [("K1", k1_idx), ("K2", k2_idx), ("K3", k3_idx)]:
        print(row_text(label, idx, df.iloc[idx]))

    gap_prev_k1 = no_price_gap(df, k1_idx - 1, k1_idx)
    gap_k1_k2 = no_price_gap(df, k1_idx, k2_idx)
    gap_k2_k3 = no_price_gap(df, k2_idx, k3_idx)
    weakest = k2_is_weakest(df, k1_idx, k2_idx, k3_idx)
    k1, k2, k3 = df.iloc[k1_idx], df.iloc[k2_idx], df.iloc[k3_idx]
    dirs = (candle_dir(k1), candle_dir(k2), candle_dir(k3))
    long_reclaim = dirs == ("yang", "yin", "yang") and float(k3["close"]) > float(k1["high"])
    short_reclaim = dirs == ("yin", "yang", "yin") and float(k3["close"]) < float(k1["low"])
    print(f"no_gap_prevK1={gap_prev_k1} no_gap_K1K2={gap_k1_k2} no_gap_K2K3={gap_k2_k3}")
    print(f"k2_weakest={weakest}")
    print(f"dir_combo={dirs}")
    print(f"long_reclaim_close_gt_k1_high={long_reclaim} close={float(k3['close']):.8g} k1_high={float(k1['high']):.8g}")
    print(f"short_reclaim_close_lt_k1_low={short_reclaim} close={float(k3['close']):.8g} k1_low={float(k1['low']):.8g}")
    signal = make_ds04_signal(df, k3_idx)
    print(f"make_ds04_signal={signal}")
    if signal is not None and signal.activate_idx < len(df):
        k4 = df.iloc[signal.activate_idx]
        print(f"K4_ENTRY_DATE={k4['date']} K4_OPEN={float(k4['open']):.8g}")
    elif signal is not None:
        print("SIGNAL_CONFIRMED_BUT_NO_K4_BAR_YET")


def load_csv(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    df.columns = [str(c).strip().lower() for c in df.columns]
    if "datetime" in df.columns and "date" not in df.columns:
        df = df.rename(columns={"datetime": "date"})
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    for col in ["open", "high", "low", "close"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    return df.dropna(subset=["date", "open", "high", "low", "close"]).reset_index(drop=True)


def main() -> None:
    data_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "data"
    for symbol in ["FGUSDT", "SAUSDT"]:
        path = data_dir / "1d" / f"{symbol}.csv"
        print(f"\n===== {symbol} {path} =====")
        df = load_csv(path)
        tail = df.tail(8)[["date", "open", "high", "low", "close"]].copy()
        print("TAIL")
        print(tail.to_string(index=True))
        target_idxs = find_row_by_date(df, "2026-05-26")
        if not target_idxs:
            print("NO_ROW_WITH_DATE_2026-05-26")
        for idx in target_idxs:
            inspect_k3(df, idx)
        print("\nNEARBY_K3_CHECKS")
        start = max(3, len(df) - 8)
        for idx in range(start, len(df)):
            inspect_k3(df, idx)


if __name__ == "__main__":
    main()
