from __future__ import annotations

import json
import sys
from pathlib import Path

from scripts.audit_domestic_notification_coverage import (
    check_notification_wording,
    check_source_contract,
    prepend_import_path,
    runtime_snapshot,
)


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def test_domestic_notification_wording_smoke_passes() -> None:
    result = check_notification_wording()

    assert result.ok, result.detail


def test_domestic_source_contract_rejects_legacy_fill_wording() -> None:
    result = check_source_contract()

    assert result.ok, result.detail


def test_prepend_import_path_moves_existing_path_to_front(tmp_path: Path) -> None:
    target = tmp_path / "src"
    other = tmp_path / "scripts"
    original = list(sys.path)
    try:
        sys.path[:] = [str(other), str(target), "tail"]
        prepend_import_path(target)

        assert sys.path[:3] == [str(target), str(other), "tail"]
        assert sys.path.count(str(target)) == 1
    finally:
        sys.path[:] = original


def test_runtime_snapshot_counts_domestic_pending_effective_and_paper_state(tmp_path: Path) -> None:
    order = {
        "order_id": "CF-DS01-D1-long-1",
        "symbol": "CF",
        "strategy_id": "DS01",
        "side": "long",
        "status": "READY_TRIGGERED",
        "trigger_price": 16195.0,
        "stop_price": 15915.0,
        "setup_key": "CF|DS01|LONG|1",
    }
    write_json(tmp_path / "runtime/fengji_pending_orders/pending_orders.json", [order])
    write_json(tmp_path / "runtime/fengji_pending_orders/futures_pending_state.json", {"filled_order_ids": [order["order_id"]]})
    write_json(
        tmp_path / "runtime/fengji_futures/state_futures_v2.json",
        {
            "symbols": {
                "CF": {
                    "open_positions": [
                        {
                            "order_id": order["order_id"],
                            "setup_key": order["setup_key"],
                            "strategy_id": "DS01",
                            "closed": False,
                        }
                    ]
                }
            }
        },
    )
    write_json(
        tmp_path / "runtime/fengji_radar/radar.json",
        [
            {"symbol": "CF", "strategy_id": "DS01", "status": "TRIGGERED"},
            {"symbol": "SA", "strategy_id": "DS03", "status": "ACTIVE"},
        ],
    )

    payload = runtime_snapshot(
        tmp_path,
        orders_file="runtime/fengji_pending_orders/pending_orders.json",
        state_file="runtime/fengji_pending_orders/futures_pending_state.json",
        paper_state_file="runtime/fengji_futures/state_futures_v2.json",
        radar_file="runtime/fengji_radar/radar.json",
    )

    assert payload["available"] == {"orders": True, "state": True, "paper_state": True, "radar": True}
    assert payload["radar_strategy_counts"] == {"DS01": 1, "DS03": 1}
    assert payload["pending_strategy_counts"] == {"DS01": 1}
    assert payload["effective_status_counts"] == {"filled_open": 1}
    assert payload["paper_open_strategy_counts"] == {"DS01": 1}
