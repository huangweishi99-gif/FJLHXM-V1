from __future__ import annotations

import csv
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services"))

from db.context_queries import attach_radar_signal_tiers, radar_row_to_score_input  # noqa: E402
import radar_snapshot  # noqa: E402
from services.api import main  # noqa: E402
from fastapi.testclient import TestClient


def write_radar_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "symbol",
        "strategy_id",
        "timeframe",
        "side",
        "status",
        "setup",
        "current_price",
        "trigger_price",
        "distance_pct",
        "stop_price",
        "os_camp",
        "latest_time",
        "score",
        "reason",
        "setup_key",
    ]
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def test_radar_row_to_score_input_maps_red_camp() -> None:
    snap = radar_row_to_score_input(
        {
            "symbol": "RBUSDT",
            "strategy_id": "ds01",
            "os_camp": "red",
            "setup_key": "",
        }
    )
    assert snap["strategy_id"] == "DS01"
    assert snap["market"] == "FUTURES"
    assert snap["camp"] == 1
    assert snap["camp_confirmed"] == 1


def test_load_latest_radar_reads_csv(monkeypatch, tmp_path: Path) -> None:
    radar = tmp_path / "radar.csv"
    write_radar_csv(
        radar,
        [
            {
                "symbol": "BTCUSDT",
                "strategy_id": "DS03",
                "timeframe": "D1",
                "side": "long",
                "status": "PENDING",
                "setup": "test",
                "current_price": "100",
                "trigger_price": "101",
                "distance_pct": "0.01",
                "stop_price": "95",
                "os_camp": "red",
                "latest_time": "2026-06-10 00:00:00",
                "score": "2.5",
                "reason": "ok",
                "setup_key": "BTC|DS03|long|101",
            }
        ],
    )
    monkeypatch.setattr(radar_snapshot, "RADAR_PATHS", (radar,))
    payload = radar_snapshot.load_latest_radar(limit=10)
    assert payload["source"] == "radar_csv"
    assert payload["count"] == 1
    assert payload["rows"][0]["symbol"] == "BTCUSDT"
    assert payload["rows"][0]["market"] == "CRYPTO"


def test_attach_radar_signal_tiers_returns_tier_fields() -> None:
    try:
        rows = attach_radar_signal_tiers(
            [
                {
                    "symbol": "000021",
                    "strategy_id": "DS01",
                    "market": "A_STOCK",
                    "os_camp": "red",
                    "status": "PENDING",
                }
            ]
        )
    except Exception as exc:
        import pytest

        pytest.skip(f"PG unavailable: {exc}")
    assert rows[0]["tier_mode"] == "read_only_bucket_lookup"
    assert rows[0]["signal_tier"] in {"STRONG", "MEDIUM", "WEAK", "INSUFFICIENT_DATA"}


def test_monitor_radar_latest_api(monkeypatch, tmp_path: Path) -> None:
    radar = tmp_path / "radar.csv"
    write_radar_csv(
        radar,
        [
            {
                "symbol": "SOLUSDT",
                "strategy_id": "DS01",
                "timeframe": "D1",
                "side": "long",
                "status": "PENDING",
                "setup": "test",
                "current_price": "150",
                "trigger_price": "151",
                "distance_pct": "0.01",
                "stop_price": "140",
                "os_camp": "blue",
                "latest_time": "2026-06-10 00:00:00",
                "score": "3",
                "reason": "ok",
                "setup_key": "",
            },
            {
                "symbol": "ETHUSDT",
                "strategy_id": "DS02",
                "timeframe": "D1",
                "side": "short",
                "status": "BLOCKED",
                "setup": "blocked",
                "current_price": "3000",
                "trigger_price": "2900",
                "distance_pct": "0.03",
                "stop_price": "3100",
                "os_camp": "red",
                "latest_time": "2026-06-10 00:00:00",
                "score": "1",
                "reason": "blocked",
                "setup_key": "",
            },
        ],
    )
    monkeypatch.setattr(radar_snapshot, "RADAR_PATHS", (radar,))

    client = TestClient(main.app)
    res = client.get("/api/v1/monitor/radar/latest?status=PENDING&include_tier=false")
    assert res.status_code == 200
    body = res.json()
    assert body["mode"] == "read_only_radar"
    assert body["count"] == 1
    assert body["rows"][0]["symbol"] == "SOLUSDT"
    assert "tier_disclaimer" in body
