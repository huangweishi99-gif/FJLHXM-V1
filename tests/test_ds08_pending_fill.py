from __future__ import annotations

import pandas as pd

from fengji_core.ds08_pending_fill import check_ds08_setup_key_stale_from_os
from fengji_core.fill_supervision import parse_ds08_setup_key
from fengji_core.os_engine import RawNode


class _MockEngine:
    def __init__(self, hardened_by_bar: list[list[RawNode]]) -> None:
        self.hardened_by_bar = hardened_by_bar


def _short_skeleton() -> list[RawNode]:
    return [
        RawNode(point_idx=0, confirm_idx=0, price=0.0045, raw_type="HIGH"),
        RawNode(point_idx=1, confirm_idx=1, price=0.0044, raw_type="LOW"),
        RawNode(point_idx=2, confirm_idx=2, price=0.0045, raw_type="HIGH"),
        RawNode(point_idx=3, confirm_idx=3, price=0.00438, raw_type="LOW"),
        RawNode(point_idx=4, confirm_idx=4, price=0.00439, raw_type="HIGH"),
    ]


def test_check_ds08_setup_key_stale_detects_idx_drift() -> None:
    dates = pd.date_range("2026-06-20", periods=5, freq="h")
    os_df = pd.DataFrame(
        {
            "date": dates,
            "open": [0.0045] * 5,
            "high": [0.0046] * 5,
            "low": [0.0043] * 5,
            "close": [0.0044] * 5,
            "camp": [-1] * 5,
        }
    )
    nodes = _short_skeleton()
    engine = _MockEngine([[]] * 4 + [nodes])
    order = {
        "strategy_id": "DS08",
        "side": "short",
        "setup_key": "ATHUSDT|SHORT|3|2|0.004385",
        "latest_time": str(dates[-1]),
        "trigger_price": 0.004385,
    }
    stale = check_ds08_setup_key_stale_from_os(order, "ATHUSDT", os_df, engine)
    assert stale is not None
    assert stale.get("stale") is True
    assert stale.get("reason") in {"ds08_setup_key_stale", "ds08_setup_key_idx_stale"}


def test_check_ds08_setup_key_stale_ok_when_key_matches() -> None:
    dates = pd.date_range("2026-06-20", periods=5, freq="h")
    os_df = pd.DataFrame(
        {
            "date": dates,
            "open": [0.0045] * 5,
            "high": [0.0046] * 5,
            "low": [0.0043] * 5,
            "close": [0.0044] * 5,
            "camp": [-1] * 5,
        }
    )
    nodes = _short_skeleton()
    engine = _MockEngine([[]] * 4 + [nodes])
    order = {
        "strategy_id": "DS08",
        "side": "short",
        "setup_key": "ATHUSDT|SHORT|4|3|0.00438",
        "latest_time": str(dates[-1]),
        "trigger_price": 0.00438,
    }
    stale = check_ds08_setup_key_stale_from_os(order, "ATHUSDT", os_df, engine)
    assert stale is None


def test_parse_ds08_setup_key_short_format() -> None:
    parsed = parse_ds08_setup_key("ATHUSDT|SHORT|2395|2389|0.004385")
    assert parsed is not None
    assert parsed["side"] == -1
    assert parsed["defense_idx"] == 2395
    assert parsed["attack_idx"] == 2389


def test_load_ds08_h1_os_frame_uses_short_ttl_cache(tmp_path, monkeypatch) -> None:
    from fengji_core import ds08_pending_fill as mod

    mod._OS_FRAME_CACHE.clear()
    calls = {"n": 0}

    def fake_build(df, gap, state_path, attach, record_hardened_by_bar=True):
        calls["n"] += 1
        return df, _MockEngine([[]])

    def fake_norm(raw):
        out = raw.copy()
        out["date"] = pd.to_datetime(out["date"])
        return out

    monkeypatch.setattr(mod, "build_os_detail_frame_stateful", fake_build)
    monkeypatch.setattr(mod, "_normalize_ohlcv", fake_norm)
    data_dir = tmp_path / "data"
    h1 = data_dir / "1h"
    h1.mkdir(parents=True)
    (h1 / "ATHUSDT.csv").write_text(
        "date,open,high,low,close\n"
        "2026-06-20 00:00:00,1,2,0.5,1.5\n"
        "2026-06-20 01:00:00,1,2,0.5,1.5\n",
        encoding="utf-8",
    )
    mod.load_ds08_h1_os_frame("ATHUSDT", data_dir, None, gap=3)
    mod.load_ds08_h1_os_frame("ATHUSDT", data_dir, None, gap=3)
    assert calls["n"] == 1
    mod._OS_FRAME_CACHE.clear()


def _wld_short_skeleton() -> list[RawNode]:
    return [
        RawNode(point_idx=0, confirm_idx=0, price=0.55, raw_type="HIGH"),
        RawNode(point_idx=1, confirm_idx=1, price=0.501, raw_type="LOW"),
        RawNode(point_idx=2, confirm_idx=2, price=0.5398, raw_type="HIGH"),
        RawNode(point_idx=3, confirm_idx=3, price=0.4811, raw_type="LOW"),
        RawNode(point_idx=4, confirm_idx=5, price=0.5025, raw_type="HIGH"),
    ]


def test_resolve_ds08_pending_fill_uses_entry_fill_on_activation_bar() -> None:
    from fengji_core.ds08_pending_fill import resolve_ds08_pending_fill_from_os_df

    dates = pd.date_range("2026-06-26 00:00", periods=7, freq="h")
    os_df = pd.DataFrame(
        {
            "date": dates,
            "open": [0.50, 0.50, 0.50, 0.50, 0.50, 0.50, 0.4858],
            "high": [0.51, 0.51, 0.51, 0.51, 0.51, 0.51, 0.4861],
            "low": [0.49, 0.49, 0.49, 0.49, 0.49, 0.4821, 0.4720],
            "close": [0.50, 0.50, 0.50, 0.50, 0.50, 0.50, 0.4729],
            "camp": [-1] * 7,
        }
    )
    nodes = _wld_short_skeleton()
    engine = _MockEngine([[]] * 6 + [nodes])
    order = {
        "strategy_id": "DS08",
        "side": "short",
        "setup_key": "WLDUSDT|SHORT|4|3|0.4811",
        "trigger_price": 0.4811,
        "stop_price": 0.5025,
    }
    out = resolve_ds08_pending_fill_from_os_df(
        order,
        "WLDUSDT",
        os_df,
        engine,
        live_price=0.4753,
        max_lag_bars=1,
    )
    assert out is not None
    assert out.get("stale") is not True
    assert out["price_source"] == "ds08_entry_fill"
    assert out["fill_price"] == 0.4811
    assert out["activation_bar_idx"] == 6


def test_resolve_ds08_pending_fill_cancels_stale_activation() -> None:
    from fengji_core.ds08_pending_fill import resolve_ds08_pending_fill_from_os_df

    dates = pd.date_range("2026-06-26 00:00", periods=10, freq="h")
    lows = [0.49] * 10
    lows[6] = 0.4720
    os_df = pd.DataFrame(
        {
            "date": dates,
            "open": [0.50] * 10,
            "high": [0.51] * 10,
            "low": lows,
            "close": [0.50] * 10,
            "camp": [-1] * 10,
        }
    )
    nodes = _wld_short_skeleton()
    engine = _MockEngine([[]] * 6 + [nodes] + [nodes] * 3)
    order = {
        "strategy_id": "DS08",
        "side": "short",
        "setup_key": "WLDUSDT|SHORT|4|3|0.4811",
        "trigger_price": 0.4811,
        "stop_price": 0.5025,
    }
    out = resolve_ds08_pending_fill_from_os_df(
        order,
        "WLDUSDT",
        os_df,
        engine,
        live_price=0.4753,
        max_lag_bars=1,
    )
    assert out is not None
    assert out.get("stale") is True
    assert out.get("reason") == "ds08_activation_bar_missed"
