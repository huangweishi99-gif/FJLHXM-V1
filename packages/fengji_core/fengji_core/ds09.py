from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

import numpy as np
import pandas as pd


RED = 1
BLUE = -1


@dataclass(frozen=True)
class DS09Signal:
    side: int
    activate_idx: int
    entry_ref: float
    initial_stop: float
    pattern: str
    key: str
    session_date: Any
    mode: str
    d1_camp: int
    d1_boundary: float
    prev_open: float
    prev_close: float
    lock_idx: int
    attack_idx: int
    attack_price: float
    defense_idx: int
    defense_price: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_prev_day_boundary_map(d1_df: pd.DataFrame) -> dict[pd.Timestamp, dict[str, Any]]:
    if "camp" not in d1_df.columns:
        raise ValueError("DS09 requires D1 FengJi OS camp column before building boundaries.")
    d1 = d1_df.copy()
    d1["session_date"] = pd.to_datetime(d1["date"]).dt.normalize()
    d1 = d1.sort_values("session_date").reset_index(drop=True)
    d1["prev_open"] = d1["open"].shift(1)
    d1["prev_high"] = d1["high"].shift(1)
    d1["prev_low"] = d1["low"].shift(1)
    d1["prev_close"] = d1["close"].shift(1)
    d1["prev_camp"] = d1["camp"].shift(1)
    out: dict[pd.Timestamp, dict[str, Any]] = {}
    for _, row in d1.iterrows():
        if pd.isna(row["prev_open"]) or pd.isna(row["prev_close"]) or pd.isna(row["prev_camp"]):
            continue
        session_date = pd.to_datetime(row["session_date"]).normalize()
        prev_open = float(row["prev_open"])
        prev_close = float(row["prev_close"])
        prev_camp = int(row["prev_camp"])
        if prev_camp == RED and prev_close < prev_open:
            out[session_date] = {
                "mode": "LONG",
                "d1_camp": RED,
                "boundary": float(row["prev_high"]),
                "prev_open": prev_open,
                "prev_close": prev_close,
            }
        elif prev_camp == BLUE and prev_close > prev_open:
            out[session_date] = {
                "mode": "SHORT",
                "d1_camp": BLUE,
                "boundary": float(row["prev_low"]),
                "prev_open": prev_open,
                "prev_close": prev_close,
            }
    return out


def assign_session_date(m15_df: pd.DataFrame, d1_df: pd.DataFrame, *, futures: bool) -> pd.DataFrame:
    """Map M15 bars to D1 session_date. Crypto uses calendar day; futures use night-session roll."""
    if futures:
        return assign_cn_futures_session_date(m15_df, d1_df)
    out = m15_df.copy()
    out["session_date"] = pd.to_datetime(out["date"]).dt.normalize()
    valid = set(pd.to_datetime(d1_df["date"]).dt.normalize())
    out = out[out["session_date"].isin(valid)]
    return out.dropna(subset=["session_date"]).reset_index(drop=True)


def assign_cn_futures_session_date(m5_df: pd.DataFrame, d1_df: pd.DataFrame) -> pd.DataFrame:
    out = m5_df.copy()
    d1_dates = sorted(pd.to_datetime(d1_df["date"]).dt.normalize().drop_duplicates().tolist())
    d1_set = set(d1_dates)
    last = d1_dates[-1] if d1_dates else None

    def map_one(value: Any) -> pd.Timestamp | None:
        dt = pd.to_datetime(value)
        candidate = dt.normalize()
        if dt.hour >= 21:
            candidate = (dt + pd.Timedelta(days=1)).normalize()
        while candidate not in d1_set:
            candidate = (candidate + pd.Timedelta(days=1)).normalize()
            if last is not None and candidate > last:
                return None
        return candidate

    out["session_date"] = pd.to_datetime(out["date"]).apply(map_one)
    return out.dropna(subset=["session_date"]).reset_index(drop=True)


def make_ds09_signal(row: pd.Series, day_state: dict[str, Any], symbol: str = "") -> DS09Signal | None:
    if day_state.get("consumed", False):
        return None
    lock_idx = day_state.get("lock_idx")
    if lock_idx is None:
        return None

    i = int(row.name)
    open_ = float(row["open"])
    high = float(row["high"])
    low = float(row["low"])
    mode = str(day_state["mode"])

    if mode == "LONG":
        if int(row.get("camp", 0)) != RED:
            return None

        if day_state.get("attack_idx") is None:
            red_peak = row.get("red_peak_price", np.nan)
            red_peak_idx = row.get("red_peak_idx", np.nan)
            if pd.isna(red_peak) or pd.isna(red_peak_idx):
                return None
            if int(red_peak_idx) >= int(lock_idx):
                day_state["attack_idx"] = int(red_peak_idx)
                day_state["attack_price"] = float(red_peak)
            return None

        if day_state.get("defense_idx") is None:
            red_ext = row.get("red_ext_price", np.nan)
            red_ext_idx = row.get("red_ext_idx", np.nan)
            if pd.isna(red_ext) or pd.isna(red_ext_idx):
                return None
            if int(red_ext_idx) > int(day_state["attack_idx"]):
                day_state["defense_idx"] = int(red_ext_idx)
                day_state["defense_price"] = float(red_ext)
            return None

        red_peak = row.get("red_peak_price", np.nan)
        red_ext = row.get("red_ext_price", np.nan)
        red_peak_idx = row.get("red_peak_idx", np.nan)
        red_ext_idx = row.get("red_ext_idx", np.nan)
        if pd.isna(red_peak) or pd.isna(red_ext) or pd.isna(red_peak_idx) or pd.isna(red_ext_idx):
            return None
        if i <= int(day_state["defense_idx"]):
            return None
        attack_price = float(day_state["attack_price"])
        defense_price = float(day_state["defense_price"])
        if high > attack_price:
            entry_ref = attack_price
            if defense_price < max(open_, entry_ref):
                day_state["consumed"] = True
                session_date = row.get("session_date")
                key = f"{symbol}|DS09|LONG|{session_date}|{day_state['attack_idx']}|{attack_price:.10g}"
                return DS09Signal(
                    side=1,
                    activate_idx=i,
                    entry_ref=entry_ref,
                    initial_stop=defense_price,
                    pattern="DS09 V2.1 Long First Red Peak",
                    key=key,
                    session_date=session_date,
                    mode=mode,
                    d1_camp=int(day_state["d1_camp"]),
                    d1_boundary=float(day_state["boundary"]),
                    prev_open=float(day_state["prev_open"]),
                    prev_close=float(day_state["prev_close"]),
                    lock_idx=int(lock_idx),
                    attack_idx=int(day_state["attack_idx"]),
                    attack_price=attack_price,
                    defense_idx=int(day_state["defense_idx"]),
                    defense_price=defense_price,
                )

    if mode == "SHORT":
        if int(row.get("camp", 0)) != BLUE:
            return None

        if day_state.get("attack_idx") is None:
            blue_peak = row.get("blue_peak_price", np.nan)
            blue_peak_idx = row.get("blue_peak_idx", np.nan)
            if pd.isna(blue_peak) or pd.isna(blue_peak_idx):
                return None
            if int(blue_peak_idx) >= int(lock_idx):
                day_state["attack_idx"] = int(blue_peak_idx)
                day_state["attack_price"] = float(blue_peak)
            return None

        if day_state.get("defense_idx") is None:
            blue_ext = row.get("blue_ext_price", np.nan)
            blue_ext_idx = row.get("blue_ext_idx", np.nan)
            if pd.isna(blue_ext) or pd.isna(blue_ext_idx):
                return None
            if int(blue_ext_idx) > int(day_state["attack_idx"]):
                day_state["defense_idx"] = int(blue_ext_idx)
                day_state["defense_price"] = float(blue_ext)
            return None

        blue_peak = row.get("blue_peak_price", np.nan)
        blue_ext = row.get("blue_ext_price", np.nan)
        blue_peak_idx = row.get("blue_peak_idx", np.nan)
        blue_ext_idx = row.get("blue_ext_idx", np.nan)
        if pd.isna(blue_peak) or pd.isna(blue_ext) or pd.isna(blue_peak_idx) or pd.isna(blue_ext_idx):
            return None
        if i <= int(day_state["defense_idx"]):
            return None
        attack_price = float(day_state["attack_price"])
        defense_price = float(day_state["defense_price"])
        if low < attack_price:
            entry_ref = attack_price
            if defense_price > min(open_, entry_ref):
                day_state["consumed"] = True
                session_date = row.get("session_date")
                key = f"{symbol}|DS09|SHORT|{session_date}|{day_state['attack_idx']}|{attack_price:.10g}"
                return DS09Signal(
                    side=-1,
                    activate_idx=i,
                    entry_ref=entry_ref,
                    initial_stop=defense_price,
                    pattern="DS09 V2.1 Short First Blue Peak",
                    key=key,
                    session_date=session_date,
                    mode=mode,
                    d1_camp=int(day_state["d1_camp"]),
                    d1_boundary=float(day_state["boundary"]),
                    prev_open=float(day_state["prev_open"]),
                    prev_close=float(day_state["prev_close"]),
                    lock_idx=int(lock_idx),
                    attack_idx=int(day_state["attack_idx"]),
                    attack_price=attack_price,
                    defense_idx=int(day_state["defense_idx"]),
                    defense_price=defense_price,
                )
    return None


def entry_fill(row: pd.Series, signal: DS09Signal) -> float:
    if signal.side == 1:
        return max(float(row["open"]), float(signal.entry_ref))
    return min(float(row["open"]), float(signal.entry_ref))


def update_ds09_stop(position: dict, row: pd.Series) -> dict:
    side = int(position["side"])
    if side == 1 and not pd.isna(row.get("red_ext_price", np.nan)):
        position["stop"] = max(float(position["stop"]), float(row["red_ext_price"]))
    elif side == -1 and not pd.isna(row.get("blue_ext_price", np.nan)):
        position["stop"] = min(float(position["stop"]), float(row["blue_ext_price"]))
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


def audit_ds09_structure(trades: pd.DataFrame) -> pd.DataFrame:
    if trades.empty:
        return trades.copy()
    if "d1_camp" not in trades.columns:
        out = trades.copy()
        out["audit_reason"] = "missing_d1_camp"
        return out
    bad_long = (
        (trades["direction"] == "long")
        & (
            (trades["mode"] != "LONG")
            | (trades["d1_camp"] != RED)
            | (trades["prev_close"] >= trades["prev_open"])
            | (trades["entry_idx"] <= trades["defense_idx"])
            | (trades["attack_idx"] < trades["lock_idx"])
            | (trades["defense_idx"] <= trades["attack_idx"])
            | (trades["attack_price"] > trades["entry_price"])
            | (trades["defense_price"] >= trades["entry_price"])
        )
    )
    bad_short = (
        (trades["direction"] == "short")
        & (
            (trades["mode"] != "SHORT")
            | (trades["d1_camp"] != BLUE)
            | (trades["prev_close"] <= trades["prev_open"])
            | (trades["entry_idx"] <= trades["defense_idx"])
            | (trades["attack_idx"] < trades["lock_idx"])
            | (trades["defense_idx"] <= trades["attack_idx"])
            | (trades["attack_price"] < trades["entry_price"])
            | (trades["defense_price"] <= trades["entry_price"])
        )
    )
    duplicate_day = trades.duplicated(["session_date"], keep=False)
    duplicate_key = trades.duplicated("key", keep=False)
    return trades[bad_long | bad_short | duplicate_day | duplicate_key].copy()
