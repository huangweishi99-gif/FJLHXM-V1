from __future__ import annotations

import csv
from pathlib import Path

from services import monitor_ledger


def test_load_recent_ledger_rejections_from_radar_and_pending(tmp_path: Path, monkeypatch) -> None:
    radar_path = tmp_path / "radar.csv"
    pending_path = tmp_path / "pending_orders.csv"
    radar_path.write_text(
        "symbol,strategy_id,timeframe,side,status,setup,current_price,trigger_price,distance_pct,stop_price,os_camp,latest_time,score,reason,setup_key\n"
        "BNBUSDT,DS01,D1,long,BLOCKED_OS_INCOMPLETE,,610,610,0,600,red,2026-06-07 00:00:00,1,missing_red_ext,setup1\n"
        "ETHUSDT,DS03,D1,long,PENDING,,3000,3000,0,2900,blue,2026-06-08 00:00:00,2,,setup2\n",
        encoding="utf-8",
    )
    with pending_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=[
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
            ],
        )
        writer.writeheader()
        writer.writerow(
            {
                "order_id": "LC-1",
                "symbol": "LCUSDT",
                "strategy_id": "DS09",
                "timeframe": "D1",
                "side": "long",
                "trigger_price": "100",
                "stop_price": "90",
                "current_price": "101",
                "distance_pct": "1",
                "status": "CANCELLED",
                "radar_status": "CANCELLED",
                "setup": "test",
                "os_camp": "blue",
                "latest_time": "2026-06-09 10:00:00",
                "created_at": "2026-06-09 09:00:00",
                "valid_until": "",
                "priority": "1",
                "reason": "risk blocked",
                "setup_key": "k1",
            }
        )

    monkeypatch.setattr(
        monitor_ledger,
        "load_latest_radar",
        lambda limit=80: {
            "source": "radar_csv",
            "source_path": str(radar_path),
            "rows": [
                {
                    "symbol": "BNBUSDT",
                    "strategy_id": "DS01",
                    "status": "BLOCKED_OS_INCOMPLETE",
                    "reason": "missing_red_ext",
                    "latest_time": "2026-06-07 00:00:00",
                    "market": "CRYPTO",
                },
                {
                    "symbol": "ETHUSDT",
                    "strategy_id": "DS03",
                    "status": "PENDING",
                    "reason": "",
                    "latest_time": "2026-06-08 00:00:00",
                    "market": "CRYPTO",
                },
            ],
        },
    )
    monkeypatch.setattr(monitor_ledger, "PENDING_ORDER_PATHS", (pending_path,))

    payload = monitor_ledger.load_recent_ledger_rejections(limit=10)
    assert payload["mode"] == "read_only_ledger"
    assert payload["count"] == 2
    kinds = {item["kind"] for item in payload["items"]}
    assert kinds == {"radar_blocked", "pending_rejected"}
    statuses = {item["status"] for item in payload["items"]}
    assert "BLOCKED_OS_INCOMPLETE" in statuses
    assert "CANCELLED" in statuses
