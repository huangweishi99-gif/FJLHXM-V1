from __future__ import annotations

import argparse
from pathlib import Path

from scripts.summarize_pending_effective_status import build_sandbox_review_command, summarize


def test_effective_status_marks_filled_open_order_not_actionable() -> None:
    order = {
        "order_id": "LCUSDT-DS01-D1-short-a8bd5f81a279c66e",
        "symbol": "LCUSDT",
        "strategy_id": "DS01",
        "side": "short",
        "status": "READY_TRIGGERED",
        "trigger_price": 158400.0,
        "setup_key": "LCUSDT|DS01|SHORT|signal=20260707160000|trigger=158400",
    }
    state = {
        "filled_order_ids": [order["order_id"]],
        "filled_setup_keys": [order["setup_key"]],
    }
    paper_state = {
        "symbols": {
            "LCUSDT": {
                "open_positions": [
                    {
                        "order_id": order["order_id"],
                        "setup_key": order["setup_key"],
                        "closed": False,
                    }
                ]
            }
        }
    }

    payload = summarize([order], state, paper_state)

    row = payload["rows"][0]
    assert row["raw_status"] == "READY_TRIGGERED"
    assert row["effective_status"] == "filled_open"
    assert row["actionable"] is False
    assert payload["actionable_orders"] == 0
    assert payload["review_candidate_orders"] == 1


def test_effective_status_marks_cancelled_conflict_not_actionable() -> None:
    order = {
        "order_id": "LCUSDT-DS03-D1-short-55e2130dc32aa8ef",
        "symbol": "LCUSDT",
        "strategy_id": "DS03",
        "side": "short",
        "status": "ACTIVE",
        "setup_key": "LCUSDT|DS03|SHORT|watch|trigger=145000",
    }
    state = {
        "cancelled_order_ids": [order["order_id"]],
        "cancelled_setup_keys": [order["setup_key"]],
    }

    payload = summarize([order], state, {})

    row = payload["rows"][0]
    assert row["effective_status"] == "cancelled"
    assert row["actionable"] is False
    assert payload["review_candidate_orders"] == 0


def test_effective_status_keeps_unseen_active_order_actionable() -> None:
    order = {
        "order_id": "ETHUSDT-DS03-D1-long-1",
        "symbol": "ETHUSDT",
        "strategy_id": "DS03",
        "side": "long",
        "status": "ACTIVE",
        "setup_key": "ETHUSDT|DS03|LONG|watch|trigger=100",
    }

    payload = summarize([order], {}, {})

    row = payload["rows"][0]
    assert row["effective_status"] == "active"
    assert row["actionable"] is True
    assert payload["effective_status_counts"] == {"active": 1}


def test_build_sandbox_review_command_reuses_effective_summary_paths() -> None:
    args = argparse.Namespace(
        orders_file="runtime/fengji_pending_orders/pending_orders.json",
        state_file="runtime/fengji_pending_orders/state.json",
        paper_state_file="runtime/fengji_paper/state.json",
        data_dir="data",
        os_state_dir="runtime/fengji_os_state",
        review_out_dir="runtime/fill_sandbox_review",
        review_limit=7,
        event_tail_lines=5000,
        event_file=[],
        symbol="BTCUSDT",
        sandbox_review_execute=True,
        review_timeout=45,
    )

    command = build_sandbox_review_command(args)

    joined = " ".join(command)
    assert "generate_fill_sandbox_review.py" in joined
    assert command[command.index("--orders-file") + 1] == args.orders_file
    assert command[command.index("--state-file") + 1] == args.state_file
    assert command[command.index("--paper-state-file") + 1] == args.paper_state_file
    assert Path(command[command.index("--event-file") + 1]) == Path("runtime/fengji_pending_orders/events.jsonl")
    assert command[command.index("--symbol") + 1] == "BTCUSDT"
    assert "--execute" in command
    assert command[command.index("--timeout") + 1] == "45"
