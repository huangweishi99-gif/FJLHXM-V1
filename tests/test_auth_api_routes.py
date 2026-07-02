"""W17-prod: HTTP route smoke for auth endpoints (DB mocked)."""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("FENGJI_AUTH_ALLOW_DEV_SECRET", "1")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services"))

from auth_service import create_access_token, create_refresh_token  # noqa: E402
from services.api import main  # noqa: E402


@pytest.fixture()
def client() -> TestClient:
    return TestClient(main.app)


def _fake_user(account: str = "smoke@test.com", plan_id: str = "free") -> dict:
    return {
        "id": "user-smoke-001",
        "account": account,
        "password_hash": "pbkdf2_sha256$120000$00$00",
        "plan_id": plan_id,
        "plan_expires_at": "2026-12-31T00:00:00+00:00",
        "created_at": "2026-06-08T00:00:00+00:00",
        "updated_at": "2026-06-08T00:00:00+00:00",
    }


def test_auth_register_route(client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr(main, "create_user", lambda **_: _fake_user("new@test.com"))

    res = client.post("/api/v1/auth/register", json={"account": "new@test.com", "password": "secret12"})
    assert res.status_code == 200
    body = res.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]
    assert body["refresh_token"]
    assert body["user"]["account"] == "new@test.com"


def test_auth_login_route(client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr(main, "authenticate_user", lambda **_: _fake_user("login@test.com"))

    res = client.post("/api/v1/auth/login", json={"account": "login@test.com", "password": "secret12"})
    assert res.status_code == 200
    assert res.json()["user"]["account"] == "login@test.com"


def test_auth_login_invalid_credentials(client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr(main, "authenticate_user", lambda **_: None)

    res = client.post("/api/v1/auth/login", json={"account": "bad@test.com", "password": "wrong12"})
    assert res.status_code == 401


def test_auth_refresh_route(client: TestClient, monkeypatch) -> None:
    user = _fake_user("refresh@test.com")
    refresh = create_refresh_token(user_id=user["id"])
    monkeypatch.setattr(main, "get_user_by_id", lambda uid: user if uid == user["id"] else None)

    res = client.post("/api/v1/auth/refresh", json={"refresh_token": refresh})
    assert res.status_code == 200
    assert res.json()["access_token"]


def test_auth_me_requires_bearer(client: TestClient) -> None:
    res = client.get("/api/v1/auth/me")
    assert res.status_code == 401


def test_auth_me_with_access_token(client: TestClient, monkeypatch) -> None:
    user = _fake_user("me@test.com", plan_id="pro")
    token = create_access_token(user_id=user["id"], account=user["account"], plan="pro")
    monkeypatch.setattr(main, "get_user_by_id", lambda uid: user if uid == user["id"] else None)

    res = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    body = res.json()
    assert body["account"] == "me@test.com"
    assert body["plan"] == "pro"
