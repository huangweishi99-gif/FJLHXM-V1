from __future__ import annotations

import csv
from pathlib import Path

from services import monitor_domestic


def write_pending(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "order_id",
        "symbol",
        "strategy_id",
        "timeframe",
        "side",
        "trigger_price",
        "stop_price",
        "current_price",
        "distance_pct",
        "status",
        "radar_status",
        "setup",
        "os_camp",
        "latest_time",
        "created_at",
        "valid_until",
        "priority",
        "reason",
        "setup_key",
    ]
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def test_extract_rejects_future_monitor_position() -> None:
    state = {
        "symbols": {
            "LCUSDT": {
                "open_positions": [
                    {
                        "strategy_id": "DS01",
                        "direction": "long",
                        "entry_time": "2117-11-11 04:55:21",
                        "entry_price": 8715.0,
                    }
                ]
            }
        }
    }

    assert monitor_domestic._extract_from_paper_state(state) == []


def test_normalize_position_includes_entry_data_contract(monkeypatch, tmp_path: Path) -> None:
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        """
        {
          "mode": "tq_actual_main_contract",
          "symbols": {
            "LH": {
              "tq_code": "KQ.m@DCE.lh",
              "underlying_symbol": "DCE.lh2609",
              "data_contract": "DCE.lh2609",
              "display_contract": "DCE.lh2609"
            }
          }
        }
        """.strip(),
        encoding="utf-8",
    )
    monkeypatch.setattr(monitor_domestic, "MAIN_CONTRACT_SOURCES_PATHS", (manifest,))

    raw = {
        "strategy_id": "DS01",
        "direction": "short",
        "entry_time": "2026-06-02 06:45:00",
        "entry_price": 12000.0,
        "entry_data_contract": "DCE.lh2608",
        "lots": 1,
        "multiplier": 16,
    }
    out = monitor_domestic._normalize_position(raw, "LHUSDT")
    assert out["entry_data_contract"] == "DCE.lh2608"
    assert out["current_data_contract"] == "DCE.lh2609"
    pending = tmp_path / "pending_orders.csv"
    write_pending(
        pending,
        [
            {
                "order_id": "TESTUSDT-DS01-D1-short",
                "symbol": "TESTUSDT",
                "strategy_id": "DS01",
                "timeframe": "D1",
                "side": "short",
                "trigger_price": "11835",
                "stop_price": "12075",
                "current_price": "12150",
                "distance_pct": "0.02",
                "status": "READY_TRIGGERED",
                "radar_status": "TRIGGERED",
                "setup": "current blue short",
                "os_camp": "blue",
                "latest_time": "2026-06-02 16:00:00",
                "created_at": "2026-06-03 19:26:43",
                "valid_until": "2026-06-05 19:26:43",
                "priority": "10",
                "reason": "test",
                "setup_key": "TESTUSDT|DS01|SHORT",
            }
        ],
    )
    monkeypatch.setattr(monitor_domestic, "PENDING_ORDER_PATHS", (pending,))

    state = {
        "symbols": {
            "TESTUSDT": {
                "open_positions": [
                    {
                        "symbol": "TESTUSDT",
                        "strategy_id": "DS01",
                        "direction": "long",
                        "entry_time": "2026-06-02 06:45:00",
                        "entry_price": 10765.0,
                    }
                ]
            }
        }
    }

    assert monitor_domestic._extract_from_paper_state(state) == []
