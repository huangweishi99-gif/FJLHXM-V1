from __future__ import annotations

from dataclasses import asdict, dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class DS03Signal:
    side: int
    activate_idx: int
    entry_ref: float
    initial_stop: float
    pattern: str
    signal_camp: int
    ref_idx: int

    def to_dict(self) -> dict[str, int | float | str]:
        return asdict(self)


def make_ds03_signal(df: pd.DataFrame, i: int) -> DS03Signal | None:
    """DS03 二四棒: in-camp peak/level break, using prior visible OS state."""
    if i < 7:
        return None

    row = df.iloc[i]
    prev = df.iloc[i - 1]
    prev_camp = int(prev["camp"])
    prev_active_high = float(prev["active_high"]) if not pd.isna(prev["active_high"]) else np.nan
    prev_active_low = float(prev["active_low"]) if not pd.isna(prev["active_low"]) else np.nan

    if prev_camp == 1 and not np.isnan(prev_active_high) and float(row["high"]) > prev_active_high:
        return DS03Signal(
            side=1,
            activate_idx=i,
            entry_ref=prev_active_high,
            initial_stop=float(df["low"].iloc[i - 1 : i + 1].min()),
            pattern="DS03 Red Break Peak Shou2-Shou4",
            signal_camp=prev_camp,
            ref_idx=i - 1,
        )

    if prev_camp == -1 and not np.isnan(prev_active_low) and float(row["low"]) < prev_active_low:
        return DS03Signal(
            side=-1,
            activate_idx=i,
            entry_ref=prev_active_low,
            initial_stop=float(df["high"].iloc[i - 1 : i + 1].max()),
            pattern="DS03 Blue Break Peak Shou2-Shou4",
            signal_camp=prev_camp,
            ref_idx=i - 1,
        )

    return None


def entry_fill(row: pd.Series, signal: DS03Signal) -> float:
    if signal.side == 1:
        return max(float(row["open"]), float(signal.entry_ref))
    return min(float(row["open"]), float(signal.entry_ref))


def update_ds03_stop(position: dict, df: pd.DataFrame, i: int) -> dict:
    side = int(position["side"])
    start = max(0, i - 3)
    if side == 1:
        dynamic_stop = float(df["low"].iloc[start : i + 1].min())
        position["stop"] = max(float(position["stop"]), dynamic_stop)
    elif side == -1:
        dynamic_stop = float(df["high"].iloc[start : i + 1].max())
        position["stop"] = min(float(position["stop"]), dynamic_stop)
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


def audit_ds03_camp_direction(trades: pd.DataFrame) -> pd.DataFrame:
    if trades.empty:
        return trades.copy()
    bad_long = (trades["direction"] == "long") & (trades["signal_camp"] != 1)
    bad_short = (trades["direction"] == "short") & (trades["signal_camp"] != -1)
    bad_ref = trades["entry_ref"].isna()
    return trades[bad_long | bad_short | bad_ref].copy()
