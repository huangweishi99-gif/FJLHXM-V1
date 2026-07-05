from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

import numpy as np
import pandas as pd

from fengji_core.ds03 import resolve_ds03_attack


@dataclass(frozen=True)
class DS07Signal:
    side: int
    activate_idx: int
    entry_ref: float
    initial_stop: float
    pattern: str
    trigger_type: str
    d1_camp: int
    prev_h1_camp: int
    h1_camp: int
    attack_idx: int
    attack_price: float
    defense_idx: int
    defense_price: float
    attack_key: str
    session_date: Any

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def prepare_datetime_ohlcv(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    out.columns = [column.strip().lower() for column in out.columns]
    column_map = {
        "时间": "datetime",
        "日期": "date",
        "开盘": "open",
        "最高": "high",
        "最低": "low",
        "收盘": "close",
        "成交量": "volume",
        "成交额": "amount",
        "持仓量": "hold",
    }
    out = out.rename(columns={column: column_map.get(column, column) for column in out.columns})
    required = ["open", "high", "low", "close", "volume"]
    if any(column not in out.columns for column in required) and len(out.columns) >= 6:
        positional = {out.columns[0]: "datetime", out.columns[1]: "open", out.columns[2]: "high", out.columns[3]: "low", out.columns[4]: "close", out.columns[5]: "volume"}
        out = out.rename(columns=positional)
    if "datetime" in out.columns and "date" not in out.columns:
        out["date"] = pd.to_datetime(out["datetime"], errors="raise")
    elif "timestamp" in out.columns and "date" not in out.columns:
        out["date"] = pd.to_datetime(out["timestamp"], errors="raise")
    elif "date" in out.columns:
        out["date"] = pd.to_datetime(out["date"], errors="raise")
    else:
        raise ValueError("CSV must contain date or datetime column.")
    missing = [column for column in required if column not in out.columns]
    if missing:
        raise ValueError(f"CSV is missing required columns: {', '.join(missing)}")
    out[required] = out[required].apply(pd.to_numeric, errors="raise")
    out = out.sort_values("date").drop_duplicates("date").reset_index(drop=True)
    return out[["date", "open", "high", "low", "close", "volume"]].dropna(subset=required)


def add_atr(frame: pd.DataFrame, window: int = 14) -> pd.DataFrame:
    out = frame.copy()
    prev_close = out["close"].shift(1)
    ranges = pd.concat(
        [
            out["high"] - out["low"],
            (out["high"] - prev_close).abs(),
            (out["low"] - prev_close).abs(),
        ],
        axis=1,
    )
    out["tr"] = ranges.max(axis=1)
    out["atr"] = out["tr"].rolling(window).mean()
    return out


def attach_os_detail(df: pd.DataFrame, engine) -> pd.DataFrame:
    os_log = engine.export_os_log().set_index("idx")
    out = engine.to_frame(df).copy()
    detail_columns = [
        "red_peak_idx",
        "red_peak_price",
        "red_ext_idx",
        "red_ext_price",
        "blue_peak_idx",
        "blue_peak_price",
        "blue_ext_idx",
        "blue_ext_price",
        "last_failed_high_idx",
        "last_failed_high_price",
        "last_failed_low_idx",
        "last_failed_low_price",
    ]
    for column in detail_columns:
        if column in os_log:
            out[column] = os_log[column].values
    hardened_by_bar = getattr(engine, "hardened_by_bar", [])
    if len(hardened_by_bar) >= len(out):
        out["hardened_count"] = [len(nodes) for nodes in hardened_by_bar[: len(out)]]
    else:
        out["hardened_count"] = len(getattr(engine, "hardened_nodes", []))
    return out


def _session_date_for_future(timestamp: pd.Timestamp, d1_dates: list[pd.Timestamp]) -> pd.Timestamp | None:
    dt = pd.to_datetime(timestamp)
    candidate = dt.normalize()
    if dt.hour >= 21:
        candidate = (dt + pd.Timedelta(days=1)).normalize()
    d1_set = set(d1_dates)
    last = d1_dates[-1] if d1_dates else None
    while candidate not in d1_set:
        candidate = (candidate + pd.Timedelta(days=1)).normalize()
        if last is not None and candidate > last:
            return None
    return candidate


def map_d1_to_h1_future(d1_os: pd.DataFrame, h1_os: pd.DataFrame) -> pd.DataFrame:
    d1 = d1_os.copy()
    h1 = h1_os.copy()
    d1["session_date"] = pd.to_datetime(d1["date"]).dt.normalize()
    d1_dates = sorted(d1["session_date"].drop_duplicates().tolist())
    h1["session_date"] = pd.to_datetime(h1["date"]).apply(lambda value: _session_date_for_future(value, d1_dates))

    camp_col = "camp_confirmed" if "camp_confirmed" in d1.columns else "camp"
    d1_ref = d1[["session_date", camp_col]].copy()
    d1_ref["d1_camp"] = d1_ref[camp_col].shift(1).fillna(0).astype(int)
    camp_map = dict(zip(d1_ref["session_date"], d1_ref["d1_camp"]))
    h1["d1_camp"] = h1["session_date"].map(camp_map).fillna(0).astype(int)
    return h1.dropna(subset=["session_date"]).reset_index(drop=True)


def map_d1_to_h1_natural_day(d1_os: pd.DataFrame, h1_os: pd.DataFrame) -> pd.DataFrame:
    d1 = d1_os.copy()
    h1 = h1_os.copy()
    d1["session_date"] = pd.to_datetime(d1["date"]).dt.normalize()
    h1["session_date"] = pd.to_datetime(h1["date"]).dt.normalize()
    camp_col = "camp_confirmed" if "camp_confirmed" in d1.columns else "camp"
    d1_ref = d1[["session_date", camp_col]].copy()
    d1_ref["d1_camp"] = d1_ref[camp_col].shift(1).fillna(0).astype(int)
    camp_map = dict(zip(d1_ref["session_date"], d1_ref["d1_camp"]))
    h1["d1_camp"] = h1["session_date"].map(camp_map).fillna(0).astype(int)
    return h1.reset_index(drop=True)


def _valid_price(value: Any) -> bool:
    return value is not None and not pd.isna(value)


def _valid_idx(value: Any) -> bool:
    return value is not None and not pd.isna(value) and int(value) >= 0


def _has_n_structure(row: pd.Series) -> bool:
    return int(row.get("hardened_count", 0) or 0) >= 4


def _line_value(row: pd.Series, name: str) -> float:
    return float(row.get(name, np.nan))


def _line_idx(row: pd.Series, name: str) -> int:
    return int(row.get(name, -1))


def _make_signal(
    *,
    side: int,
    activate_idx: int,
    d1_camp: int,
    prev_h1_camp: int,
    h1_camp: int,
    entry_ref: float,
    initial_stop: float,
    attack_idx: int,
    defense_idx: int,
    attack_key: str,
    trigger_type: str,
    pattern: str,
    session_date: Any,
) -> DS07Signal | None:
    if attack_idx < 0 or defense_idx < 0 or attack_key == "":
        return None
    if side == 1 and initial_stop >= entry_ref:
        return None
    if side == -1 and initial_stop <= entry_ref:
        return None
    return DS07Signal(
        side=side,
        activate_idx=activate_idx,
        entry_ref=entry_ref,
        initial_stop=initial_stop,
        pattern=pattern,
        trigger_type=trigger_type,
        d1_camp=d1_camp,
        prev_h1_camp=prev_h1_camp,
        h1_camp=h1_camp,
        attack_idx=attack_idx,
        attack_price=entry_ref,
        defense_idx=defense_idx,
        defense_price=initial_stop,
        attack_key=attack_key,
        session_date=session_date,
    )


def _confirmed_camp(row: pd.Series) -> int:
    if "camp_confirmed" in row.index and not pd.isna(row.get("camp_confirmed")):
        return int(row["camp_confirmed"])
    return int(row.get("camp", 0))


def make_ds07_signal(
    row: pd.Series,
    i: int,
    used_attack_keys: set[str],
    symbol: str = "",
    prev_row: pd.Series | None = None,
    df: pd.DataFrame | None = None,
) -> DS07Signal | None:
    """DS07 共振决战：D1 camp_confirmed 战略授权 + H1 DS03 二四棒同向触发。

    与 DS01、DS02 无关；不满足双周期同向或 H1 未过 DS03 二四棒则不开仓。
    """
    if i < 1 or prev_row is None or df is None:
        return None

    ds03 = resolve_ds03_attack(df, i)
    if ds03 is None:
        return None

    d1_camp = int(row.get("d1_camp", 0))
    h1_camp = _confirmed_camp(row)
    prev_h1_camp = _confirmed_camp(prev_row)
    open_price = float(row["open"])

    if d1_camp == 1 and ds03.side == 1:
        red_ext = prev_row.get("red_ext_price", np.nan)
        red_ext_idx = prev_row.get("red_ext_idx", np.nan)
        if (
            prev_h1_camp == 1
            and h1_camp == 1
            and _has_n_structure(prev_row)
            and _valid_price(red_ext)
            and _valid_idx(red_ext_idx)
        ):
            attack_idx = int(ds03.ref_idx)
            defense_idx = int(red_ext_idx)
            entry_ref = float(ds03.entry_ref)
            initial_stop = float(red_ext)
            entry_price = max(open_price, entry_ref)
            attack_key = f"{symbol}|LONG_CONTINUE|{ds03.peak_key}"
            if attack_key not in used_attack_keys and initial_stop < entry_price:
                return _make_signal(
                    side=1,
                    activate_idx=i,
                    d1_camp=d1_camp,
                    prev_h1_camp=prev_h1_camp,
                    h1_camp=h1_camp,
                    entry_ref=entry_ref,
                    initial_stop=initial_stop,
                    attack_idx=attack_idx,
                    defense_idx=defense_idx,
                    attack_key=attack_key,
                    trigger_type="LONG_CONTINUE",
                    pattern=f"DS07 D1 Red + H1 Red DS03 | {ds03.pattern}",
                    session_date=row.get("session_date"),
                )

    if d1_camp == -1 and ds03.side == -1:
        blue_ext = prev_row.get("blue_ext_price", np.nan)
        blue_ext_idx = prev_row.get("blue_ext_idx", np.nan)
        if (
            prev_h1_camp == -1
            and h1_camp == -1
            and _has_n_structure(prev_row)
            and _valid_price(blue_ext)
            and _valid_idx(blue_ext_idx)
        ):
            attack_idx = int(ds03.ref_idx)
            defense_idx = int(blue_ext_idx)
            entry_ref = float(ds03.entry_ref)
            initial_stop = float(blue_ext)
            entry_price = min(open_price, entry_ref)
            attack_key = f"{symbol}|SHORT_CONTINUE|{ds03.peak_key}"
            if attack_key not in used_attack_keys and initial_stop > entry_price:
                return _make_signal(
                    side=-1,
                    activate_idx=i,
                    d1_camp=d1_camp,
                    prev_h1_camp=prev_h1_camp,
                    h1_camp=h1_camp,
                    entry_ref=entry_ref,
                    initial_stop=initial_stop,
                    attack_idx=attack_idx,
                    defense_idx=defense_idx,
                    attack_key=attack_key,
                    trigger_type="SHORT_CONTINUE",
                    pattern=f"DS07 D1 Blue + H1 Blue DS03 | {ds03.pattern}",
                    session_date=row.get("session_date"),
                )

    return None


def entry_fill(row: pd.Series, signal: DS07Signal) -> float:
    if signal.side == 1:
        return max(float(row["open"]), float(signal.entry_ref))
    return min(float(row["open"]), float(signal.entry_ref))


def update_ds07_stop(position: dict, row: pd.Series) -> dict:
    side = int(position["side"])
    if side == 1 and _valid_price(row.get("red_ext_price")):
        position["stop"] = max(float(position["stop"]), float(row["red_ext_price"]))
    elif side == -1 and _valid_price(row.get("blue_ext_price")):
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


def audit_ds07_structure(trades: pd.DataFrame) -> pd.DataFrame:
    if trades.empty:
        return trades.copy()

    trigger = trades["trigger_type"] if "trigger_type" in trades else pd.Series("", index=trades.index)
    prev_h1 = trades["prev_h1_camp"] if "prev_h1_camp" in trades else trades["h1_camp"]
    bad_long = (
        (trades["direction"] == "long")
        & (
            (trades["d1_camp"] != 1)
            | (trades["h1_camp"] != 1)
            | ((trigger == "LONG_CONTINUE") & (prev_h1 != 1))
            | (trades["attack_price"] > trades["entry_price"])
            | (trades["defense_price"] >= trades["entry_price"])
        )
    )
    bad_short = (
        (trades["direction"] == "short")
        & (
            (trades["d1_camp"] != -1)
            | (trades["h1_camp"] != -1)
            | ((trigger == "SHORT_CONTINUE") & (prev_h1 != -1))
            | (trades["attack_price"] < trades["entry_price"])
            | (trades["defense_price"] <= trades["entry_price"])
        )
    )
    bad_trigger = ~trigger.isin({"LONG_CONTINUE", "SHORT_CONTINUE"})
    duplicate_attack = trades.duplicated("attack_key", keep=False)
    return trades[bad_long | bad_short | bad_trigger | duplicate_attack].copy()
