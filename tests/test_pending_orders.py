from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from fengji_pending_order_monitor import process_once
from fengji_pending_orders import convert_radar_rows, write_orders


def _future_latest_time(days: int = 2) -> str:
    return str((pd.Timestamp.now(tz="Asia/Shanghai").tz_localize(None) + pd.Timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S"))


def _future_created_at() -> str:
    return str((pd.Timestamp.now(tz="Asia/Shanghai").tz_localize(None) + pd.Timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S"))


def radar_row(
    symbol: str,
    strategy_id: str,
    status: str,
    side: str = "long",
    trigger: float = 10.0,
    current: float = 9.5,
    latest_time: str | None = None,
    setup_key: str = "",
) -> dict:
    return {
        "symbol": symbol,
        "strategy_id": strategy_id,
        "timeframe": "D1",
        "side": side,
        "status": status,
        "setup": "test setup",
        "current_price": current,
        "trigger_price": trigger,
        "distance_pct": (trigger - current) / current,
        "stop_price": 9.0,
        "os_camp": "red",
        "latest_time": latest_time or _future_latest_time(),
        "reason": "test",
        "setup_key": setup_key,
    }


def test_convert_radar_rows_exports_only_actionable_pending_orders() -> None:
    rows = [
        radar_row("RENDERUSDT", "DS01", "PENDING"),
        radar_row("RENDERUSDT", "DS02", "CONFIRM_ON_CLOSE"),
        radar_row("RENDERUSDT", "DS01", "BLOCKED_LEFT_LINES"),
        radar_row("RENDERUSDT", "ERROR", "ERROR"),
    ]

    orders = convert_radar_rows(
        rows,
        include_strategies={"DS01", "DS02"},
        include_triggered=False,
        max_distance_pct=0.08,
        created_at=_future_created_at(),
    )

    assert len(orders) == 1
    assert orders[0].symbol == "RENDERUSDT"
    assert orders[0].strategy_id == "DS01"
    assert orders[0].status == "ACTIVE"


def test_ds05_pending_is_actionable_by_default() -> None:
    rows = [radar_row("BTCUSDT", "DS05", "PENDING", side="short", trigger=9.0, current=9.5)]

    orders = convert_radar_rows(
        rows,
        include_strategies={"DS01", "DS03", "DS05", "DS06", "DS07", "DS08"},
        include_triggered=False,
        max_distance_pct=0.08,
        created_at=_future_created_at(),
    )

    assert len(orders) == 1
    assert orders[0].strategy_id == "DS05"
    assert orders[0].side == "short"
    assert orders[0].status == "ACTIVE"


def test_ds06_pending_is_not_actionable_by_default() -> None:
    rows = [radar_row("APTUSDT", "DS06", "PENDING", side="short", trigger=9.0, current=9.5)]

    orders = convert_radar_rows(
        rows,
        include_strategies={"DS01", "DS03", "DS05", "DS07", "DS08"},
        include_triggered=False,
        max_distance_pct=0.08,
        created_at=_future_created_at(),
    )

    assert orders == []


def test_pending_monitor_fills_crossed_mock_price(tmp_path: Path) -> None:
    orders = convert_radar_rows(
        [radar_row("RENDERUSDT", "DS01", "PENDING", trigger=10.0, current=9.5)],
        include_strategies={"DS01"},
        include_triggered=False,
        max_distance_pct=0.08,
        created_at=_future_created_at(),
    )
    out_dir = tmp_path / "pending"
    orders_json, _ = write_orders(orders, out_dir)
    price_file = tmp_path / "prices.json"
    price_file.write_text(json.dumps({"RENDERUSDT": 10.01}), encoding="utf-8")

    args = argparse.Namespace(
        orders_file=str(orders_json),
        out_dir=str(out_dir),
        state_file=str(out_dir / "state.json"),
        paper_state_file="",
        feishu_webhook="",
        price_file=str(price_file),
        max_ds01_entries=3,
        no_paper_state_update=False,
    )
    state = {"version": 1, "filled_order_ids": [], "cancelled_order_ids": [], "fills": []}

    summary = process_once(args, state)

    assert summary["checked_orders"] == 1
    assert summary["filled"] == 1
    assert state["filled_order_ids"] == [orders[0].order_id]
    assert (out_dir / "fills.csv").exists()


def test_setup_key_keeps_order_id_stable_across_refreshes() -> None:
    setup_key = "RENDERUSDT|DS08|LONG|4|3|2.28"
    orders_1 = convert_radar_rows(
        [radar_row("RENDERUSDT", "DS08", "PENDING", trigger=10.0, current=9.5, latest_time=_future_latest_time(2), setup_key=setup_key)],
        include_strategies={"DS08"},
        include_triggered=False,
        max_distance_pct=0.08,
        created_at=_future_created_at(),
    )
    orders_2 = convert_radar_rows(
        [radar_row("RENDERUSDT", "DS08", "PENDING", trigger=10.0, current=9.5, latest_time=_future_latest_time(2), setup_key=setup_key)],
        include_strategies={"DS08"},
        include_triggered=False,
        max_distance_pct=0.08,
        created_at=str((pd.Timestamp.now(tz="Asia/Shanghai").tz_localize(None) + pd.Timedelta(hours=2)).strftime("%Y-%m-%d %H:%M:%S")),
    )

    assert orders_1[0].setup_key == setup_key
    assert orders_1[0].order_id == orders_2[0].order_id


def test_pending_monitor_records_filled_setup_key(tmp_path: Path) -> None:
    setup_key = "RENDERUSDT|DS01|LONG|signal=20260701000000|trigger=10"
    orders = convert_radar_rows(
        [radar_row("RENDERUSDT", "DS01", "PENDING", trigger=10.0, current=9.5, setup_key=setup_key)],
        include_strategies={"DS01"},
        include_triggered=False,
        max_distance_pct=0.08,
        created_at=_future_created_at(),
    )
    out_dir = tmp_path / "pending"
    orders_json, _ = write_orders(orders, out_dir)
    price_file = tmp_path / "prices.json"
    price_file.write_text(json.dumps({"RENDERUSDT": 10.01}), encoding="utf-8")
    args = argparse.Namespace(
        orders_file=str(orders_json),
        out_dir=str(out_dir),
        state_file=str(out_dir / "state.json"),
        paper_state_file="",
        feishu_webhook="",
        price_file=str(price_file),
        max_ds01_entries=3,
        no_paper_state_update=False,
    )
    state = {"version": 1, "filled_order_ids": [], "cancelled_order_ids": [], "fills": []}

    process_once(args, state)

    assert state["filled_setup_keys"] == [setup_key]


def test_pending_monitor_cancels_same_symbol_conflicts_in_same_cycle(tmp_path: Path) -> None:
    orders = convert_radar_rows(
        [
            radar_row("RENDERUSDT", "DS01", "PENDING", trigger=10.0, current=9.5),
            radar_row("RENDERUSDT", "DS03", "PENDING", trigger=9.9, current=9.5),
        ],
        include_strategies={"DS01", "DS03"},
        include_triggered=False,
        max_distance_pct=0.08,
        created_at=_future_created_at(),
    )
    out_dir = tmp_path / "pending"
    orders_json, _ = write_orders(orders, out_dir)
    price_file = tmp_path / "prices.json"
    price_file.write_text(json.dumps({"RENDERUSDT": 10.01}), encoding="utf-8")

    args = argparse.Namespace(
        orders_file=str(orders_json),
        out_dir=str(out_dir),
        state_file=str(out_dir / "state.json"),
        paper_state_file="",
        feishu_webhook="",
        price_file=str(price_file),
        max_ds01_entries=3,
        no_paper_state_update=False,
    )
    state = {"version": 1, "filled_order_ids": [], "cancelled_order_ids": [], "fills": []}

    summary = process_once(args, state)

    assert summary["filled"] == 1
    assert len(state["filled_order_ids"]) == 1
    assert len(state["cancelled_order_ids"]) == 1
    filled_order = next(order for order in orders if order.order_id in state["filled_order_ids"])
    assert filled_order.strategy_id == "DS01"


def test_pending_monitor_updates_paper_state_on_fill(tmp_path: Path) -> None:
    orders = convert_radar_rows(
        [radar_row("RENDERUSDT", "DS01", "PENDING", trigger=10.0, current=9.5)],
        include_strategies={"DS01"},
        include_triggered=False,
        max_distance_pct=0.08,
        created_at=_future_created_at(),
    )
    out_dir = tmp_path / "pending"
    orders_json, _ = write_orders(orders, out_dir)
    price_file = tmp_path / "prices.json"
    price_file.write_text(json.dumps({"RENDERUSDT": 10.01}), encoding="utf-8")
    paper_state = tmp_path / "paper_state.json"

    args = argparse.Namespace(
        orders_file=str(orders_json),
        out_dir=str(out_dir),
        state_file=str(out_dir / "state.json"),
        paper_state_file=str(paper_state),
        feishu_webhook="",
        price_file=str(price_file),
        max_ds01_entries=3,
        initial_cash=1000.0,
        margin_per_trade=200.0,
        leverage=2.0,
        fee_rate=0.0005,
        slippage_rate=0.0003,
        no_paper_state_update=False,
    )
    state = {"version": 1, "filled_order_ids": [], "cancelled_order_ids": [], "fills": []}

    summary = process_once(args, state)
    saved = json.loads(paper_state.read_text(encoding="utf-8"))
    position = saved["symbols"]["RENDERUSDT"]["open_position"]

    assert summary["filled"] == 1
    assert position["source"] == "pending_order"
    assert position["strategy_id"] == "DS01"
    assert position["entries"] == 1


def test_pending_monitor_skip_log_preserves_skip_reason(tmp_path: Path) -> None:
    orders = convert_radar_rows(
        [radar_row("RENDERUSDT", "DS03", "PENDING", trigger=10.0, current=9.5)],
        include_strategies={"DS03"},
        include_triggered=False,
        max_distance_pct=0.08,
        created_at=_future_created_at(),
    )
    out_dir = tmp_path / "pending"
    orders_json, _ = write_orders(orders, out_dir)
    price_file = tmp_path / "prices.json"
    price_file.write_text(json.dumps({"RENDERUSDT": 9.8}), encoding="utf-8")
    paper_state = tmp_path / "paper_state.json"
    paper_state.write_text(
        json.dumps(
            {
                "symbols": {
                    "RENDERUSDT": {
                        "open_position": {"strategy_id": "DS01", "side": 1},
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    args = argparse.Namespace(
        orders_file=str(orders_json),
        out_dir=str(out_dir),
        state_file=str(out_dir / "state.json"),
        paper_state_file=str(paper_state),
        feishu_webhook="",
        price_file=str(price_file),
        max_ds01_entries=3,
        initial_cash=1000.0,
        margin_per_trade=200.0,
        leverage=2.0,
        fee_rate=0.0005,
        slippage_rate=0.0003,
        no_paper_state_update=False,
    )
    state = {"version": 1, "filled_order_ids": [], "cancelled_order_ids": [], "fills": []}

    summary = process_once(args, state)
    event = json.loads((out_dir / "events.jsonl").read_text(encoding="utf-8").strip())

    assert summary["skipped"] == 1
    assert event["skip_reason"] == "symbol already has an open position"
    assert event["reason"] == "test"


def test_pending_monitor_closes_paper_state_on_stop(tmp_path: Path, monkeypatch) -> None:
    import fengji_core.stop_bar_monitor as sbm

    def _fake_stop_bar(args, symbol, position):
        return {"date": "2026-07-02 00:00:00", "low": 8.9, "high": 10.0, "close": 9.5}

    monkeypatch.setattr(sbm, "read_stop_bar_for_position", _fake_stop_bar)
    monkeypatch.setattr(sbm, "stop_bar_after_entry", lambda _pos, _bar: True)
    monkeypatch.setattr(sbm, "stop_crossed", lambda _pos, _bar: True)
    monkeypatch.setattr(sbm, "stop_exit_fill", lambda _pos, _bar: (9.0, "stop"))

    orders = convert_radar_rows(
        [radar_row("RENDERUSDT", "DS01", "PENDING", trigger=10.0, current=9.5)],
        include_strategies={"DS01"},
        include_triggered=False,
        max_distance_pct=0.08,
        created_at=_future_created_at(),
    )
    out_dir = tmp_path / "pending"
    orders_json, _ = write_orders(orders, out_dir)
    price_file = tmp_path / "prices.json"
    price_file.write_text(json.dumps({"RENDERUSDT": 10.01}), encoding="utf-8")
    paper_state = tmp_path / "paper_state.json"
    args = argparse.Namespace(
        orders_file=str(orders_json),
        out_dir=str(out_dir),
        state_file=str(out_dir / "state.json"),
        paper_state_file=str(paper_state),
        feishu_webhook="",
        price_file=str(price_file),
        max_ds01_entries=3,
        initial_cash=1000.0,
        margin_per_trade=200.0,
        leverage=2.0,
        fee_rate=0.0005,
        slippage_rate=0.0003,
        no_paper_state_update=False,
    )
    state = {"version": 1, "filled_order_ids": [], "cancelled_order_ids": [], "fills": []}

    process_once(args, state)
    price_file.write_text(json.dumps({"RENDERUSDT": 8.9}), encoding="utf-8")
    summary = process_once(args, state)
    saved = json.loads(paper_state.read_text(encoding="utf-8"))

    assert summary["closed"] == 1
    assert saved["symbols"]["RENDERUSDT"]["open_position"] is None
    assert saved["closed_trades"][0]["exit_reason"] == "stop"
