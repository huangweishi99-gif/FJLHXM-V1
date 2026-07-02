from __future__ import annotations

import os

import pytest

os.environ.setdefault("FENGJI_AUTH_ALLOW_DEV_SECRET", "1")

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services"))

from auth_service import auth_response_from_user, create_access_token, decode_token
from db import auth_users


def test_auth_password_hash_roundtrip() -> None:
    encoded = auth_users.hash_password("secret123")
    assert auth_users.verify_password("secret123", encoded)
    assert not auth_users.verify_password("wrong", encoded)


def test_jwt_access_token_decode() -> None:
    token = create_access_token(user_id="u1", account="demo@test.com", plan="pro")
    payload = decode_token(token, expected_type="access")
    assert payload["sub"] == "u1"
    assert payload["plan"] == "pro"


def test_auth_response_shape() -> None:
    row = {
        "id": "u1",
        "account": "demo@test.com",
        "plan_id": "free",
        "plan_expires_at": None,
        "created_at": "2026-06-08T00:00:00+00:00",
    }
    payload = auth_response_from_user(row)
    assert payload["token_type"] == "bearer"
    assert payload["user"]["account"] == "demo@test.com"
    assert payload["access_token"]


def test_resolve_monitor_identity_from_token(monkeypatch) -> None:
    from services.api import main

    user = {
        "id": "jwt-user",
        "account": "jwt@test.com",
        "plan_id": "pro",
        "plan_expires_at": "2026-12-31T00:00:00+00:00",
        "created_at": "2026-06-08T00:00:00+00:00",
    }
    monkeypatch.setattr(main, "get_user_by_id", lambda uid: user if uid == user["id"] else None)
    token = create_access_token(user_id="jwt-user", account="jwt@test.com", plan="free")
    user_id, plan, auth_user = main.resolve_monitor_identity("", "free", token)
    assert user_id == "jwt-user"
    assert plan == "pro"
    assert auth_user is not None


def test_monitor_ws_accepts_jwt_identity(monkeypatch) -> None:
    from services.api import main

    user = {
        "id": "jwt-user",
        "account": "jwt@test.com",
        "plan_id": "pro",
        "plan_expires_at": "2026-12-31T00:00:00+00:00",
        "created_at": "2026-06-08T00:00:00+00:00",
    }
    monkeypatch.setattr(main, "get_user_by_id", lambda uid: user if uid == user["id"] else None)
    _patch = __import__("tests.test_monitor_websocket", fromlist=["_patch_monitor_sources"])._patch_monitor_sources
    _patch(monkeypatch)
    token = create_access_token(user_id="jwt-user", account="jwt@test.com", plan="pro")

    async def run() -> None:
        ws = __import__("tests.test_monitor_websocket", fromlist=["FakeWebSocket"]).FakeWebSocket(disconnect_after_messages=1)
        await main.monitor_websocket(
            ws,
            user_id="",
            plan="free",
            access_token=token,
            interval_seconds=0.01,
        )
        assert ws.accepted
        assert ws.messages[0]["type"] in {"monitor.snapshot.v1", "monitor.heartbeat.v1"}

    import asyncio

    asyncio.run(run())
