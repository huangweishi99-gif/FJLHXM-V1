"""WAdmin MVP: admin overview API."""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services"))

from services.api import main  # noqa: E402


@pytest.fixture()
def client() -> TestClient:
    return TestClient(main.app)


def test_admin_overview_requires_token(client: TestClient, monkeypatch) -> None:
    monkeypatch.setenv("FENGJI_ADMIN_TOKEN", "admin-test-secret")
    res = client.get("/api/v1/admin/overview")
    assert res.status_code == 401


def test_admin_overview_ok(client: TestClient, monkeypatch) -> None:
    monkeypatch.setenv("FENGJI_ADMIN_TOKEN", "admin-test-secret")
    monkeypatch.setattr(
        main,
        "build_admin_overview",
        lambda **_: {
            "auth_users": 2,
            "auth_users_recent": [{"account": "a@test", "plan_id": "free"}],
            "subscription_orders_total": 1,
            "subscription_orders_recent": [],
            "custom_instrument_requests_total": 0,
            "backtest_jobs": {"total": 3, "queued": 1},
            "monitor_ws": {
                "active_total": 1,
                "lifetime": {"deltas_sent": 2},
                "recent_events": [],
            },
        },
    )
    res = client.get(
        "/api/v1/admin/overview",
        headers={"Authorization": "Bearer admin-test-secret"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["auth_users"] == 2
    assert body["auth_users_recent"][0]["account"] == "a@test"
    assert body["service"]["status"] == "ok"


def test_admin_not_configured(client: TestClient, monkeypatch) -> None:
    monkeypatch.delenv("FENGJI_ADMIN_TOKEN", raising=False)
    res = client.get(
        "/api/v1/admin/overview",
        headers={"Authorization": "Bearer anything"},
    )
    assert res.status_code == 503
