from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "render_corrupt_futures_state_repair_checklist.py"


def load_module():
    spec = importlib.util.spec_from_file_location("render_corrupt_futures_state_repair_checklist", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["render_corrupt_futures_state_repair_checklist"] = module
    spec.loader.exec_module(module)
    return module


def test_decision_requires_apply_confirmation_when_state_or_locks_change() -> None:
    module = load_module()
    plan = {
        "apply": False,
        "counts": {
            "targets": 1,
            "invalidated_positions": 1,
            "released_monitor_locks": 2,
            "already_invalid_closes": 0,
            "equity_rollback_candidates": 0,
        },
    }

    status, message = module.decision(plan)

    assert status == "APPLY_REQUIRES_CONFIRMATION"
    assert "manual evidence review" in message


def test_decision_equity_review_wins_when_no_writable_residue() -> None:
    module = load_module()
    plan = {
        "apply": False,
        "counts": {
            "targets": 3,
            "invalidated_positions": 0,
            "released_monitor_locks": 0,
            "already_invalid_closes": 1,
            "equity_rollback_candidates": 1,
        },
    }

    status, _ = module.decision(plan)

    assert status == "EQUITY_REVIEW_REQUIRED"


def test_main_writes_markdown_checklist(tmp_path: Path) -> None:
    module = load_module()
    plan_path = tmp_path / "plan.json"
    out_path = tmp_path / "checklist.md"
    plan_path.write_text(
        json.dumps(
            {
                "apply": False,
                "audit": "runtime/logs/audit.json",
                "state": "runtime/fengji_futures/state_futures_v2.json",
                "monitor_state": "runtime/fengji_pending_orders/futures_pending_state.json",
                "targets": ["PPUSDT-DS01-D1-long-x"],
                "counts": {
                    "targets": 1,
                    "invalidated_positions": 0,
                    "released_monitor_locks": 0,
                    "already_invalid_closes": 1,
                    "equity_rollback_candidates": 1,
                },
                "already_invalid_closes": [{"symbol": "PPUSDT", "order_id": "PPUSDT-DS01-D1-long-x"}],
                "equity_rollback_candidates": [{"symbol": "PPUSDT", "net_pnl_to_reverse": -100.0}],
                "released_monitor_locks": {"filled_order_ids": [], "filled_setup_keys": [], "consumed_ds03_setup_keys": []},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    code = module.main(["--plan", str(plan_path), "--out", str(out_path), "--title", "PP checklist"])
    text = out_path.read_text(encoding="utf-8")

    assert code == 0
    assert "# PP checklist" in text
    assert "Decision: **EQUITY_REVIEW_REQUIRED**" in text
    assert "Equity rollback is **not automatic**" in text
    assert "Apply command template" in text
