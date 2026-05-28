from __future__ import annotations

from types import SimpleNamespace

import pandas as pd

from fengji_total_radar import add_ds08


def node(point_idx: int, confirm_idx: int, raw_type: str, price: float) -> SimpleNamespace:
    return SimpleNamespace(point_idx=point_idx, confirm_idx=confirm_idx, raw_type=raw_type, price=price)


def engine_with_nodes(nodes: list[SimpleNamespace], length: int = 7) -> SimpleNamespace:
    hardened_by_bar = [[] for _ in range(length)]
    hardened_by_bar[-1] = nodes
    return SimpleNamespace(hardened_by_bar=hardened_by_bar)


def frame(highs: list[float] | None = None, lows: list[float] | None = None, latest_open: float = 13.0) -> pd.DataFrame:
    highs = highs or [10.4, 15.0, 11.4, 16.0, 12.4, 15.8, 15.9]
    lows = lows or [9.8, 10.8, 10.6, 11.0, 11.7, 11.9, 12.2]
    opens = [10.0, 12.0, 11.0, 14.0, 12.0, 13.0, latest_open]
    closes = [10.2, 14.0, 11.2, 15.0, 12.2, 14.0, 14.5]
    return pd.DataFrame(
        [
            {"date": f"2026-05-26 {i:02d}:00:00", "open": opens[i], "high": highs[i], "low": lows[i], "close": closes[i], "camp": 1}
            for i in range(7)
        ]
    )


def long_nodes(v3_price: float = 12.0) -> list[SimpleNamespace]:
    return [
        node(0, 0, "LOW", 10.0),
        node(1, 1, "HIGH", 15.0),
        node(2, 2, "LOW", 11.0),
        node(3, 3, "HIGH", 16.0),
        node(4, 5, "LOW", v3_price),
    ]


def short_nodes(p3_price: float = 17.0) -> list[SimpleNamespace]:
    return [
        node(0, 0, "HIGH", 20.0),
        node(1, 1, "LOW", 15.0),
        node(2, 2, "HIGH", 18.0),
        node(3, 3, "LOW", 14.0),
        node(4, 5, "HIGH", p3_price),
    ]


def test_ds08_long_pending_after_v3_confirm_before_first_break() -> None:
    rows = []

    add_ds08(rows, "RENDERUSDT", frame(), engine_with_nodes(long_nodes()), current=15.9)

    assert len(rows) == 1
    assert rows[0].strategy_id == "DS08"
    assert rows[0].side == "long"
    assert rows[0].status == "PENDING"
    assert rows[0].trigger_price == 16.0
    assert rows[0].stop_price == 12.0
    assert "key=RENDERUSDT|LONG|4|3|16" in rows[0].reason


def test_ds08_long_equal_trigger_is_not_started_yet() -> None:
    rows = []
    df = frame(highs=[10.4, 15.0, 11.4, 16.0, 12.4, 15.8, 16.0])

    add_ds08(rows, "RENDERUSDT", df, engine_with_nodes(long_nodes()), current=16.0)

    assert len(rows) == 1
    assert rows[0].status == "PENDING"


def test_ds08_long_invalidated_if_wait_window_already_broke_p2() -> None:
    rows = []
    df = frame(highs=[10.4, 15.0, 11.4, 16.0, 16.2, 15.8, 15.9])

    add_ds08(rows, "RENDERUSDT", df, engine_with_nodes(long_nodes()), current=15.9)

    assert len(rows) == 1
    assert rows[0].status == "INVALIDATED"
    assert "wait_high_gt_trigger" in rows[0].reason


def test_ds08_long_invalidated_if_stop_is_not_below_entry_reference() -> None:
    rows = []

    add_ds08(rows, "RENDERUSDT", frame(), engine_with_nodes(long_nodes(v3_price=16.5)), current=15.9)

    assert len(rows) == 1
    assert rows[0].status == "INVALIDATED"
    assert "invalid_stop" in rows[0].reason


def test_ds08_short_pending_after_p3_confirm_before_first_break() -> None:
    rows = []
    df = frame(
        highs=[20.0, 19.0, 18.0, 17.0, 17.0, 16.8, 16.6],
        lows=[19.0, 15.0, 16.0, 14.0, 14.5, 14.2, 14.1],
        latest_open=16.0,
    )

    add_ds08(rows, "BTCUSDT", df, engine_with_nodes(short_nodes()), current=14.1)

    assert len(rows) == 1
    assert rows[0].side == "short"
    assert rows[0].status == "PENDING"
    assert rows[0].trigger_price == 14.0
    assert rows[0].stop_price == 17.0
    assert "key=BTCUSDT|SHORT|4|3|14" in rows[0].reason


def test_ds08_short_invalidated_if_wait_window_already_broke_v2() -> None:
    rows = []
    df = frame(
        highs=[20.0, 19.0, 18.0, 17.0, 17.0, 16.8, 16.6],
        lows=[19.0, 15.0, 16.0, 14.0, 13.8, 14.2, 14.1],
        latest_open=16.0,
    )

    add_ds08(rows, "BTCUSDT", df, engine_with_nodes(short_nodes()), current=14.1)

    assert len(rows) == 1
    assert rows[0].status == "INVALIDATED"
    assert "wait_low_lt_trigger" in rows[0].reason
