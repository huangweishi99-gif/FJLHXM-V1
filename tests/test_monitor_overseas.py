from __future__ import annotations

import csv
import json
from pathlib import Path

from services import monitor_overseas


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


def test_extract_crypto_open_position(monkeypatch) -> None:
    # Isolate from live pending_orders.csv: a real BNBUSDT long ACTIVE order on
    # disk would make the short position below look contradicted and be filtered.
    monkeypatch.setattr(monitor_overseas, "PENDING_ORDER_PATHS", (None,))
    state = {
        "symbols": {
            "BNBUSDT": {
                "open_position": {
                    "trade_key": "BNBUSDT-DS03-D1-short",
                    "symbol": "BNBUSDT",
                    "strategy_id": "DS03",
                    "direction": "short",
                    "entry_time": "2026-06-11 08:00:00",
                    "entry_price": 602.79,
                    "initial_stop": 618.5,
                    "margin": 200.0,
                    "leverage": 2.0,
                }
            }
        }
    }

    positions = monitor_overseas._extract_from_paper_state(state)
    assert len(positions) == 1
    pos = positions[0]
    assert pos["market"] == "CRYPTO"
    assert pos["symbol"] == "BNBUSDT"
    assert pos["direction"] == "short"
    assert pos["paper_origin"] == "overseas"
    assert pos["current_stop"] == 618.5


def test_extract_rejects_future_monitor_position() -> None:
    state = {
        "symbols": {
            "IOUSDT": {
                "open_position": {
                    "strategy_id": "DS01",
                    "direction": "long",
                    "entry_time": "2117-11-11 04:55:21",
                    "entry_price": 3.21,
                }
            }
        }
    }

    assert monitor_overseas._extract_from_paper_state(state) == []


def test_load_latest_opens_from_tmp_state(monkeypatch, tmp_path: Path) -> None:
    state_path = tmp_path / "overseas_paper_state.json"
    state_path.write_text(
        json.dumps(
            {
                "symbols": {
                    "ETHUSDT": {
                        "open_position": {
                            "symbol": "ETHUSDT",
                            "strategy_id": "DS01",
                            "direction": "long",
                            "entry_time": "2026-06-10 12:00:00",
                            "entry_price": 2500.0,
                            "initial_stop": 2400.0,
                        }
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(monitor_overseas, "ROOT", tmp_path)
    monkeypatch.setenv("OVERSEAS_PAPER_STATE_PATH", str(state_path))
    monkeypatch.setattr(monitor_overseas, "PENDING_ORDER_PATHS", (None,))

    payload = monitor_overseas.load_latest_opens()
    assert payload["source"] == "paper_state"
    assert payload["market_scope"] == "CRYPTO"
    assert len(payload["positions"]) == 1
    assert payload["positions"][0]["symbol"] == "ETHUSDT"


def test_extract_filters_position_contradicted_by_current_pending(monkeypatch, tmp_path: Path) -> None:
    pending = tmp_path / "pending_orders.csv"
    write_pending(
        pending,
        [
            {
                "order_id": "BNBUSDT-DS01-D1-long",
                "symbol": "BNBUSDT",
                "strategy_id": "DS01",
                "timeframe": "D1",
                "side": "long",
                "trigger_price": "610",
                "stop_price": "590",
                "current_price": "605",
                "distance_pct": "0.01",
                "status": "READY_TRIGGERED",
                "radar_status": "TRIGGERED",
                "setup": "current red long",
                "os_camp": "red",
                "latest_time": "2026-06-12 16:00:00",
                "created_at": "2026-06-12 19:26:43",
                "valid_until": "2026-06-14 19:26:43",
                "priority": "10",
                "reason": "test",
                "setup_key": "BNBUSDT|DS01|LONG",
            }
        ],
    )
    monkeypatch.setattr(monitor_overseas, "PENDING_ORDER_PATHS", (pending,))

    state = {
        "symbols": {
            "BNBUSDT": {
                "open_position": {
                    "symbol": "BNBUSDT",
                    "strategy_id": "DS03",
                    "direction": "short",
                    "entry_time": "2026-06-11 08:00:00",
                    "entry_price": 602.79,
                }
            }
        }
    }

    assert monitor_overseas._extract_from_paper_state(state) == []
