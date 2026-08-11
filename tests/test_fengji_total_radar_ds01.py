from __future__ import annotations

from types import SimpleNamespace

import math
import pandas as pd

from fengji_total_radar import add_ds01


def _engine() -> SimpleNamespace:
    return SimpleNamespace(hardened_by_bar=[[], []])


def test_ds01_long_blocks_when_red_defense_missing() -> None:
    d1 = pd.DataFrame(
        [
            {
                "date": "2026-06-06",
                "open": 572.17,
                "high": 584.43,
                "low": 559.68,
                "close": 574.53,
                "camp": 1,
                "active_low": math.nan,
            },
            {
                "date": "2026-06-07",
                "open": 574.54,
                "high": 610.54,
                "low": 573.60,
                "close": 604.44,
                "camp": 1,
                "active_low": math.nan,
            },
        ]
    )
    rows = []

    add_ds01(rows, "BNBUSDT", d1, _engine(), current=604.44)

    assert len(rows) == 1
    assert rows[0].strategy_id == "DS01"
    assert rows[0].side == "long"
    assert rows[0].status == "BLOCKED_OS_INCOMPLETE"
    assert "missing_red_ext" in rows[0].reason


def test_ds01_long_does_not_use_current_bar_defense_retroactively() -> None:
    d1 = pd.DataFrame(
        [
            {
                "date": "2026-06-07",
                "open": 574.54,
                "high": 610.54,
                "low": 573.60,
                "close": 604.44,
                "camp": 1,
                "active_low": math.nan,
            },
            {
                "date": "2026-06-08",
                "open": 604.44,
                "high": 612.0,
                "low": 599.0,
                "close": 601.91,
                "camp": 1,
                "active_low": 556.46,
            },
        ]
    )
    rows = []

    add_ds01(rows, "BNBUSDT", d1, _engine(), current=601.91)

    assert len(rows) == 1
    assert rows[0].strategy_id == "DS01"
    assert rows[0].side == "long"
    assert rows[0].status == "BLOCKED_OS_INCOMPLETE"
    assert "missing_red_ext" in rows[0].reason


def test_ds01_short_blocks_when_blue_defense_missing() -> None:
    d1 = pd.DataFrame(
        [
            {
                "date": "2026-06-06",
                "open": 100.0,
                "high": 105.0,
                "low": 95.0,
                "close": 98.0,
                "camp": -1,
                "active_high": math.nan,
            },
            {
                "date": "2026-06-07",
                "open": 98.0,
                "high": 99.0,
                "low": 94.0,
                "close": 95.0,
                "camp": -1,
                "active_high": math.nan,
            },
        ]
    )
    rows = []

    add_ds01(rows, "TESTUSDT", d1, _engine(), current=95.0)

    assert len(rows) == 1
    assert rows[0].strategy_id == "DS01"
    assert rows[0].side == "short"
    assert rows[0].status == "BLOCKED_OS_INCOMPLETE"
    assert "missing_blue_ext" in rows[0].reason


def test_ds01_long_allows_when_red_defense_present() -> None:
    d1 = pd.DataFrame(
        [
            {
                "date": "2026-06-06",
                "open": 100.0,
                "high": 105.0,
                "low": 95.0,
                "close": 104.0,
                "camp": 1,
                "active_low": 95.0,
            },
            {
                "date": "2026-06-07",
                "open": 104.0,
                "high": 106.0,
                "low": 103.0,
                "close": 105.0,
                "camp": 1,
                "active_low": 95.0,
            },
        ]
    )
    rows = []

    add_ds01(rows, "TESTUSDT", d1, _engine(), current=105.0)

    assert len(rows) == 1
    assert rows[0].status == "TRIGGERED"
    assert "missing_red_ext" not in rows[0].reason
