from __future__ import annotations

from pathlib import Path

import pandas as pd

from fengji_core.ds03_pending_fill import (
    find_missed_attack_bar_index,
    is_ds03_watch_setup_key,
    resolve_ds03_pending_fill_from_os_df,
    watch_trigger_stale_vs_attack,
)


def _attack_os_frame(trigger: float = 100.0) -> pd.DataFrame:
    df = pd.DataFrame(
        {
            "date": pd.date_range("2026-05-01", periods=9, freq="D"),
            "open": [9.0] * 9,
            "high": [9.2] * 9,
            "low": [8.8] * 9,
            "close": [9.0] * 9,
            "camp": [1] * 9,
            "active_high": [trigger] * 9,
            "active_low": [8.0] * 9,
            "red_peak_idx": [1] * 9,
            "red_ext_idx": [3] * 9,
        }
    )
    df.loc[6, "high"] = trigger + 1.0
    df.loc[6, "open"] = trigger - 2.0
    return df


def test_ds03_attack_bar_fill_on_latest_bar() -> None:
    trigger = 100.0
    os_df = _attack_os_frame(trigger)
    for idx in range(8):
        os_df.loc[idx, "high"] = trigger - 1.0
    os_df.loc[8, "open"] = trigger - 2.0
    os_df.loc[8, "high"] = trigger + 1.0
    order = {
        "strategy_id": "DS03",
        "side": "long",
        "trigger_price": trigger,
        "stop_price": 90.0,
        "setup_key": "CJUSDT|DS03|LONG|watch|trigger=100",
    }
    ctx = resolve_ds03_pending_fill_from_os_df(order, "CJUSDT", os_df, live_price=999.0)
    assert ctx is not None
    assert not ctx.get("stale")
    assert ctx["fill_price"] == trigger
    assert ctx["price_source"] == "ds03_attack_bar"


def test_ds03_blocks_ticker_fill_after_missed_attack_bar() -> None:
    trigger = 75.778
    os_df = _attack_os_frame(trigger)
    os_df.loc[6, "high"] = trigger + 1.0
    extra = pd.DataFrame(
        {
            "date": pd.to_datetime(["2026-06-16", "2026-06-17"]),
            "open": [74.0, 74.0],
            "high": [75.0, 76.0],
            "low": [70.0, 67.0],
            "close": [74.0, 67.0],
            "camp": [1, 1],
            "active_high": [trigger, trigger],
            "active_low": [59.666, 59.666],
            "red_peak_idx": [1, 1],
            "red_ext_idx": [3, 3],
        }
    )
    os_df = pd.concat([os_df.iloc[:7], extra], ignore_index=True)

    order = {
        "strategy_id": "DS03",
        "side": "long",
        "trigger_price": trigger,
        "stop_price": 59.666,
        "setup_key": f"HYPEUSDT|DS03|LONG|watch|trigger={trigger}",
    }
    ctx = resolve_ds03_pending_fill_from_os_df(order, "HYPEUSDT", os_df, live_price=76.0)
    assert ctx is not None
    assert ctx.get("stale") is True
    assert ctx.get("reason") == "ds03_attack_bar_missed"


def test_is_ds03_watch_setup_key() -> None:
    assert is_ds03_watch_setup_key("HYPEUSDT|DS03|LONG|watch|trigger=75.778")
    assert not is_ds03_watch_setup_key("HYPEUSDT|DS03|1|true_peak|idx=210|px=75.778")


def test_find_missed_attack_bar_on_prior_bar() -> None:
    os_df = _attack_os_frame(10.0)
    order = {
        "side": "long",
        "trigger_price": 10.0,
        "setup_key": "TESTUSDT|DS03|LONG|watch|trigger=10",
    }
    missed = find_missed_attack_bar_index(os_df, order, "TESTUSDT")
    assert missed == 6


def test_watch_trigger_stale_blocks_intraday_fill(monkeypatch) -> None:
    os_df = _attack_os_frame(4333.0)
    order = {
        "strategy_id": "DS03",
        "side": "short",
        "trigger_price": 4152.0,
        "stop_price": 4321.0,
        "setup_key": "EGUSDT|DS03|SHORT|watch|trigger=4152",
    }

    class _Attack:
        side = -1
        entry_ref = 4333.0

    monkeypatch.setattr(
        "fengji_core.ds03_pending_fill.resolve_ds03_attack",
        lambda _df, _i: _Attack(),
    )
    stale = watch_trigger_stale_vs_attack(os_df, order)
    assert stale is not None
    assert stale.get("reason") == "ds03_watch_trigger_stale"

    ctx = resolve_ds03_pending_fill_from_os_df(order, "EGUSDT", os_df, live_price=4140.0)
    assert ctx is not None
    assert ctx.get("stale") is True
    assert ctx.get("reason") == "ds03_watch_trigger_stale"


def patch_ds03_os_frame(monkeypatch, os_df) -> None:
    from fengji_core.ds03_pending_fill import resolve_ds03_pending_fill_from_os_df

    def _fake(order, symbol, data_dir, os_state_dir, live_price=None, gap=3):
        return resolve_ds03_pending_fill_from_os_df(order, symbol, os_df, live_price=live_price)

    monkeypatch.setattr("fengji_core.ds03_pending_fill.resolve_ds03_pending_fill", _fake)
    monkeypatch.setattr("fengji_pending_order_monitor.resolve_ds03_pending_fill", _fake)
