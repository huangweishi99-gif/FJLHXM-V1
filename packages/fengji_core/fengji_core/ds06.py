from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

import pandas as pd

from fengji_core.os_engine import RawNode, TurnEvent


@dataclass(frozen=True)
class DS06Signal:
    side: int
    activate_idx: int
    entry_ref: float
    initial_stop: float
    pattern: str
    signal_camp: int
    turn_idx: int
    turn_type: str
    old_extreme_price: float
    d_idx: int
    d_confirm_idx: int
    d_price: float
    e_idx: int
    e_confirm_idx: int
    e_price: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _node_key(node: RawNode) -> tuple[int, int, str, float]:
    return (node.point_idx, node.confirm_idx, node.raw_type, float(node.price))


def _turns_by_idx(turns: list[TurnEvent]) -> dict[int, TurnEvent]:
    return {int(turn.idx): turn for turn in turns}


def _new_hardened_nodes_at(hardened_by_bar: list[list[RawNode]], i: int) -> list[RawNode]:
    current = hardened_by_bar[i] if i < len(hardened_by_bar) else []
    previous = hardened_by_bar[i - 1] if i > 0 and i - 1 < len(hardened_by_bar) else []
    previous_keys = {_node_key(node) for node in previous}
    nodes = [node for node in current if _node_key(node) not in previous_keys and node.confirm_idx == i]
    return sorted(nodes, key=lambda node: (node.point_idx, node.confirm_idx, node.raw_type))


def _make_long_signal(df: pd.DataFrame, i: int, active: dict[str, Any]) -> DS06Signal:
    d_node: RawNode = active["d_node"]
    e_node: RawNode = active["e_node"]
    return DS06Signal(
        side=1,
        activate_idx=i,
        entry_ref=float(d_node.price),
        initial_stop=float(df["low"].iloc[i - 1 : i + 1].min()),
        pattern="DS06 Blue-to-Red External Peak",
        signal_camp=1,
        turn_idx=int(active["turn"].idx),
        turn_type=str(active["turn"].turn),
        old_extreme_price=float(active["turn"].broken_price),
        d_idx=int(d_node.point_idx),
        d_confirm_idx=int(d_node.confirm_idx),
        d_price=float(d_node.price),
        e_idx=int(e_node.point_idx),
        e_confirm_idx=int(e_node.confirm_idx),
        e_price=float(e_node.price),
    )


def _make_short_signal(df: pd.DataFrame, i: int, active: dict[str, Any]) -> DS06Signal:
    d_node: RawNode = active["d_node"]
    e_node: RawNode = active["e_node"]
    return DS06Signal(
        side=-1,
        activate_idx=i,
        entry_ref=float(d_node.price),
        initial_stop=float(df["high"].iloc[i - 1 : i + 1].max()),
        pattern="DS06 Red-to-Blue External Peak",
        signal_camp=-1,
        turn_idx=int(active["turn"].idx),
        turn_type=str(active["turn"].turn),
        old_extreme_price=float(active["turn"].broken_price),
        d_idx=int(d_node.point_idx),
        d_confirm_idx=int(d_node.confirm_idx),
        d_price=float(d_node.price),
        e_idx=int(e_node.point_idx),
        e_confirm_idx=int(e_node.confirm_idx),
        e_price=float(e_node.price),
    )


def detect_ds06_signals(df: pd.DataFrame, turns: list[TurnEvent], hardened_by_bar: list[list[RawNode]]) -> list[DS06Signal]:
    """Detect DS06 strict revolution signals on the current FengJi OS physical line.

    DS06 does not enter on the old defense break. It waits for the new-camp
    attack node D/d, then the new-camp defense node E/e, then the first external
    break of D/d after E/e is confirmed.
    """
    turns_by_idx = _turns_by_idx(turns)
    active: dict[str, Any] | None = None
    signals: list[DS06Signal] = []

    for i in range(len(df)):
        if i in turns_by_idx:
            turn = turns_by_idx[i]
            if turn.turn == "BLUE_TO_RED":
                active = {"mode": "LONG", "state": "WAIT_D", "turn": turn}
            elif turn.turn == "RED_TO_BLUE":
                active = {"mode": "SHORT", "state": "WAIT_D", "turn": turn}
            else:
                active = None

        if active is None:
            continue

        mode = active["mode"]
        state = active["state"]
        row = df.iloc[i]

        if mode == "LONG" and state == "WAIT_E":
            d_node: RawNode = active["d_node"]
            if i > d_node.confirm_idx and float(row["high"]) > float(d_node.price):
                active = {"mode": mode, "state": "WAIT_D", "turn": active["turn"]}
                state = "WAIT_D"

        if mode == "SHORT" and state == "WAIT_E":
            d_node = active["d_node"]
            if i > d_node.confirm_idx and float(row["low"]) < float(d_node.price):
                active = {"mode": mode, "state": "WAIT_D", "turn": active["turn"]}
                state = "WAIT_D"

        for node in _new_hardened_nodes_at(hardened_by_bar, i):
            turn: TurnEvent = active["turn"]

            if mode == "LONG" and active["state"] == "WAIT_D":
                if node.raw_type == "HIGH" and node.point_idx > turn.idx and node.confirm_idx > turn.idx:
                    active["d_node"] = node
                    active["state"] = "WAIT_E"
                continue

            if mode == "SHORT" and active["state"] == "WAIT_D":
                if node.raw_type == "LOW" and node.point_idx > turn.idx and node.confirm_idx > turn.idx:
                    active["d_node"] = node
                    active["state"] = "WAIT_E"
                continue

            if mode == "LONG" and active["state"] == "WAIT_E":
                d_node = active["d_node"]
                if (
                    node.raw_type == "LOW"
                    and node.point_idx > d_node.point_idx
                    and node.point_idx > d_node.confirm_idx
                    and float(d_node.price) > float(node.price)
                ):
                    active["e_node"] = node
                    active["state"] = "WAIT_F"
                continue

            if mode == "SHORT" and active["state"] == "WAIT_E":
                d_node = active["d_node"]
                if (
                    node.raw_type == "HIGH"
                    and node.point_idx > d_node.point_idx
                    and node.point_idx > d_node.confirm_idx
                    and float(d_node.price) < float(node.price)
                ):
                    active["e_node"] = node
                    active["state"] = "WAIT_F"
                continue

        if active is None or active["state"] != "WAIT_F":
            continue

        d_node = active["d_node"]
        e_node = active["e_node"]
        if mode == "LONG" and i > e_node.confirm_idx and float(row["high"]) > float(d_node.price):
            signals.append(_make_long_signal(df, i, active))
            active = None
        elif mode == "SHORT" and i > e_node.confirm_idx and float(row["low"]) < float(d_node.price):
            signals.append(_make_short_signal(df, i, active))
            active = None

    return signals


def entry_fill(row: pd.Series, signal: DS06Signal) -> float:
    if signal.side == 1:
        return max(float(row["open"]), float(signal.entry_ref))
    return min(float(row["open"]), float(signal.entry_ref))


def update_ds06_stop(position: dict, df: pd.DataFrame, i: int) -> dict:
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


def audit_ds06_structure(trades: pd.DataFrame) -> pd.DataFrame:
    if trades.empty:
        return trades.copy()

    long_bad = (
        (trades["direction"] == "long")
        & (
            (trades["turn_type"] != "BLUE_TO_RED")
            | (trades["signal_camp"] != 1)
            | (trades["d_price"] <= trades["e_price"])
        )
    )
    short_bad = (
        (trades["direction"] == "short")
        & (
            (trades["turn_type"] != "RED_TO_BLUE")
            | (trades["signal_camp"] != -1)
            | (trades["d_price"] >= trades["e_price"])
        )
    )
    order_bad = ~(
        (trades["turn_idx"] < trades["d_idx"])
        & (trades["d_idx"] < trades["e_idx"])
        & (trades["e_idx"] < trades["entry_idx"])
        & (trades["d_confirm_idx"] < trades["e_idx"])
        & (trades["e_confirm_idx"] < trades["entry_idx"])
    )
    return trades[long_bad | short_bad | order_bad].copy()
