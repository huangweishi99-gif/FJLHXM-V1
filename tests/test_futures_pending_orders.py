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
