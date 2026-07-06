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
    peak_key: str
    trigger_source: str

    def to_dict(self) -> dict[str, int | float | str]:
        return asdict(self)


@dataclass(frozen=True)
class DS03Attack:
    side: int
    entry_ref: float
    ref_idx: int
    pattern: str
    trigger_source: str

    @property
    def peak_key(self) -> str:
        return make_peak_trade_key(self.side, self.ref_idx, self.entry_ref, self.trigger_source)


def make_peak_trade_key(side: int, ref_idx: int, entry_ref: float, trigger_source: str) -> str:
    """One peak identity -> at most one DS03 entry (filled or consumed)."""
    return f"DS03|{side}|{trigger_source}|idx={ref_idx}|px={entry_ref:.10g}"


def ds03_order_setup_key(symbol: str, peak_key: str) -> str:
    return f"{symbol.strip().upper()}|{peak_key}"


def _num(row: pd.Series, column: str) -> float:
    if column not in row.index or pd.isna(row[column]):
        return np.nan
    return float(row[column])


def _idx(row: pd.Series, column: str) -> int | None:
    if column not in row.index or pd.isna(row[column]):
        return None
    return int(row[column])


def _first_pierce_long(df: pd.DataFrame, i: int, level: float) -> bool:
    row = df.iloc[i]
    if float(row["high"]) <= level:
        return False
    if i <= 0:
        return True
    return float(df.iloc[i - 1]["high"]) <= level


def _first_pierce_short(df: pd.DataFrame, i: int, level: float) -> bool:
    row = df.iloc[i]
    if float(row["low"]) >= level:
        return False
    if i <= 0:
        return True
    return float(df.iloc[i - 1]["low"]) >= level


def resolve_ds03_attack(df: pd.DataFrame, i: int) -> DS03Attack | None:
    """DS03 二四棒：阵营内只破「峰」推进；真峰=active_high/low，假峰=OS 硬化 FAILED（a/f 点）。

    - 真峰：刺破上一根可见 active 峰，且为本峰第一次刺破（启动棍）。
    - 假峰：未刺破真峰、已抬升防守极后，第一次刺破假峰（启动棍）；破极仍属转势，不得开仓。
    """
    if i < 1:
        return None

    row = df.iloc[i]
    prev = df.iloc[i - 1]
    prev_camp = int(prev["camp"])
    cur_camp = int(row["camp"])

    prev_active_high = _num(prev, "active_high")
    prev_active_low = _num(prev, "active_low")

    if prev_camp == 1 and not np.isnan(prev_active_high) and not np.isnan(prev_active_low):
        if float(row["high"]) > prev_active_high and _first_pierce_long(df, i, prev_active_high):
            return DS03Attack(
                side=1,
                entry_ref=prev_active_high,
                ref_idx=_idx(prev, "red_peak_idx") or i - 1,
                pattern="DS03 Red Break True Peak Shou2-Shou4",
                trigger_source="true_peak",
            )

    if prev_camp == -1 and not np.isnan(prev_active_low) and not np.isnan(prev_active_high):
        if float(row["low"]) < prev_active_low and _first_pierce_short(df, i, prev_active_low):
            return DS03Attack(
                side=-1,
                entry_ref=prev_active_low,
                ref_idx=_idx(prev, "blue_peak_idx") or i - 1,
                pattern="DS03 Blue Break True Peak Shou2-Shou4",
                trigger_source="true_peak",
            )

    if prev_camp == 1 and cur_camp == 1 and not np.isnan(prev_active_high):
        fake_idx = _idx(row, "last_failed_high_idx")
        defense_idx = _idx(row, "red_ext_idx")
        fake_price = _num(row, "last_failed_high_price")
        if (
            fake_idx is not None
            and defense_idx is not None
            and defense_idx > fake_idx
            and not np.isnan(fake_price)
            and float(row["high"]) > fake_price
            and float(row["high"]) <= prev_active_high
            and _first_pierce_long(df, i, fake_price)
        ):
            return DS03Attack(
                side=1,
                entry_ref=fake_price,
                ref_idx=fake_idx,
                pattern="DS03 Red Break Fake Peak Shou2-Shou4",
                trigger_source="fake_peak",
            )

    if prev_camp == -1 and cur_camp == -1 and not np.isnan(prev_active_low):
        fake_idx = _idx(row, "last_failed_low_idx")
        defense_idx = _idx(row, "blue_ext_idx")
        fake_price = _num(row, "last_failed_low_price")
        if (
            fake_idx is not None
            and defense_idx is not None
            and defense_idx > fake_idx
            and not np.isnan(fake_price)
            and float(row["low"]) < fake_price
            and float(row["low"]) >= prev_active_low
            and _first_pierce_short(df, i, fake_price)
        ):
            return DS03Attack(
                side=-1,
                entry_ref=fake_price,
                ref_idx=fake_idx,
                pattern="DS03 Blue Break Fake Peak Shou2-Shou4",
                trigger_source="fake_peak",
            )

    return None


def make_ds03_signal(df: pd.DataFrame, i: int, consumed_peak_keys: set[str] | None = None) -> DS03Signal | None:
    """DS03 二四棒: in-camp peak break; each peak_key may fire at most once."""
    attack = resolve_ds03_attack(df, i)
    if attack is None:
        return None
    if consumed_peak_keys is not None:
        if attack.peak_key in consumed_peak_keys:
            return None
        consumed_peak_keys.add(attack.peak_key)

    signal_camp = int(df.iloc[i - 1]["camp"])
    if attack.side == 1:
        initial_stop = float(df["low"].iloc[i - 1 : i + 1].min())
    else:
        initial_stop = float(df["high"].iloc[i - 1 : i + 1].max())
    return DS03Signal(
        side=attack.side,
        activate_idx=i,
        entry_ref=attack.entry_ref,
        initial_stop=initial_stop,
        pattern=attack.pattern,
        signal_camp=signal_camp,
        ref_idx=attack.ref_idx,
        peak_key=attack.peak_key,
        trigger_source=attack.trigger_source,
    )


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
