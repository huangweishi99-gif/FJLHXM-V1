from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "audit_corrupt_futures_state.py"


def load_module():
    spec = importlib.util.spec_from_file_location("audit_corrupt_futures_state", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["audit_corrupt_futures_state"] = module
    spec.loader.exec_module(module)
    return module


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def test_audit_corrupt_window_finds_state_events_and_monitor_locks(tmp_path: Path) -> None:
    module = load_module()
    order_id = "PPUSDT-DS01-D1-long-44b9d7cd48133592"
    state_path = tmp_path / "runtime" / "fengji_futures" / "state_futures_v2.json"
    monitor_path = tmp_path / "runtime" / "fengji_pending_orders" / "futures_pending_state.json"
    events_path = tmp_path / "runtime" / "fengji_pending_orders" / "events.jsonl"
    out_path = tmp_path / "audit.json"
    state = {
        "symbols": {
            "PPUSDT": {
                "open_positions": [
                    {
                        "order_id": order_id,
                        "symbol": "PPUSDT",
                        "strategy_id": "DS01",
                        "direction": "long",
                        "entry_time": "2026-05-29 01:00:00",
                        "entry_price": 8812.0,
                        "entry_bar": "15m:2026-05-29 01:00:00",
                    }
                ],
                "audit_invalid_closes": [
                    {
                        "event_type": "close",
                        "symbol": "聚丙烯(PP)",
                        "strategy_id": "DS01",
                        "order_id": order_id,
                        "entry_time": "2026-05-29 01:00:00",
                        "exit_time": "2026-05-29 01:00:00",
                        "entry_price": 8812.0,
                        "exit_price": 6.518154682897931e-143,
                    }
                ],
                "seen_entries": [order_id],
                "closed_entries": [f"pending|{order_id}"],
            },
            "SAUSDT": {"open_positions": []},
        }
    }
    monitor = {
        "filled_order_ids": [order_id, "SAUSDT-DS01-D1-short-x"],
        "filled_setup_keys": ["PPUSDT|DS01|LONG|signal=20260601160000|trigger=8788"],
        "fills": [
            {
                "event_type": "fill",
                "symbol": "PPUSDT",
                "order_id": order_id,
                "time": "2026-06-04 10:40:22",
                "bar_time": "2026-05-29 01:00:00",
                "bar_high": 5.040428908412403e180,
                "bar_low": 3.183734056624e-312,
            }
        ],
    }
    events = [
        {
            "event_type": "fill",
            "symbol": "PPUSDT",
            "order_id": order_id,
            "time": "2026-06-04 10:40:22",
            "bar_time": "2026-05-29 01:00:00",
            "bar_high": 5.040428908412403e180,
            "bar_low": 3.183734056624e-312,
        },
        {
            "event_type": "close",
            "symbol": "聚丙烯(PP)",
            "order_id": order_id,
            "event_time": "2026-06-04 10:40:29",
            "entry_time": "2026-05-29 01:00:00",
            "exit_time": "2026-05-29 01:00:00",
            "exit_price": 6.518154682897931e-143,
        },
        {
            "event_type": "fill",
            "symbol": "SAUSDT",
            "order_id": "SAUSDT-x",
            "bar_time": "2026-05-29 01:00:00",
        },
    ]
    write_json(state_path, state)
    before_state = state_path.read_text(encoding="utf-8")
    write_json(monitor_path, monitor)
    events_path.parent.mkdir(parents=True, exist_ok=True)
    events_path.write_text("\n".join(json.dumps(item, ensure_ascii=False) for item in events), encoding="utf-8")

    code = module.main(
        [
            "--symbol",
            "PP",
            "--around",
            "2026-05-29 01:00:00",
            "--hours",
            "1",
            "--paper-state-file",
            str(state_path),
            "--monitor-state-file",
            str(monitor_path),
            "--events-file",
            str(events_path),
            "--out",
            str(out_path),
        ]
    )
    payload = json.loads(out_path.read_text(encoding="utf-8"))

    assert code == 0
    assert state_path.read_text(encoding="utf-8") == before_state
    assert payload["summary"]["PPUSDT"]["fills"] == 2
    assert payload["summary"]["PPUSDT"]["closes"] == 1
    assert payload["summary"]["PPUSDT"]["open_positions"] == 1
    assert payload["summary"]["PPUSDT"]["invalid_closes"] == 1
    assert payload["summary"]["PPUSDT"]["suspicious"] >= 3
    assert order_id in payload["monitor"]["ids"]["filled_order_ids"]
    assert all(item["_symbol"] == "PPUSDT" for item in payload["events"])


def test_normalize_symbol_handles_display_and_contract_codes() -> None:
    module = load_module()

    assert module.normalize_symbol("聚丙烯(PP)") == "PPUSDT"
    assert module.normalize_symbol("DCE.pp2609") == "PPUSDT"
    assert module.normalize_symbol("KQ.m@DCE.pp") == "PPUSDT"
    assert module.normalize_symbol("PPUSDT") == "PPUSDT"
