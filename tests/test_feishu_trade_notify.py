from __future__ import annotations

from fengji_core.feishu_trade_notify import (
    format_close_done,
    format_fill_done,
    format_pending_expected,
    validate_close_fill,
    validate_expected_close,
    validate_pending_order,
)


def test_validate_pending_order_rejects_bad_stop_geometry() -> None:
    check = validate_pending_order(
        {
            "symbol": "BTCUSDT",
            "strategy_id": "DS01",
            "side": "long",
            "status": "ACTIVE",
            "trigger_price": 100.0,
            "stop_price": 101.0,
            "current_price": 99.0,
            "distance_pct": 0.01,
        }
    )
    assert check.ok is False
    assert any("几何" in issue for issue in check.issues)


def test_format_pending_expected_has_clear_title() -> None:
    msg = format_pending_expected(
        {
            "symbol": "BNBUSDT",
            "strategy_id": "DS01",
            "timeframe": "D1",
            "side": "long",
            "trigger_price": 584.43,
            "stop_price": 559.68,
            "current_price": 580.0,
            "distance_pct": 0.007,
            "os_camp": "red",
            "setup": "test",
            "valid_until": "2026-06-30 00:00:00",
        },
        symbol_label="BNB(BNBUSDT)",
        now="2026-06-23 12:00:00",
    )
    assert "【已挂单 · 预计挂单买入价格】" in msg
    assert "消息类型: 已挂单 + 预计挂单买入价格" in msg
    assert "状态: 已挂单" in msg
    assert "预计挂单买入价格: 584.43" in msg
    assert "峰极阵营: D1=red" in msg


def test_format_fill_done_has_bought_status_for_long() -> None:
    msg = format_fill_done(
        {
            "symbol": "BTCUSDT",
            "strategy_id": "DS01",
            "timeframe": "D1",
            "side": "long",
            "trigger_price": 100.0,
            "stop_price": 95.0,
            "setup": "test",
        },
        100.0,
        symbol_label="BTC(BTCUSDT)",
        now="2026-06-23 12:00:00",
    )
    assert "【已买入 · 挂单买入价格已成交】" in msg
    assert "消息类型: 已买入 + 挂单买入价格已成交" in msg
    assert "状态: 已买入" in msg


def test_format_fill_done_has_clear_title_for_short() -> None:
    msg = format_fill_done(
        {
            "symbol": "ETHUSDT",
            "strategy_id": "DS03",
            "timeframe": "D1",
            "side": "short",
            "trigger_price": 2500.0,
            "stop_price": 2600.0,
            "os_camp": "blue",
            "setup": "test",
        },
        2498.0,
        symbol_label="ETH(ETHUSDT)",
        now="2026-06-23 12:00:00",
    )
    assert "【已卖出 · 挂单卖出价格已成交】" in msg
    assert "消息类型: 已卖出 + 挂单卖出价格已成交" in msg
    assert "状态: 已卖出" in msg
    assert "预计挂单卖出价格: 2500" in msg
    assert "挂单卖出价格已成交: 2498" in msg


def test_format_fill_done_merges_expected_close() -> None:
    position = {
        "strategy_id": "DS01",
        "side": 1,
        "entry_time": "2026-06-23 10:00:00",
        "entry_price": 100.0,
        "initial_stop": 95.0,
        "current_stop": 95.0,
    }
    msg = format_fill_done(
        {
            "symbol": "BTCUSDT",
            "strategy_id": "DS01",
            "timeframe": "D1",
            "side": "long",
            "trigger_price": 100.0,
            "stop_price": 95.0,
            "setup": "test",
        },
        100.0,
        symbol_label="BTC(BTCUSDT)",
        now="2026-06-23 12:00:00",
        position=position,
    )
    assert "含预计平仓" in msg
    assert "预计挂单平仓价格: 95" in msg
    assert "消息类型: 已买入 + 挂单买入价格已成交 + 预计挂单平仓价格" in msg


def test_validate_expected_close_and_close_fill() -> None:
    position = {
        "strategy_id": "DS01",
        "side": 1,
        "entry_time": "2026-06-23 10:00:00",
        "entry_price": 100.0,
        "initial_stop": 95.0,
        "current_stop": 95.0,
    }
    assert validate_expected_close(position).ok is True
    assert validate_close_fill(position, 95.0, exit_reason="stop").ok is True

    close_msg = format_close_done(
        position,
        95.0,
        {"net_pnl": 120.0, "unit": "USDT"},
        symbol_label="TEST(TESTUSDT)",
        now="2026-06-23 13:00:00",
    )
    assert "【已卖出平仓 · 平仓价格已成交】" in close_msg
    assert "消息类型: 已卖出平仓 + 平仓价格已成交" in close_msg
    assert "状态: 已卖出平仓" in close_msg
    assert "预计挂单平仓价格: 95" in close_msg
    assert "平仓价格已成交: 95" in close_msg
