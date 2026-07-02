"""W17-prod Feature Gate: JWT plan overrides client plan_id on gated routes."""
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
from services.api import main  # noqa: E402


@pytest.fixture()
def client() -> TestClient:
    return TestClient(main.app)


def _fake_user(*, plan_id: str = "free", user_id: str = "user-gate-001") -> dict:
    return {
        "id": user_id,
        "account": "gate@test.com",
        "password_hash": "pbkdf2_sha256$120000$00$00",
        "plan_id": plan_id,
        "plan_expires_at": "2026-12-31T00:00:00+00:00",
        "created_at": "2026-06-08T00:00:00+00:00",
        "updated_at": "2026-06-08T00:00:00+00:00",
    }


def _auth_header(user: dict) -> dict[str, str]:
    token = create_access_token(
        user_id=user["id"],
        account=user["account"],
        plan=user["plan_id"],
    )
    return {"Authorization": f"Bearer {token}"}


def test_backtest_free_jwt_rejects_five_years(client: TestClient, monkeypatch) -> None:
    user = _fake_user(plan_id="free")
    monkeypatch.setattr(main, "get_user_by_id", lambda uid: user if uid == user["id"] else None)
    monkeypatch.setattr(main, "resolve_csv", lambda *args, **kwargs: Path("dummy.csv"))

    res = client.post(
        "/api/v1/backtests",
        headers=_auth_header(user),
        json={
            "market": "CRYPTO",
            "symbol": "BTCUSDT",
            "strategy_id": "DS01",
            "years": 5,
        },
    )
    assert res.status_code == 403
    assert "5-year" in res.json()["detail"] or "5" in res.json()["detail"]


def test_backtest_free_jwt_rejects_total_strategy(client: TestClient, monkeypatch) -> None:
    user = _fake_user(plan_id="free")
    monkeypatch.setattr(main, "get_user_by_id", lambda uid: user if uid == user["id"] else None)
    monkeypatch.setattr(main, "resolve_csv", lambda *args, **kwargs: Path("dummy.csv"))

    res = client.post(
        "/api/v1/backtests",
        headers=_auth_header(user),
        json={
            "market": "CRYPTO",
            "symbol": "BTCUSDT",
            "strategy_id": "TOTAL",
            "years": 1,
        },
    )
    assert res.status_code == 403
    assert "TOTAL" in res.json()["detail"]


def test_backtest_pro_jwt_allows_five_years(client: TestClient, monkeypatch) -> None:
    user = _fake_user(plan_id="pro")
    job = {"id": "job-gate-1", "status": "queued"}
    monkeypatch.setattr(main, "get_user_by_id", lambda uid: user if uid == user["id"] else None)
    monkeypatch.setattr(main, "resolve_csv", lambda *args, **kwargs: Path("dummy.csv"))
    monkeypatch.setattr(main, "create_backtest_job", lambda **kwargs: dict(job))
    monkeypatch.setattr(main, "run_backtest_job_once", lambda job_id: None)

    res = client.post(
        "/api/v1/backtests",
        headers=_auth_header(user),
        json={
            "market": "CRYPTO",
            "symbol": "BTCUSDT",
            "strategy_id": "TOTAL",
            "years": 5,
        },
    )
    assert res.status_code == 202
    assert res.json()["id"] == "job-gate-1"


def test_custom_request_jwt_plan_overrides_forged_body_plan(client: TestClient, monkeypatch) -> None:
    user = _fake_user(plan_id="free")
    monkeypatch.setattr(main, "get_user_by_id", lambda uid: user if uid == user["id"] else None)

    res = client.post(
        "/api/v1/custom-instruments/request",
        headers=_auth_header(user),
        json={
            "market": "CRYPTO",
            "symbol": "ETHUSDT",
            "strategies": ["DS01"],
            "years": 1,
            "user_id": "forged-user",
            "plan_id": "pro",
        },
    )
    assert res.status_code == 403
    assert "free plan" in res.json()["detail"]


def test_custom_request_without_jwt_rejected(client: TestClient) -> None:
    res = client.post(
        "/api/v1/custom-instruments/request",
        json={
            "market": "CRYPTO",
            "symbol": "ETHUSDT",
            "strategies": ["DS01"],
            "years": 1,
            "user_id": "demo-user",
            "plan_id": "pro",
        },
    )
    assert res.status_code == 401
    assert "login required" in res.json()["detail"]


def test_backtest_expired_jwt_rejected(client: TestClient, monkeypatch) -> None:
    user = _fake_user(plan_id="standard")
    user["plan_expires_at"] = "2026-06-01T00:00:00+00:00"
    monkeypatch.setattr(main, "get_user_by_id", lambda uid: user if uid == user["id"] else None)
    monkeypatch.setattr(main, "resolve_csv", lambda *args, **kwargs: Path("dummy.csv"))

    res = client.post(
        "/api/v1/backtests",
        headers=_auth_header(user),
        json={
            "market": "CRYPTO",
            "symbol": "BTCUSDT",
            "strategy_id": "DS01",
            "years": 1,
        },
    )
    assert res.status_code == 403
    assert "expired" in res.json()["detail"]


def test_custom_request_uses_jwt_user_id_not_body(client: TestClient, monkeypatch) -> None:
    user = _fake_user(plan_id="standard", user_id="jwt-user-99")
    captured: dict = {}
    job = {"id": "job-gate-2", "status": "queued"}
    monkeypatch.setattr(main, "get_user_by_id", lambda uid: user if uid == user["id"] else None)
    monkeypatch.setattr(main, "resolve_csv", lambda *args, **kwargs: Path("dummy.csv"))
    monkeypatch.setattr(main, "missing_crypto_timeframes", lambda symbol: [])
    monkeypatch.setattr(
        main,
        "check_custom_request_quota",
        lambda uid, plan: captured.update({"user_id": uid, "plan": plan}) or {"allowed": True, "used": 0, "limit": 3},
    )
    monkeypatch.setattr(main, "create_backtest_job", lambda **kwargs: dict(job))
    monkeypatch.setattr(main, "run_backtest_job_once", lambda job_id: None)
    monkeypatch.setattr(
        main,
        "create_custom_instrument_request",
        lambda **kwargs: {"id": "req-gate-1", "status": "backtesting", **kwargs},
    )
    monkeypatch.setattr(main, "get_custom_instrument_request", lambda _: {"id": "req-gate-1", "status": "queued"})

    res = client.post(
        "/api/v1/custom-instruments/request",
        headers=_auth_header(user),
        json={
            "market": "CRYPTO",
            "symbol": "ETHUSDT",
            "strategies": ["DS01"],
            "years": 3,
            "user_id": "forged-user",
            "plan_id": "pro",
        },
    )
    assert res.status_code == 202
    assert captured["user_id"] == "jwt-user-99"
    assert captured["plan"] == "standard"
