"""行为测试：成交价与成本的现实性（跳空计价、funding 成本，均默认关闭）。

现状「触发价即成交价」会低估跳空滑点，「不计资金费」会高估长期持仓收益。
这两项默认保持原行为，需显式开启。
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta

import pytest

from fengji_futures_pending_order_monitor import resolve_fill_price
from fengji_pending_order_monitor import calc_position_pnl, funding_cost


def _args(**overrides) -> argparse.Namespace:
    base = dict(fill_price_mode="trigger", funding_rate_per_8h=0.0, fee_rate=0.0005, slippage_rate=0.0003, margin_per_trade=200.0, leverage=2.0)
    base.update(overrides)
    return argparse.Namespace(**base)


def test_trigger_mode_keeps_legacy_behaviour() -> None:
    """回归契约：默认 trigger 模式成交价就是触发价。"""
    order = {"trigger_price": 100.0, "side": "long"}
    bar = {"open": 105.0, "close": 106.0}
    assert resolve_fill_price(_args(), order, bar) == pytest.approx(100.0)


def test_gap_open_mode_uses_open_on_gap() -> None:
    order = {"trigger_price": 100.0, "side": "long"}
    # 多头：开盘已高于触发价 → 真实成交在开盘价
    assert resolve_fill_price(_args(fill_price_mode="gap_open"), order, {"open": 105.0, "close": 106.0}) == pytest.approx(105.0)

    short = {"trigger_price": 100.0, "side": "short"}
    assert resolve_fill_price(_args(fill_price_mode="gap_open"), short, {"open": 95.0, "close": 94.0}) == pytest.approx(95.0)


def test_gap_open_mode_no_gap_uses_trigger() -> None:
    order = {"trigger_price": 100.0, "side": "long"}
    assert resolve_fill_price(_args(fill_price_mode="gap_open"), order, {"open": 99.0, "close": 101.0}) == pytest.approx(100.0)


def test_gap_open_mode_falls_back_without_open() -> None:
    order = {"trigger_price": 100.0, "side": "long"}
    assert resolve_fill_price(_args(fill_price_mode="gap_open"), order, {"close": 101.0}) == pytest.approx(100.0)


def test_funding_cost_disabled_by_default() -> None:
    position = {"entry_time": (datetime.now() - timedelta(hours=24)).strftime("%Y-%m-%d %H:%M:%S")}
    assert funding_cost(position, 1000.0, _args()) == 0.0


def test_funding_cost_charges_per_8h_period() -> None:
    position = {"entry_time": (datetime.now() - timedelta(hours=24)).strftime("%Y-%m-%d %H:%M:%S")}
    # 24h = 3 期；1000 × 0.0001 × 3 = 0.3
    assert funding_cost(position, 1000.0, _args(funding_rate_per_8h=0.0001)) == pytest.approx(0.3, abs=0.02)


def test_funding_cost_without_entry_time_is_zero() -> None:
    assert funding_cost({}, 1000.0, _args(funding_rate_per_8h=0.0001)) == 0.0
    assert funding_cost({"entry_time": "bad-format"}, 1000.0, _args(funding_rate_per_8h=0.0001)) == 0.0


def test_pnl_deducts_funding_when_enabled() -> None:
    position = {
        "entry_price": 100.0,
        "side": 1,
        "margin": 200.0,
        "leverage": 2.0,
        "notional": 400.0,
        "entry_time": (datetime.now() - timedelta(hours=24)).strftime("%Y-%m-%d %H:%M:%S"),
    }
    plain = calc_position_pnl(position, 110.0, _args())
    with_funding = calc_position_pnl(position, 110.0, _args(funding_rate_per_8h=0.0001))
    assert plain["net_pnl"] > with_funding["net_pnl"]  # 计入 funding 后净利下降
    assert with_funding["funding"] > 0.0
    assert with_funding["net_pnl"] == pytest.approx(plain["net_pnl"] - with_funding["funding"])
