from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "repair_corrupt_futures_state_from_audit.py"


def load_module():
    spec = importlib.util.spec_from_file_location("repair_corrupt_futures_state_from_audit", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["repair_corrupt_futures_state_from_audit"] = module
    spec.loader.exec_module(module)
    return module


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def make_files(tmp_path: Path) -> tuple[Path, Path, Path]:
    order_id = "PPUSDT-DS01-D1-long-44b9d7cd48133592"
    audit_path = tmp_path / "audit.json"
    state_path = tmp_path / "state_futures_v2.json"
    monitor_path = tmp_path / "futures_pending_state.json"
    write_json(
        audit_path,
        {
            "suspicious": [
                {
                    "_suspicious_reasons": ["fill_touches_corrupt_window", "bar_low=too_small"],
                    "event_type": "fill",
                    "symbol": "PPUSDT",
                    "order_id": order_id,
                    "setup_key": "PPUSDT|DS01|LONG|signal=20260601160000|trigger=8788",
                }
            ],
            "state": {
                "PPUSDT": {
                    "audit_invalid_closes": [
                        {
                            "event_type": "close",
                            "symbol": "PPUSDT",
                            "order_id": order_id,
                            "trade_key": f"pending|{order_id}",
                            "net_pnl": -88146.44,
                        }
                    ]
                }
            },
        },
    )
    write_json(
        state_path,
        {
            "symbols": {
                "PPUSDT": {
                    "open_positions": [
                        {
                            "key": f"pending|{order_id}",
                            "order_id": order_id,
                            "setup_key": "PPUSDT|DS01|LONG|signal=20260601160000|trigger=8788",
                            "symbol": "PPUSDT",
                            "entry_time": "2026-05-29 01:00:00",
                            "entry_price": 8812.0,
                        }
                    ],
                    "seen_entries": [order_id],
                    "closed_entries": [],
                    "equity": 11790.839,
                    "audit_invalid_closes": [
                        {
                            "event_type": "close",
                            "symbol": "PPUSDT",
                            "order_id": order_id,
                            "trade_key": f"pending|{order_id}",
                            "net_pnl": -88146.44,
                        }
                    ],
                }
            }
        },
    )
    write_json(
        monitor_path,
        {
            "filled_order_ids": [order_id, "SAUSDT-DS01-D1-short-x"],
            "filled_setup_keys": ["PPUSDT|DS01|LONG|signal=20260601160000|trigger=8788"],
            "consumed_ds03_setup_keys": [],
        },
    )
    return audit_path, state_path, monitor_path


def test_dry_run_does_not_mutate_state_or_monitor(tmp_path: Path) -> None:
    module = load_module()
    audit_path, state_path, monitor_path = make_files(tmp_path)
    before_state = state_path.read_text(encoding="utf-8")
    before_monitor = monitor_path.read_text(encoding="utf-8")
    out_path = tmp_path / "plan.json"

    code = module.main(
        [
            "--audit",
            str(audit_path),
            "--state",
            str(state_path),
            "--monitor-state",
            str(monitor_path),
            "--out",
            str(out_path),
        ]
    )
    plan = json.loads(out_path.read_text(encoding="utf-8"))

    assert code == 0
    assert state_path.read_text(encoding="utf-8") == before_state
    assert monitor_path.read_text(encoding="utf-8") == before_monitor
    assert plan["apply"] is False
    assert plan["counts"]["invalidated_positions"] == 1
    assert plan["counts"]["released_monitor_locks"] == 2
    assert plan["counts"]["equity_rollback_candidates"] == 1


def test_apply_moves_open_position_and_archives_monitor_locks(tmp_path: Path) -> None:
    module = load_module()
    audit_path, state_path, monitor_path = make_files(tmp_path)

    code = module.main(
        [
            "--audit",
            str(audit_path),
            "--state",
            str(state_path),
            "--monitor-state",
            str(monitor_path),
            "--backup-dir",
            str(tmp_path / "backup"),
            "--apply",
        ]
    )
    state = json.loads(state_path.read_text(encoding="utf-8"))
    monitor = json.loads(monitor_path.read_text(encoding="utf-8"))
    pp = state["symbols"]["PPUSDT"]

    assert code == 0
    assert pp["open_positions"] == []
    assert pp["audit_invalid_positions"][0]["audit_invalid"] is True
    assert "PPUSDT-DS01-D1-long-44b9d7cd48133592" in pp["audit_invalid_entries"]
    assert monitor["filled_order_ids"] == ["SAUSDT-DS01-D1-short-x"]
    assert monitor["filled_setup_keys"] == []
    assert monitor["audit_invalid_filled_order_ids"] == ["PPUSDT-DS01-D1-long-44b9d7cd48133592"]
    assert (tmp_path / "backup" / "state_futures_v2.json").exists()
    assert (tmp_path / "backup" / "futures_pending_state.json").exists()
