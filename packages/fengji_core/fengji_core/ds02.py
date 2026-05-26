from __future__ import annotations

from dataclasses import asdict, dataclass

import pandas as pd


@dataclass(frozen=True)
class DS02Signal:
    side: int
    activate_idx: int
    initial_stop: float
    pattern: str
    k1: int
    k2: int
    camp_k1: int
    camp_k2: int
    signal_camp: int

    def to_dict(self) -> dict[str, int | float | str]:
        return asdict(self)


def make_ds02_signal(df: pd.DataFrame, i: int) -> DS02Signal | None:
    """DS02 阴阳相吃: signal after K2 close, entry at next bar open."""
    if i < 1 or i + 1 >= len(df):
        return None

    k1_idx, k2_idx = i - 1, i
    k1 = df.iloc[k1_idx]
    k2 = df.iloc[k2_idx]
    camp_k1 = int(k1["camp"])
    camp_k2 = int(k2["camp"])
    if camp_k1 != camp_k2 or camp_k2 not in {1, -1}:
        return None

    k1_yin = float(k1["close"]) < float(k1["open"])
    k1_yang = float(k1["close"]) > float(k1["open"])
    k2_yang = float(k2["close"]) > float(k2["open"])
    k2_yin = float(k2["close"]) < float(k2["open"])

    if camp_k2 == 1 and k1_yin and k2_yang and float(k2["close"]) > float(k1["high"]):
        return DS02Signal(
            side=1,
            activate_idx=i + 1,
            initial_stop=min(float(k1["low"]), float(k2["low"])),
            pattern="DS02 Red Yang-Eats-Yin",
            k1=k1_idx,
            k2=k2_idx,
            camp_k1=camp_k1,
            camp_k2=camp_k2,
            signal_camp=camp_k2,
        )

    if camp_k2 == -1 and k1_yang and k2_yin and float(k2["close"]) < float(k1["low"]):
        return DS02Signal(
            side=-1,
            activate_idx=i + 1,
            initial_stop=max(float(k1["high"]), float(k2["high"])),
            pattern="DS02 Blue Yin-Eats-Yang",
            k1=k1_idx,
            k2=k2_idx,
            camp_k1=camp_k1,
            camp_k2=camp_k2,
            signal_camp=camp_k2,
        )

    return None


def update_ds02_stop(position: dict, row: pd.Series) -> dict:
    if int(position["side"]) == 1 and float(row["close"]) > float(row["open"]):
        position["stop"] = max(float(position["stop"]), float(row["low"]))
    elif int(position["side"]) == -1 and float(row["close"]) < float(row["open"]):
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


def audit_ds02_camp_direction(trades: pd.DataFrame) -> pd.DataFrame:
    if trades.empty:
        return trades.copy()
    bad_long = (trades["direction"] == "long") & ~((trades["camp_k1"] == 1) & (trades["camp_k2"] == 1))
    bad_short = (trades["direction"] == "short") & ~((trades["camp_k1"] == -1) & (trades["camp_k2"] == -1))
    return trades[bad_long | bad_short].copy()
