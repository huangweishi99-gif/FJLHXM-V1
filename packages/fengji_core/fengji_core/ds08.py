from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

import pandas as pd

from fengji_core.os_engine import RawNode


@dataclass(frozen=True)
class DS08Signal:
    side: int
    activate_idx: int
    entry_ref: float
    initial_stop: float
    pattern: str
    key: str
    n1_idx: int
    n1_price: float
    n1_type: str
    n2_idx: int
    n2_price: float
    n2_type: str
    n3_idx: int
    n3_price: float
    n3_type: str
    n4_idx: int
    n4_price: float
    n4_type: str
    n5_idx: int
    n5_confirm_idx: int
    n5_price: float
    n5_type: str
    attack_idx: int
    attack_price: float
    defense_idx: int
    defense_price: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def node_role(node: RawNode) -> str:
    return "P" if node.raw_type == "HIGH" else "V"


def _node_fields(prefix: str, node: RawNode) -> dict[str, Any]:
    return {
        f"{prefix}_idx": int(node.point_idx),
        f"{prefix}_price": float(node.price),
        f"{prefix}_type": node_role(node),
    }


def _make_signal(
    side: int,
    i: int,
    nodes: list[RawNode],
    entry_ref: float,
    initial_stop: float,
    pattern: str,
    key: str,
    attack_node: RawNode,
    defense_node: RawNode,
) -> DS08Signal:
    values: dict[str, Any] = {
        "side": side,
        "activate_idx": i,
        "entry_ref": entry_ref,
        "initial_stop": initial_stop,
        "pattern": pattern,
        "key": key,
        "n5_confirm_idx": int(nodes[4].confirm_idx),
        "attack_idx": int(attack_node.point_idx),
        "attack_price": float(attack_node.price),
        "defense_idx": int(defense_node.point_idx),
        "defense_price": float(defense_node.price),
    }
    for number, node in enumerate(nodes, start=1):
        values.update(_node_fields(f"n{number}", node))
    return DS08Signal(**values)


def make_ds08_signal(df: pd.DataFrame, i: int, skeleton: list[RawNode], used_keys: set[str], symbol: str = "") -> DS08Signal | None:
    if len(skeleton) < 5:
        return None

    nodes = sorted(skeleton[-5:], key=lambda node: (node.point_idx, node.confirm_idx))
    roles = [node_role(node) for node in nodes]
    row = df.iloc[i]
    open_ = float(row["open"])
    high = float(row["high"])
    low = float(row["low"])

    if roles == ["V", "P", "V", "P", "V"]:
        v1, p1, v2, p2, v3 = nodes
        if float(v3.price) > float(v2.price) > float(v1.price) and float(p2.price) > float(p1.price):
            key = f"{symbol}|LONG|{v3.point_idx}|{p2.point_idx}|{float(p2.price):.10g}"
            if key in used_keys or i <= int(v3.confirm_idx):
                return None

            wait_high = float(df["high"].iloc[int(v3.point_idx) : int(v3.confirm_idx) + 1].max())
            if wait_high > float(p2.price):
                used_keys.add(key)
                return None

            if int(v3.confirm_idx) + 1 <= i - 1:
                prev_high = float(df["high"].iloc[int(v3.confirm_idx) + 1 : i].max())
                if prev_high > float(p2.price):
                    used_keys.add(key)
                    return None

            if high > float(p2.price):
                entry_ref = float(p2.price)
                initial_stop = float(v3.price)
                if initial_stop < max(open_, entry_ref):
                    used_keys.add(key)
                    return _make_signal(1, i, nodes, entry_ref, initial_stop, "DS08 Long Power Seizure", key, p2, v3)

    if roles == ["P", "V", "P", "V", "P"]:
        p1, v1, p2, v2, p3 = nodes
        if float(p3.price) < float(p2.price) < float(p1.price) and float(v2.price) < float(v1.price):
            key = f"{symbol}|SHORT|{p3.point_idx}|{v2.point_idx}|{float(v2.price):.10g}"
            if key in used_keys or i <= int(p3.confirm_idx):
                return None

            wait_low = float(df["low"].iloc[int(p3.point_idx) : int(p3.confirm_idx) + 1].min())
            if wait_low < float(v2.price):
                used_keys.add(key)
                return None

            if int(p3.confirm_idx) + 1 <= i - 1:
                prev_low = float(df["low"].iloc[int(p3.confirm_idx) + 1 : i].min())
                if prev_low < float(v2.price):
                    used_keys.add(key)
                    return None

            if low < float(v2.price):
                entry_ref = float(v2.price)
                initial_stop = float(p3.price)
                if initial_stop > min(open_, entry_ref):
                    used_keys.add(key)
                    return _make_signal(-1, i, nodes, entry_ref, initial_stop, "DS08 Short Power Seizure", key, v2, p3)

    return None


def entry_fill(row: pd.Series, signal: DS08Signal) -> float:
    if signal.side == 1:
        return max(float(row["open"]), float(signal.entry_ref))
    return min(float(row["open"]), float(signal.entry_ref))


def update_ds08_stop(position: dict, skeleton: list[RawNode]) -> dict:
    if not skeleton:
        return position
    side = int(position["side"])
    if side == 1:
        lows = [node for node in skeleton if node.raw_type == "LOW"]
        if lows:
            position["stop"] = max(float(position["stop"]), float(lows[-1].price))
    elif side == -1:
        highs = [node for node in skeleton if node.raw_type == "HIGH"]
        if highs:
            position["stop"] = min(float(position["stop"]), float(highs[-1].price))
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


def audit_ds08_structure(trades: pd.DataFrame) -> pd.DataFrame:
    if trades.empty:
        return trades.copy()

    long_roles = (
        (trades["n1_type"] == "V")
        & (trades["n2_type"] == "P")
        & (trades["n3_type"] == "V")
        & (trades["n4_type"] == "P")
        & (trades["n5_type"] == "V")
    )
    short_roles = (
        (trades["n1_type"] == "P")
        & (trades["n2_type"] == "V")
        & (trades["n3_type"] == "P")
        & (trades["n4_type"] == "V")
        & (trades["n5_type"] == "P")
    )
    bad_long = (
        (trades["direction"] == "long")
        & (
            ~long_roles
            | ~(trades["n5_price"] > trades["n3_price"])
            | ~(trades["n3_price"] > trades["n1_price"])
            | ~(trades["n4_price"] > trades["n2_price"])
            | (trades["n5_confirm_idx"] >= trades["entry_idx"])
            | (trades["defense_price"] >= trades["entry_price"])
            | (trades["attack_price"] > trades["entry_price"])
        )
    )
    bad_short = (
        (trades["direction"] == "short")
        & (
            ~short_roles
            | ~(trades["n5_price"] < trades["n3_price"])
            | ~(trades["n3_price"] < trades["n1_price"])
            | ~(trades["n4_price"] < trades["n2_price"])
            | (trades["n5_confirm_idx"] >= trades["entry_idx"])
            | (trades["defense_price"] <= trades["entry_price"])
            | (trades["attack_price"] < trades["entry_price"])
        )
    )
    duplicate_key = trades.duplicated("key", keep=False)
    return trades[bad_long | bad_short | duplicate_key].copy()
