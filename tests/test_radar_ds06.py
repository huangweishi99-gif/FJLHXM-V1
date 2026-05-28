from __future__ import annotations

from types import SimpleNamespace

import pandas as pd

from fengji_total_radar import add_ds06, latest_ds06_setup


def node(point_idx: int, confirm_idx: int, raw_type: str, price: float) -> SimpleNamespace:
    return SimpleNamespace(point_idx=point_idx, confirm_idx=confirm_idx, raw_type=raw_type, price=price)


def engine_with_long_de() -> SimpleNamespace:
    d = node(2, 3, "HIGH", 10.0)
    e = node(4, 5, "LOW", 8.0)
    hardened_by_bar = [
        [],
        [],
        [],
        [d],
        [d],
        [d, e],
        [d, e],
        [d, e],
    ]
    turn = SimpleNamespace(idx=1, turn="BLUE_TO_RED")
    return SimpleNamespace(turns=[turn], hardened_by_bar=hardened_by_bar)


def frame(latest_high: float) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"date": "2026-05-19", "open": 9.0, "high": 9.5, "low": 8.9, "close": 9.2},
            {"date": "2026-05-20", "open": 9.2, "high": 9.6, "low": 9.0, "close": 9.4},
            {"date": "2026-05-21", "open": 9.4, "high": 10.0, "low": 9.1, "close": 9.8},
            {"date": "2026-05-22", "open": 9.8, "high": 9.9, "low": 9.2, "close": 9.4},
            {"date": "2026-05-23", "open": 9.4, "high": 9.6, "low": 8.0, "close": 8.8},
            {"date": "2026-05-24", "open": 8.8, "high": 9.0, "low": 8.4, "close": 8.7},
            {"date": "2026-05-25", "open": 8.7, "high": 9.3, "low": 8.7, "close": 9.0},
            {"date": "2026-05-26", "open": 9.0, "high": latest_high, "low": 8.9, "close": 9.2},
        ]
    )


def test_ds06_pending_stop_uses_last_two_bar_low_not_e_point() -> None:
    setup = latest_ds06_setup(frame(latest_high=9.8), engine_with_long_de())

    assert setup is not None
    assert setup["status"] == "PENDING"
    assert setup["trigger"] == 10.0
    assert setup["stop"] == 8.7


def test_ds06_triggered_stop_uses_last_two_bar_low_not_e_point() -> None:
    setup = latest_ds06_setup(frame(latest_high=10.2), engine_with_long_de())

    assert setup is not None
    assert setup["status"] == "TRIGGERED"
    assert setup["trigger"] == 10.0
    assert setup["stop"] == 8.7


def test_ds06_radar_carries_structure_setup_key() -> None:
    rows = []

    add_ds06(rows, "RENDERUSDT", frame(latest_high=9.8), engine_with_long_de(), current=9.2)

    assert len(rows) == 1
    assert rows[0].setup_key == "RENDERUSDT|DS06|LONG|d=2|e=4|trigger=10"
