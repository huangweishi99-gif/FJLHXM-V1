from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from fengji_futures_pending_order_monitor import process_once
from fengji_pending_orders import convert_radar_rows, write_orders


def radar_row(symbol: str, side: str = "long", trigger: float = 100.0, stop: float = 95.0) -> dict:
    current = trigger - 2 if side == "long" else trigger + 2
    return {
        "symbol": symbol,
        "strategy_id": "DS03",
        "timeframe": "D1",
        "side": side,
        "status": "PENDING",
        "setup": "test setup",
        "current_price": current,
        "trigger_price": trigger,
        "distance_pct": abs(trigger - current) / current,
        "stop_price": stop,
        "os_camp": "red" if side == "long" else "blue",
        "latest_time": "2026-05-26 00:00:00",
        "reason": "test",
        "setup_key": f"{symbol}|DS03|{side}|trigger={trigger}",
    }


def write_bar(data_dir: Path, symbol: str, high: float, low: float, close: float) -> None:
    path = data_dir / "15m" / f"{symbol}.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        [
            {
                "date": "2026-05-26 10:15:00",
                "open": close,
                "high": high,
                "low": low,
                "close": close,
                "volume": 1,
            }
        ]
    ).to_csv(path, index=False)


def make_args(tmp_path: Path, orders_json: Path, data_dir: Path) -> argparse.Namespace:
    return argparse.Namespace(
        orders_file=str(orders_json),
        out_dir=str(tmp_path / "pending"),
        state_file=str(tmp_path / "pending" / "futures_pending_state.json"),
        paper_state_file=str(tmp_path / "futures" / "state_futures_v2.json"),
        trade_csv=str(tmp_path / "futures" / "trades_futures_astock.csv"),
        data_dir=str(data_dir),
        price_timeframes="15m,1h,1d",
        feishu_webhook="",
        max_ds01_entries=3,
        max_open_positions_per_symbol=3,
        lots=1,
        fee_rate=0.0001,
        slippage_rate=0.0002,
        no_paper_state_update=False,
    )


def test_futures_pending_monitor_fills_from_local_bar_cross(tmp_path: Path) -> None:
    orders = convert_radar_rows(
        [radar_row("CJUSDT", side="long", trigger=100.0, stop=95.0)],
        include_strategies={"DS03"},
        include_triggered=False,
        max_distance_pct=0.08,
        created_at="2026-05-26 10:00:00",
    )
    out_dir = tmp_path / "pending"
    orders_json, _ = write_orders(orders, out_dir)
    data_dir = tmp_path / "data"
    write_bar(data_dir, "CJUSDT", high=101.0, low=98.0, close=100.5)
    args = make_args(tmp_path, orders_json, data_dir)
    state = {"version": 1, "filled_order_ids": [], "cancelled_order_ids": [], "fills": []}

    summary = process_once(args, state)
    saved = json.loads(Path(args.paper_state_file).read_text(encoding="utf-8"))
    position = saved["symbols"]["CJUSDT"]["open_positions"][0]

    assert summary["filled"] == 1
    assert position["source"] == "pending_order"
    assert position["entry_price"] == 100.0
    assert position["side"] == 1
    assert Path(args.trade_csv).exists()


def test_futures_pending_monitor_blocks_reverse_position(tmp_path: Path) -> None:
    orders = convert_radar_rows(
        [radar_row("CJUSDT", side="short", trigger=98.0, stop=101.0)],
        include_strategies={"DS03"},
        include_triggered=False,
        max_distance_pct=0.08,
        created_at="2026-05-26 10:00:00",
    )
    out_dir = tmp_path / "pending"
    orders_json, _ = write_orders(orders, out_dir)
    data_dir = tmp_path / "data"
    write_bar(data_dir, "CJUSDT", high=100.0, low=97.0, close=98.0)
    paper_state = tmp_path / "futures" / "state_futures_v2.json"
    paper_state.parent.mkdir(parents=True, exist_ok=True)
    paper_state.write_text(
        json.dumps({"symbols": {"CJUSDT": {"open_positions": [{"strategy_id": "DS01", "side": 1}]}}}),
        encoding="utf-8",
    )
    args = make_args(tmp_path, orders_json, data_dir)
    state = {"version": 1, "filled_order_ids": [], "cancelled_order_ids": [], "fills": []}

    summary = process_once(args, state)

    assert summary["filled"] == 0
    assert summary["skipped"] == 1
    assert "已有反向持仓" in (out_dir / "events.jsonl").read_text(encoding="utf-8")


def test_futures_pending_monitor_cancels_order_across_main_contract_switch(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.delenv("FENGJI_MARKET", raising=False)
    manifest = tmp_path / "runtime" / "logs" / "futures_main_contract_sources.json"
    manifest.parent.mkdir(parents=True)
    manifest.write_text(
        json.dumps(
            {
                "symbols": {
                    "JD": {
                        "data_contract": "DCE.jd2609",
                        "previous_data_contract": "DCE.jd2608",
                        "contract_switched_at": "2026-07-15 13:02:29",
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    orders = convert_radar_rows(
        [radar_row("JDUSDT", side="short", trigger=4590.0, stop=4688.0)],
        include_strategies={"DS03"},
        include_triggered=False,
        max_distance_pct=0.08,
        created_at="2026-07-15 13:01:04",
    )
    out_dir = tmp_path / "pending"
    orders_json, _ = write_orders(orders, out_dir)
    data_dir = tmp_path / "data"
    write_bar(data_dir, "JDUSDT", high=4435.0, low=4393.0, close=4400.0)
    args = make_args(tmp_path, orders_json, data_dir)
    state = {"version": 1, "filled_order_ids": [], "cancelled_order_ids": [], "fills": []}

    summary = process_once(args, state)

    assert summary["filled"] == 0
    assert summary["cancelled"] == 1
    assert state["cancelled_order_ids"] == [orders[0].order_id]
    event = json.loads((out_dir / "events.jsonl").read_text(encoding="utf-8").strip())
    assert event["event_type"] == "cancel"
    assert event["cancel_reason"] == "main_contract_switched"
    assert event["contract_switch"]["current_contract"] == "DCE.jd2609"


def test_futures_pending_monitor_closes_stop_from_local_bar(tmp_path: Path) -> None:
    orders = convert_radar_rows(
        [radar_row("CJUSDT", side="long", trigger=100.0, stop=95.0)],
        include_strategies={"DS03"},
        include_triggered=False,
        max_distance_pct=0.08,
        created_at="2026-05-26 10:00:00",
    )
    out_dir = tmp_path / "pending"
    orders_json, _ = write_orders(orders, out_dir)
    data_dir = tmp_path / "data"
    write_bar(data_dir, "CJUSDT", high=101.0, low=98.0, close=100.5)
    args = make_args(tmp_path, orders_json, data_dir)
    state = {"version": 1, "filled_order_ids": [], "cancelled_order_ids": [], "fills": []}
    process_once(args, state)

    write_bar(data_dir, "CJUSDT", high=97.0, low=94.0, close=95.0)
    summary = process_once(args, state)
    saved = json.loads(Path(args.paper_state_file).read_text(encoding="utf-8"))

    assert summary["closed"] == 1
    assert saved["symbols"]["CJUSDT"]["open_positions"] == []
    assert "CLOSE" in Path(args.trade_csv).read_text(encoding="utf-8-sig")


def test_futures_pending_monitor_freezes_old_contract_position_stop(tmp_path: Path, monkeypatch) -> None:
    manifest = tmp_path / "runtime" / "logs" / "futures_main_contract_sources.json"
    manifest.parent.mkdir(parents=True)
    manifest.write_text(
        json.dumps(
            {
                "symbols": {
                    "JD": {
                        "data_contract": "DCE.jd2609",
                        "previous_data_contract": "DCE.jd2608",
                        "contract_switched_at": "2026-07-15 13:02:29",
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("FUTURES_MAIN_CONTRACT_MANIFEST", str(manifest))
    orders_json = tmp_path / "pending" / "pending_orders.json"
    orders_json.parent.mkdir(parents=True)
    orders_json.write_text("[]", encoding="utf-8")
    data_dir = tmp_path / "data"
    write_bar(data_dir, "JDUSDT", high=4700.0, low=4400.0, close=4600.0)
    paper_state = tmp_path / "futures" / "state_futures_v2.json"
    paper_state.parent.mkdir(parents=True)
    paper_state.write_text(
        json.dumps(
            {
                "symbols": {
                    "JDUSDT": {
                        "open_positions": [
                            {
                                "key": "pending|jd-old",
                                "order_id": "jd-old",
                                "strategy_id": "DS01",
                                "side": -1,
                                "entry_price": 4590.0,
                                "initial_stop": 4688.0,
                                "current_stop": 4688.0,
                                "entry_data_contract": "DCE.jd2608",
                                "created_at": "2026-07-15 13:01:04",
                            }
                        ]
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    args = make_args(tmp_path, orders_json, data_dir)
    state = {"version": 1, "filled_order_ids": [], "cancelled_order_ids": [], "fills": []}

    summary = process_once(args, state)
    saved = json.loads(paper_state.read_text(encoding="utf-8"))

    assert summary["closed"] == 0
    assert len(saved["symbols"]["JDUSDT"]["open_positions"]) == 1


def test_format_fill_includes_chinese_futures_name() -> None:
    from fengji_futures_pending_order_monitor import format_fill

    msg = format_fill(
        {
            "symbol": "SA",
            "side": "short",
            "strategy_id": "DS03",
            "timeframe": "D1",
            "trigger_price": 1079,
            "stop_price": 1117,
            "os_camp": "blue",
            "setup": "blue camp break true peak (starter bar only)",
        },
        1079.0,
        {"timeframe": "15m", "date": "2026-07-07 05:45:00", "high": 1083, "low": 1076},
        "DS03 非连续定式允许首次开仓",
    )
    assert "品种: 纯碱(SA)" in msg
    assert "【已卖出 · 挂单卖出价格已成交 · 含预计平仓】" in msg
    assert "消息类型: 已卖出 + 挂单卖出价格已成交 + 预计挂单平仓价格" in msg
    assert "状态: 已卖出" in msg
    assert "预计挂单卖出价格: 1079" in msg
    assert "挂单卖出价格已成交: 1079" in msg
    assert "预计挂单平仓价格: 1117" in msg
    assert "挂单触发价" not in msg
    assert "模拟成交价" not in msg


def test_format_fill_domestic_long_matches_clear_status_copy() -> None:
    from fengji_futures_pending_order_monitor import format_fill

    msg = format_fill(
        {
            "symbol": "CF",
            "side": "long",
            "strategy_id": "DS01",
            "timeframe": "D1",
            "trigger_price": 16195,
            "stop_price": 15915,
            "os_camp": "red",
            "setup": "yesterday red-camp bullish stick; initial/add decided by position state",
        },
        16195.0,
        {"timeframe": "15m", "date": "2026-07-13 01:30:00", "high": 16200, "low": 16155},
        "DS01 允许同向连续开仓",
    )

    assert "【已买入 · 挂单买入价格已成交 · 含预计平仓】" in msg
    assert "消息类型: 已买入 + 挂单买入价格已成交 + 预计挂单平仓价格" in msg
    assert "品种: 棉花(CF)" in msg
    assert "状态: 已买入" in msg
    assert "预计挂单买入价格: 16195" in msg
    assert "挂单买入价格已成交: 16195" in msg
    assert "预计挂单平仓价格: 15915" in msg
    assert "风控规则: DS01 允许同向连续开仓" in msg


def test_format_stop_exit_domestic_close_status_by_position_side() -> None:
    from fengji_futures_pending_order_monitor import format_stop_exit

    long_msg = format_stop_exit(
        "CF",
        {
            "strategy_id": "DS01",
            "side": 1,
            "entry_time": "2026-07-13 01:30:00",
            "entry_price": 16195,
            "initial_stop": 15915,
        },
        15915,
        {"net_pnl": -1400.0},
        {"timeframe": "15m", "date": "2026-07-13 10:00:00"},
    )
    assert "【已卖出平仓 · 平仓价格已成交】" in long_msg
    assert "消息类型: 已卖出平仓 + 平仓价格已成交" in long_msg
    assert "状态: 已卖出平仓" in long_msg
    assert "预计挂单平仓价格: 15915" in long_msg
    assert "平仓价格已成交: 15915" in long_msg

    short_msg = format_stop_exit(
        "SA",
        {
            "strategy_id": "DS03",
            "side": -1,
            "entry_time": "2026-07-07 05:45:00",
            "entry_price": 1079,
            "initial_stop": 1117,
        },
        1117,
        {"net_pnl": -760.0},
        {"timeframe": "15m", "date": "2026-07-07 10:00:00"},
    )
    assert "【已买入平仓 · 平仓价格已成交】" in short_msg
    assert "消息类型: 已买入平仓 + 平仓价格已成交" in short_msg
    assert "状态: 已买入平仓" in short_msg

