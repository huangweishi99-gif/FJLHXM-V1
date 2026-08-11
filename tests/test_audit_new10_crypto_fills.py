from __future__ import annotations

import json
from pathlib import Path

from scripts.audit_new10_crypto_fills import collect_fills_from_events, merge_positions


def test_collect_fills_from_events(tmp_path: Path) -> None:
    events = tmp_path / "events.jsonl"
    events.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "event_type": "fill",
                        "order_id": "OPUSDT-DS07-H1-short-abc",
                        "symbol": "OPUSDT",
                        "strategy_id": "DS07",
                        "side": "short",
                        "fill_price": 0.0985,
                        "trigger_price": 0.0996,
                        "stop_price": 0.1017,
                        "bar_time": "2026-06-23 14:34:08",
                    }
                ),
                json.dumps({"event_type": "cancel", "order_id": "OTHER"}),
            ]
        ),
        encoding="utf-8",
    )
    rows = collect_fills_from_events(events, {"OPUSDT-DS07-H1-short-abc"})
    assert len(rows) == 1
    assert rows[0]["symbol"] == "OPUSDT"
    assert rows[0]["strategy_id"] == "DS07"
    assert rows[0]["entry_price"] == 0.0985


def test_merge_positions_dedupes_by_order_id() -> None:
    a = [{"order_id": "x", "symbol": "PEPEUSDT", "strategy_id": "DS05"}]
    b = [{"order_id": "x", "symbol": "PEPEUSDT", "strategy_id": "DS05", "status": "CLOSED_OR_FILLED"}]
    merged = merge_positions(a, b)
    assert len(merged) == 1
    assert merged[0]["status"] == "CLOSED_OR_FILLED"
