from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from scripts.generate_fill_sandbox_review import build_review_tasks, load_jsonl, match_trade_no, render_markdown


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def test_builds_ready_ds01_review_task_from_filled_open_order(tmp_path: Path) -> None:
    orders = tmp_path / "pending_orders.json"
    state = tmp_path / "state.json"
    paper = tmp_path / "paper.json"
    events = tmp_path / "events.jsonl"
    data_dir = tmp_path / "data"
    data_dir.joinpath("1d").mkdir(parents=True)
    data_dir.joinpath("1d", "LCUSDT.csv").write_text("date,open,high,low,close,volume\n2026-07-08,1,2,1,2,10\n", encoding="utf-8")

    order = {
        "order_id": "LCUSDT-DS01-D1-short-a8bd5f81a279c66e",
        "symbol": "LCUSDT",
        "strategy_id": "DS01",
        "side": "short",
        "status": "READY_TRIGGERED",
        "trigger_price": 158400.0,
        "stop_price": 165200.0,
        "latest_time": "2026-07-08 16:00:00",
        "setup_key": "LCUSDT|DS01|SHORT|signal=20260707160000|trigger=158400",
    }
    write_json(orders, [order])
    write_json(state, {"filled_order_ids": [order["order_id"]]})
    write_json(
        paper,
        {"symbols": {"LCUSDT": {"open_positions": [{"order_id": order["order_id"], "setup_key": order["setup_key"]}]}}},
    )
    events.write_text(
        json.dumps(
            {
                "event_type": "fill",
                "order_id": order["order_id"],
                "setup_key": order["setup_key"],
                "time": "2026-07-09 13:53:35",
                "latest_time": "2026-07-08 16:00:00",
                "fill_price": 158400.0,
                "trigger_price": 158400.0,
                "stop_price": 165200.0,
            }
        )
        + "\n",
        encoding="utf-8",
    )

    tasks = build_review_tasks(
        orders_file=orders,
        state_file=state,
        paper_state_file=paper,
        event_files=[events],
        data_dir=data_dir,
        os_state_dir=tmp_path / "os_state",
        out_dir=tmp_path / "review",
    )

    assert len(tasks) == 1
    task = tasks[0]
    assert task.status == "ready"
    assert task.strategy_id == "DS01"
    assert task.fill_price == 158400.0
    assert "plot_crypto_ds01_trade_sandbox.py" in " ".join(task.command)
    assert "--entry-date" in task.command


def test_ignores_cancelled_and_active_orders(tmp_path: Path) -> None:
    orders = tmp_path / "pending_orders.json"
    state = tmp_path / "state.json"
    paper = tmp_path / "paper.json"
    write_json(
        orders,
        [
            {
                "order_id": "A",
                "symbol": "ETHUSDT",
                "strategy_id": "DS03",
                "side": "long",
                "status": "ACTIVE",
                "trigger_price": 100,
                "stop_price": 90,
            },
            {
                "order_id": "B",
                "symbol": "BTCUSDT",
                "strategy_id": "DS03",
                "side": "short",
                "status": "ACTIVE",
                "trigger_price": 100,
                "stop_price": 120,
            },
        ],
    )
    write_json(state, {"cancelled_order_ids": ["B"]})
    write_json(paper, {})

    tasks = build_review_tasks(
        orders_file=orders,
        state_file=state,
        paper_state_file=paper,
        event_files=[],
        data_dir=tmp_path / "data",
        os_state_dir=tmp_path / "os_state",
        out_dir=tmp_path / "review",
    )

    assert tasks == []


def test_marks_filled_unsupported_strategy_explicitly(tmp_path: Path) -> None:
    orders = tmp_path / "pending_orders.json"
    state = tmp_path / "state.json"
    paper = tmp_path / "paper.json"
    order = {
        "order_id": "LHUSDT-DS06-D1-short-1",
        "symbol": "LHUSDT",
        "strategy_id": "DS06",
        "side": "short",
        "status": "READY_TRIGGERED",
        "trigger_price": 11750,
        "stop_price": 11940,
    }
    write_json(orders, [order])
    write_json(state, {"filled_order_ids": [order["order_id"]]})
    write_json(paper, {})

    tasks = build_review_tasks(
        orders_file=orders,
        state_file=state,
        paper_state_file=paper,
        event_files=[],
        data_dir=tmp_path / "data",
        os_state_dir=tmp_path / "os_state",
        out_dir=tmp_path / "review",
    )

    assert tasks[0].status == "unsupported"
    assert "DS06" in tasks[0].reason
    assert "unsupported" in render_markdown(tasks)


def test_ds04_is_supported_and_reports_missing_plotter_or_data(tmp_path: Path) -> None:
    orders = tmp_path / "pending_orders.json"
    state = tmp_path / "state.json"
    paper = tmp_path / "paper.json"
    order = {
        "order_id": "SHUSDT-DS04-D1-short-1",
        "symbol": "SHUSDT",
        "strategy_id": "DS04",
        "side": "short",
        "status": "READY_TRIGGERED",
        "trigger_price": 1871,
        "stop_price": 1941,
    }
    write_json(orders, [order])
    write_json(state, {"filled_order_ids": [order["order_id"]]})
    write_json(paper, {})

    tasks = build_review_tasks(
        orders_file=orders,
        state_file=state,
        paper_state_file=paper,
        event_files=[],
        data_dir=tmp_path / "data",
        os_state_dir=tmp_path / "os_state",
        out_dir=tmp_path / "review",
    )

    assert tasks[0].status == "missing_data"
    assert "DS04" not in tasks[0].reason


def test_ds05_filled_open_uses_live_plotter(tmp_path: Path) -> None:
    orders = tmp_path / "pending_orders.json"
    state = tmp_path / "state.json"
    paper = tmp_path / "paper.json"
    data_dir = tmp_path / "data"
    data_dir.joinpath("1d").mkdir(parents=True)
    data_dir.joinpath("1d", "LHUSDT.csv").write_text("date,open,high,low,close,volume\n2026-07-08,1,2,1,2,10\n", encoding="utf-8")
    order = {
        "order_id": "LHUSDT-DS05-D1-short-1",
        "symbol": "LHUSDT",
        "strategy_id": "DS05",
        "side": "short",
        "status": "READY_TRIGGERED",
        "trigger_price": 11750,
        "stop_price": 11940,
        "setup_key": "LHUSDT|DS05|SHORT|k2=20260623160000|k3=20260624160000|trigger=11750",
    }
    write_json(orders, [order])
    write_json(state, {"filled_order_ids": [order["order_id"]]})
    write_json(paper, {"symbols": {"LHUSDT": {"open_positions": [{"order_id": order["order_id"]}]}}})

    tasks = build_review_tasks(
        orders_file=orders,
        state_file=state,
        paper_state_file=paper,
        event_files=[],
        data_dir=data_dir,
        os_state_dir=tmp_path / "os_state",
        out_dir=tmp_path / "review",
    )

    assert tasks[0].status == "ready"
    assert "plot_live_ds05_sandbox.py" in " ".join(tasks[0].command)
    assert "--setup-key" in tasks[0].command


def test_ds09_filled_open_uses_live_plotter(tmp_path: Path) -> None:
    orders = tmp_path / "pending_orders.json"
    state = tmp_path / "state.json"
    paper = tmp_path / "paper.json"
    data_dir = tmp_path / "data"
    data_dir.joinpath("1d").mkdir(parents=True)
    data_dir.joinpath("15m").mkdir(parents=True)
    data_dir.joinpath("1d", "SOLUSDT.csv").write_text("date,open,high,low,close,volume\n2026-07-08,1,2,1,2,10\n", encoding="utf-8")
    data_dir.joinpath("15m", "SOLUSDT.csv").write_text("date,open,high,low,close,volume\n2026-07-08 09:00,1,2,1,2,10\n", encoding="utf-8")
    order = {
        "order_id": "SOLUSDT-DS09-M15-long-1",
        "symbol": "SOLUSDT",
        "strategy_id": "DS09",
        "side": "long",
        "status": "READY_TRIGGERED",
        "trigger_price": 75.87,
        "stop_price": 73.96,
        "setup_key": "SOLUSDT|DS09|LONG|2026-07-01 00:00:00|lock=923|def=931|75.87",
        "reason": "lock_idx=923, attack_idx=924, defense_idx=931, boundary=75.8",
    }
    write_json(orders, [order])
    write_json(state, {"filled_order_ids": [order["order_id"]]})
    write_json(paper, {"symbols": {"SOLUSDT": {"open_positions": [{"order_id": order["order_id"]}]}}})

    tasks = build_review_tasks(
        orders_file=orders,
        state_file=state,
        paper_state_file=paper,
        event_files=[],
        data_dir=data_dir,
        os_state_dir=tmp_path / "os_state",
        out_dir=tmp_path / "review",
    )

    assert tasks[0].status == "ready"
    command = " ".join(tasks[0].command)
    assert "plot_live_ds09_sandbox.py" in command
    assert "--boundary" in tasks[0].command


def test_load_jsonl_reads_only_tail_lines(tmp_path: Path) -> None:
    path = tmp_path / "events.jsonl"
    path.write_text(
        "\n".join(
            json.dumps({"event_type": "fill", "order_id": f"ORDER-{idx}"})
            for idx in range(10)
        )
        + "\n",
        encoding="utf-8",
    )

    rows = load_jsonl(path, tail_lines=3)

    assert [row["order_id"] for row in rows] == ["ORDER-7", "ORDER-8", "ORDER-9"]


def test_match_trade_no_uses_side_price_and_date() -> None:
    trades = pd.DataFrame(
        [
            {"trade_no": 1, "direction": "long", "entry_price": 100.0, "entry_date": "2026-07-01 00:00:00"},
            {"trade_no": 2, "direction": "short", "entry_price": 158410.0, "entry_date": "2026-07-08 16:00:00"},
        ]
    )

    assert match_trade_no(trades, side="short", fill=158400.0, trigger=158400.0, when="2026-07-08 16:00:00") == 2
