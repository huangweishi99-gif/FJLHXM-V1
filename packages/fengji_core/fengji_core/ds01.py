from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from fengji_core.os_engine import RawNode


@dataclass(frozen=True)
class DS01PendingOrder:
    side: int
    signal_idx: int
    trigger_idx: int
    trigger_price: float
    stop_price: float
    is_add: bool
    left_count: int = 0


def build_lines_from_hardened(nodes: list[RawNode]) -> list[tuple[RawNode, RawNode]]:
    ordered = sorted(nodes, key=lambda node: (node.point_idx, node.confirm_idx))
    return [(a, b) for a, b in zip(ordered[:-1], ordered[1:]) if a.point_idx != b.point_idx]


def count_left_lines(
    hardened_nodes: list[RawNode],
    i: int,
    price: float,
    lookback: int = 30,
) -> int:
    """Count how many FengJi line segments are crossed by the current horizontal price."""
    left = max(0, i - lookback)
    count = 0
    for a, b in build_lines_from_hardened(hardened_nodes):
        if a.point_idx < left or b.point_idx >= i:
            continue
        if min(a.price, b.price) <= price <= max(a.price, b.price):
            count += 1
    return count


def make_ds01_pending(
    df: pd.DataFrame,
    i: int,
    camp: int,
    position: dict | None,
    max_adds: int = 3,
    left_count: int = 0,
) -> DS01PendingOrder | None:
    """DS01 挫棍 setup: same-direction candle creates next-bar trigger."""
    row = df.iloc[i]
    is_bull = float(row["close"]) > float(row["open"])
    is_bear = float(row["close"]) < float(row["open"])

    if position is None:
        is_add = False
    else:
        if int(position.get("adds", 0)) >= max_adds:
            return None
        is_add = True

    if camp == 1 and is_bull:
        return DS01PendingOrder(
            side=1,
            signal_idx=i,
            trigger_idx=i + 1,
            trigger_price=float(row["high"]),
            stop_price=float(row["low"]),
            is_add=is_add,
            left_count=left_count,
        )
    if camp == -1 and is_bear:
        return DS01PendingOrder(
            side=-1,
            signal_idx=i,
            trigger_idx=i + 1,
            trigger_price=float(row["low"]),
            stop_price=float(row["high"]),
            is_add=is_add,
            left_count=left_count,
        )
    return None


def ds01_left_filter_pass(
    hardened_nodes: list[RawNode],
    bar_idx: int,
    price: float,
    is_add: bool,
    lookback: int = 30,
    max_lines: int = 2,
) -> tuple[bool, int]:
    """首仓在当日突破/跌破触发价格位置检查左30线数；续棍不要求左30线数。"""
    left_count = count_left_lines(hardened_nodes, bar_idx, price, lookback)
    if is_add:
        return True, left_count
    return left_count <= max_lines, left_count


def entry_fill(row: pd.Series, side: int, trigger_price: float) -> float | None:
    if side == 1:
        if float(row["open"]) >= trigger_price:
            return float(row["open"])
        if float(row["high"]) >= trigger_price:
            return trigger_price
    elif side == -1:
        if float(row["open"]) <= trigger_price:
            return float(row["open"])
        if float(row["low"]) <= trigger_price:
            return trigger_price
    return None


def exit_fill(row: pd.Series, side: int, stop_price: float) -> float | None:
    if side == 1:
        if float(row["open"]) <= stop_price:
            return float(row["open"])
        if float(row["low"]) <= stop_price:
            return stop_price
    elif side == -1:
        if float(row["open"]) >= stop_price:
            return float(row["open"])
        if float(row["high"]) >= stop_price:
            return stop_price
    return None
