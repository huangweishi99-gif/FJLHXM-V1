from __future__ import annotations

from dataclasses import asdict, dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class DS05Signal:
    side: int
    activate_idx: int
    entry_price: float
    initial_stop: float
    pattern: str
    k1: int
    k2: int
    k3: int
    active_extreme: float
    camp_k1: int
    camp_k2: int
    camp_k3: int
    signal_camp: int

    def to_dict(self) -> dict[str, int | float | str]:
        return asdict(self)


def has_price_gap_with_prev(df: pd.DataFrame, idx: int) -> bool:
    if idx <= 0:
        return True
    prev_high = float(df.iloc[idx - 1]["high"])
    prev_low = float(df.iloc[idx - 1]["low"])
    cur_high = float(df.iloc[idx]["high"])
    cur_low = float(df.iloc[idx]["low"])
    return cur_low > prev_high or cur_high < prev_low


def near_active_extreme(row: pd.Series, price: float, active_price: float, tol: float = 0.80) -> bool:
    if np.isnan(active_price):
        return False
    atr = float(row.get("atr", np.nan))
    if np.isnan(atr) or atr <= 0:
        return False
    return abs(float(price) - float(active_price)) <= atr * tol


def make_ds05_signal(df: pd.DataFrame, i: int, extreme_atr_tol: float = 0.80) -> DS05Signal | None:
    if i < 4 or i >= len(df):
        return None

    k1_idx, k2_idx, k3_idx = i - 2, i - 1, i
    k1 = df.iloc[k1_idx]
    k2 = df.iloc[k2_idx]
    k3 = df.iloc[k3_idx]
    camp_k1 = int(k1["camp"])
    camp_k2 = int(k2["camp"])
    camp_k3 = int(k3["camp"])

    if camp_k2 != camp_k3:
        return None
    signal_camp = camp_k3
    if signal_camp not in {1, -1}:
        return None
    if has_price_gap_with_prev(df, k2_idx):
        return None

    active_high = float(k3["active_high"])
    active_low = float(k3["active_low"])

    if signal_camp == 1:
        ok = (
            float(k2["low"]) < float(k1["low"])
            and float(k2["low"]) == float(df["low"].iloc[k2_idx - 3 : k2_idx + 1].min())
            and near_active_extreme(k2, float(k2["low"]), active_low, extreme_atr_tol)
            and float(k3["low"]) >= float(k2["low"])
            and float(k3["high"]) > float(k2["high"])
        )
        if ok:
            return DS05Signal(
                side=1,
                activate_idx=i,
                entry_price=max(float(k3["open"]), float(k2["high"])),
                initial_stop=float(k2["low"]),
                pattern="DS05 Bullish Finger",
                k1=k1_idx,
                k2=k2_idx,
                k3=k3_idx,
                active_extreme=active_low,
                camp_k1=camp_k1,
                camp_k2=camp_k2,
                camp_k3=camp_k3,
                signal_camp=signal_camp,
            )

    if signal_camp == -1:
        ok = (
            float(k2["high"]) > float(k1["high"])
            and float(k2["high"]) == float(df["high"].iloc[k2_idx - 3 : k2_idx + 1].max())
            and near_active_extreme(k2, float(k2["high"]), active_high, extreme_atr_tol)
            and float(k3["high"]) <= float(k2["high"])
            and float(k3["low"]) < float(k2["low"])
        )
        if ok:
            return DS05Signal(
                side=-1,
                activate_idx=i,
                entry_price=min(float(k3["open"]), float(k2["low"])),
                initial_stop=float(k2["high"]),
                pattern="DS05 Bearish Finger",
                k1=k1_idx,
                k2=k2_idx,
                k3=k3_idx,
                active_extreme=active_high,
                camp_k1=camp_k1,
                camp_k2=camp_k2,
                camp_k3=camp_k3,
                signal_camp=signal_camp,
            )
    return None


def update_ds05_stop(position: dict, row: pd.Series) -> dict:
    if position["side"] == 1 and float(row["close"]) > float(row["open"]):
        position["stop"] = max(float(position["stop"]), float(row["low"]))
    elif position["side"] == -1 and float(row["close"]) < float(row["open"]):
        position["stop"] = min(float(position["stop"]), float(row["high"]))
    return position


def check_stop(row: pd.Series, position: dict) -> tuple[float | None, str | None]:
    side = int(position["side"])
    stop = float(position["stop"])
    if side == 1:
        if float(row["open"]) <= stop:
            return float(row["open"]), "gap_stop"
        if float(row["low"]) <= stop:
            return stop, "stop"
    elif side == -1:
        if float(row["open"]) >= stop:
            return float(row["open"]), "gap_stop"
        if float(row["high"]) >= stop:
            return stop, "stop"
    return None, None


def audit_ds05_camp_direction(trades: pd.DataFrame) -> pd.DataFrame:
    if trades.empty:
        return trades.copy()

    bad_long = (trades["direction"] == "long") & ~((trades["camp_k2"] == 1) & (trades["camp_k3"] == 1))
    bad_short = (trades["direction"] == "short") & ~((trades["camp_k2"] == -1) & (trades["camp_k3"] == -1))
    return trades[bad_long | bad_short].copy()

