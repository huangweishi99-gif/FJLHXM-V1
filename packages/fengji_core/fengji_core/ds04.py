from __future__ import annotations

from dataclasses import asdict, dataclass

import pandas as pd


@dataclass(frozen=True)
class DS04Signal:
    side: int
    activate_idx: int
    initial_stop: float
    pattern: str
    k1: int
    k2: int
    k3: int
    reclaim_price: float
    k3_camp: int

    def to_dict(self) -> dict[str, int | float | str]:
        return asdict(self)


def candle_body(row: pd.Series) -> float:
    return abs(float(row["close"]) - float(row["open"]))


def candle_range(row: pd.Series) -> float:
    return float(row["high"]) - float(row["low"])


def no_price_gap(df: pd.DataFrame, left_idx: int, right_idx: int) -> bool:
    left = df.iloc[left_idx]
    right = df.iloc[right_idx]
    return not (float(right["low"]) > float(left["high"]) or float(right["high"]) < float(left["low"]))


def k2_is_weakest(df: pd.DataFrame, k1: int, k2: int, k3: int) -> bool:
    r1 = df.iloc[k1]
    r2 = df.iloc[k2]
    r3 = df.iloc[k3]
    body_ok = candle_body(r2) < candle_body(r1) and candle_body(r2) < candle_body(r3)
    range_ok = candle_range(r2) <= candle_range(r1) and candle_range(r2) <= candle_range(r3)
    return body_ok and range_ok


def make_ds04_signal(df: pd.DataFrame, k3_idx: int) -> DS04Signal | None:
    """DS04 夹棍/隔山炮: K1/K2/K3 reclaim, entry at K4 open."""
    if k3_idx < 3 or k3_idx + 1 >= len(df):
        return None

    k1_idx = k3_idx - 2
    k2_idx = k3_idx - 1
    k3_idx = k3_idx
    if not (
        no_price_gap(df, k1_idx - 1, k1_idx)
        and no_price_gap(df, k1_idx, k2_idx)
        and no_price_gap(df, k2_idx, k3_idx)
    ):
        return None
    if not k2_is_weakest(df, k1_idx, k2_idx, k3_idx):
        return None

    k1 = df.iloc[k1_idx]
    k2 = df.iloc[k2_idx]
    k3 = df.iloc[k3_idx]
    k1_yang = float(k1["close"]) > float(k1["open"])
    k1_yin = float(k1["close"]) < float(k1["open"])
    k2_yang = float(k2["close"]) > float(k2["open"])
    k2_yin = float(k2["close"]) < float(k2["open"])
    k3_yang = float(k3["close"]) > float(k3["open"])
    k3_yin = float(k3["close"]) < float(k3["open"])
    k3_camp = int(k3.get("camp", 0))

    if k1_yang and k2_yin and k3_yang and float(k3["close"]) > float(k1["high"]):
        return DS04Signal(
            side=1,
            activate_idx=k3_idx + 1,
            initial_stop=float(df["low"].iloc[k1_idx : k3_idx + 1].min()),
            pattern="DS04 Long Yang-Yin-Yang Reclaim",
            k1=k1_idx,
            k2=k2_idx,
            k3=k3_idx,
            reclaim_price=float(k1["high"]),
            k3_camp=k3_camp,
        )

    if k1_yin and k2_yang and k3_yin and float(k3["close"]) < float(k1["low"]):
        return DS04Signal(
            side=-1,
            activate_idx=k3_idx + 1,
            initial_stop=float(df["high"].iloc[k1_idx : k3_idx + 1].max()),
            pattern="DS04 Short Yin-Yang-Yin Reclaim",
            k1=k1_idx,
            k2=k2_idx,
            k3=k3_idx,
            reclaim_price=float(k1["low"]),
            k3_camp=k3_camp,
        )

    return None


def update_ds04_stop(position: dict, os_state: pd.Series) -> dict:
    side = int(position["side"])
    current_stop = float(position["stop"])
    if side == 1:
        red_ext = os_state.get("red_ext_price")
        if red_ext is not None and not pd.isna(red_ext) and float(red_ext) > current_stop:
            position["stop"] = float(red_ext)
            position["stop_source"] = "UPGRADED_RED_EXT"
    elif side == -1:
        blue_ext = os_state.get("blue_ext_price")
        if blue_ext is not None and not pd.isna(blue_ext) and float(blue_ext) < current_stop:
            position["stop"] = float(blue_ext)
            position["stop_source"] = "UPGRADED_BLUE_EXT"
    return position


def check_stop(row: pd.Series, position: dict) -> tuple[float | None, str | None]:
    side = int(position["side"])
    stop = float(position["stop"])
    source = str(position.get("stop_source", "INITIAL_3K"))
    if side == 1:
        if float(row["open"]) < stop:
            return float(row["open"]), f"DS04_LONG_BREAK_{source}_GAP"
        if float(row["low"]) < stop:
            return stop, f"DS04_LONG_BREAK_{source}"
    elif side == -1:
        if float(row["open"]) > stop:
            return float(row["open"]), f"DS04_SHORT_BREAK_{source}_GAP"
        if float(row["high"]) > stop:
            return stop, f"DS04_SHORT_BREAK_{source}"
    return None, None


def audit_ds04_structure(trades: pd.DataFrame) -> pd.DataFrame:
    if trades.empty:
        return trades.copy()
    required = ["k1", "k2", "k3", "reclaim_price", "initial_stop"]
    bad = pd.Series(False, index=trades.index)
    for column in required:
        bad = bad | trades[column].isna()
    return trades[bad].copy()
