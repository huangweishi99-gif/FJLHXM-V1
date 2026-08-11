"""Monitor REST polling gate tests."""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("FENGJI_AUTH_ALLOW_DEV_SECRET", "1")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services"))

from auth_service import create_access_token  # noqa: E402
from monitor_polling_gate import enforce_monitor_polling, reset_monitor_polling_state_for_tests  # noqa: E402
from services.api import main  # noqa: E402


@pytest.fixture()
def client() -> TestClient:
    reset_monitor_polling_state_for_tests()
    return TestClient(main.app)


def test_enforce_monitor_polling_allows_burst_within_window() -> None:
    reset_monitor_polling_state_for_tests()
    first = enforce_monitor_polling(user_key="u1", plan="free", now=1000.0)
    second = enforce_monitor_polling(user_key="u1", plan="free", now=1005.0)
    assert first["allowed"] is True
    assert second["allowed"] is True
    assert second["mode"] == "polling_burst"


def test_enforce_monitor_polling_blocks_before_interval() -> None:
    reset_monitor_polling_state_for_tests()
    enforce_monitor_polling(user_key="u1", plan="standard", now=1000.0)
    blocked = enforce_monitor_polling(user_key="u1", plan="standard", now=1030.0)
    assert blocked["allowed"] is False
    assert blocked["min_interval_seconds"] == 60
    assert blocked["retry_after_seconds"] == pytest.approx(30.0)


def test_latest_opens_includes_monitor_policy(client: TestClient) -> None:
    res = client.get("/api/v1/monitor/domestic/latest-opens")
    assert res.status_code == 200
    body = res.json()
    assert body["monitor_policy"]["plan"] == "free"
    assert body["monitor_policy"]["min_interval_seconds"] == 900


def test_latest_opens_throttles_after_burst_window(client: TestClient) -> None:
    from monitor_polling_gate import _MONITOR_POLL_STATE

    assert client.get("/api/v1/monitor/domestic/latest-opens").status_code == 200
    for state in _MONITOR_POLL_STATE.values():
        state["burst_until"] = 0.0
    res = client.get("/api/v1/monitor/domestic/latest-opens")
    assert res.status_code == 429
    assert "Retry-After" in res.headers
    assert "too frequent" in res.json()["detail"]


def test_overseas_latest_opens_includes_monitor_policy(client: TestClient) -> None:
    res = client.get("/api/v1/monitor/overseas/latest-opens")
    assert res.status_code == 200
    body = res.json()
    assert body["monitor_policy"]["plan"] == "free"
    assert body.get("market_scope") == "CRYPTO"
    assert "positions" in body


def test_build_monitor_snapshot_merges_domestic_and_overseas(monkeypatch) -> None:
    monkeypatch.setattr(
        main,
        "load_latest_opens",
        lambda: {
            "source": "paper_state",
            "positions": [{"symbol": "PG", "market": "FUTURES", "entry_time": "2026-06-10 10:00:00"}],
        },
    )
    monkeypatch.setattr(
        main,
        "load_overseas_latest_opens",
        lambda: {
            "source": "paper_state",
            "positions": [{"symbol": "BNBUSDT", "market": "CRYPTO", "entry_time": "2026-06-11 08:00:00"}],
        },
    )
    snap = main.build_monitor_snapshot(user_id="", plan="free")
    symbols = {p["symbol"] for p in snap["payload"]["positions"]}
    assert symbols == {"PG", "BNBUSDT"}
    assert snap["sources"]["domestic_positions"] == "paper_state"
    assert snap["sources"]["overseas_positions"] == "paper_state"


def test_latest_opens_jwt_standard_interval(client: TestClient, monkeypatch) -> None:
    user = {
        "id": "poll-user-1",
        "account": "poll@test.com",
        "password_hash": "x",
        "plan_id": "standard",
        "plan_expires_at": "2026-12-31T00:00:00+00:00",
        "created_at": "2026-06-01T00:00:00+00:00",
    }
    monkeypatch.setattr(main, "get_user_by_id", lambda uid: user if uid == user["id"] else None)
    token = create_access_token(user_id=user["id"], account=user["account"], plan="standard")
    res = client.get("/api/v1/monitor/domestic/latest-opens", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    assert res.json()["monitor_policy"]["plan"] == "standard"
    assert res.json()["monitor_policy"]["min_interval_seconds"] == 60
