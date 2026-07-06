from __future__ import annotations

import pandas as pd

from fengji_core.ds01 import ds01_left_filter_pass, ds01_os_defense_missing, make_ds01_pending
from fengji_core.os_engine import RawNode


def node(point_idx: int, price: float, raw_type: str) -> RawNode:
    return RawNode(point_idx=point_idx, confirm_idx=point_idx + 3, price=price, raw_type=raw_type)


def test_ds01_left_wireless_checks_trigger_price_level() -> None:
    hardened = [
        node(0, 1.00, "LOW"),
        node(5, 1.05, "HIGH"),
        node(10, 1.02, "LOW"),
    ]

    left_ok, left_count = ds01_left_filter_pass(hardened, bar_idx=12, price=1.08, is_add=False)

    assert left_ok
    assert left_count == 0


def test_ds01_left_filter_allows_up_to_two_left_lines() -> None:
    hardened = [
        node(0, 1.00, "LOW"),
        node(5, 1.10, "HIGH"),
        node(10, 1.02, "LOW"),
    ]

    left_ok, left_count = ds01_left_filter_pass(hardened, bar_idx=12, price=1.05, is_add=False)

    assert left_ok
    assert left_count == 2


def test_ds01_left_filter_blocks_three_or_more_left_lines() -> None:
    hardened = [
        node(0, 1.00, "LOW"),
        node(3, 1.10, "HIGH"),
        node(6, 1.02, "LOW"),
        node(9, 1.08, "HIGH"),
    ]

    left_ok, left_count = ds01_left_filter_pass(hardened, bar_idx=12, price=1.05, is_add=False)

    assert not left_ok
    assert left_count == 3


def test_ds01_os_defense_missing_blocks_bare_red_and_blue() -> None:
    red_bare = pd.Series({"active_low": float("nan"), "active_high": 100.0})
    red_ok = pd.Series({"active_low": 95.0, "active_high": 100.0})
    blue_bare = pd.Series({"active_high": float("nan"), "active_low": 90.0})
    blue_ok = pd.Series({"active_high": 105.0, "active_low": 90.0})

    assert ds01_os_defense_missing(1, red_bare)
    assert not ds01_os_defense_missing(1, red_ok)
    assert ds01_os_defense_missing(-1, blue_bare)
    assert not ds01_os_defense_missing(-1, blue_ok)


def test_ds01_pending_carries_signal_day_left_count() -> None:
    df = pd.DataFrame(
        [
            {"open": 1.00, "high": 1.20, "low": 0.95, "close": 1.10},
            {"open": 1.11, "high": 1.21, "low": 1.05, "close": 1.18},
        ]
    )

    pending = make_ds01_pending(df, 0, camp=1, position=None, left_count=0)

    assert pending is not None
    assert pending.trigger_price == 1.20
    assert pending.left_count == 0
