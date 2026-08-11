"""W17-prod: subscription manual-confirm, redeem, webhook routes."""
from __future__ import annotations

import hashlib
import hmac
import json
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


def _fake_user(*, plan_id: str = "free", user_id: str = "user-sub-001") -> dict:
    return {
        "id": user_id,
        "account": "sub@test.com",
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


def test_payment_config_endpoint(client: TestClient, monkeypatch) -> None:
    monkeypatch.delenv("FENGJI_ALLOW_MANUAL_SUBSCRIPTION_CONFIRM", raising=False)
    monkeypatch.delenv("FENGJI_PAYMENT_WEBHOOK_SECRET", raising=False)
    monkeypatch.delenv("FENGJI_SUBSCRIPTION_REDEEM_CODES", raising=False)

    res = client.get("/api/v1/subscriptions/payment-config")
    assert res.status_code == 200
    body = res.json()
    assert body["version"] == 1
    assert body["confirm_button_mode"] == "demo_only"
    assert body["channels"]["payment_webhook"] is False
    assert body["pricing"]["standard"]["amount_yuan"] == 99
    assert body["pricing"]["pro"]["amount_yuan"] == 299
    assert "env_hints" in body


def test_manual_confirm_disabled_without_env(client: TestClient, monkeypatch) -> None:
    user = _fake_user()
    monkeypatch.setattr(main, "get_user_by_id", lambda uid: user if uid == user["id"] else None)
    monkeypatch.delenv("FENGJI_ALLOW_MANUAL_SUBSCRIPTION_CONFIRM", raising=False)

    res = client.post(
        "/api/v1/subscriptions/manual-confirm",
        headers=_auth_header(user),
        json={"plan": "standard"},
    )
    assert res.status_code == 503


def test_manual_confirm_upgrades_plan(client: TestClient, monkeypatch) -> None:
    user = _fake_user(plan_id="free")
    updated = {**user, "plan_id": "standard", "plan_expires_at": "2027-01-08T00:00:00+00:00"}
    order = {"id": "ord-1", "plan_id": "standard", "channel": "personal_wechat_qr", "status": "active"}

    monkeypatch.setenv("FENGJI_ALLOW_MANUAL_SUBSCRIPTION_CONFIRM", "1")
    monkeypatch.setattr(main, "get_user_by_id", lambda uid: user if uid == user["id"] else None)
    monkeypatch.setattr(main, "activate_user_subscription", lambda **_: (updated, order))

    res = client.post(
        "/api/v1/subscriptions/manual-confirm",
        headers=_auth_header(user),
        json={"plan": "standard"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["user"]["plan"] == "standard"
    assert body["subscription_order"]["channel"] == "personal_wechat_qr"


def test_manual_confirm_blocks_pro_to_standard(client: TestClient, monkeypatch) -> None:
    user = _fake_user(plan_id="pro")
    monkeypatch.setenv("FENGJI_ALLOW_MANUAL_SUBSCRIPTION_CONFIRM", "1")
    monkeypatch.setattr(main, "get_user_by_id", lambda uid: user if uid == user["id"] else None)

    res = client.post(
        "/api/v1/subscriptions/manual-confirm",
        headers=_auth_header(user),
        json={"plan": "standard"},
    )
    assert res.status_code == 400
    assert "downgrade" in res.json()["detail"]


def test_redeem_code_activates_plan(client: TestClient, monkeypatch) -> None:
    user = _fake_user(plan_id="free")
    updated = {**user, "plan_id": "pro", "plan_expires_at": "2027-01-08T00:00:00+00:00"}
    order = {"id": "ord-2", "plan_id": "pro", "channel": "redeem_code", "status": "active"}

    monkeypatch.setenv("FENGJI_SUBSCRIPTION_REDEEM_CODES", "pro:TEST-PRO-2026")
    monkeypatch.setattr(main, "get_user_by_id", lambda uid: user if uid == user["id"] else None)
    monkeypatch.setattr(main, "activate_user_subscription", lambda **_: (updated, order))

    res = client.post(
        "/api/v1/subscriptions/redeem",
        headers=_auth_header(user),
        json={"code": "test-pro-2026"},
    )
    assert res.status_code == 200
    assert res.json()["user"]["plan"] == "pro"


def test_webhook_requires_signature(client: TestClient, monkeypatch) -> None:
    monkeypatch.setenv("FENGJI_PAYMENT_WEBHOOK_SECRET", "webhook-test-secret")
    body = json.dumps({"user_id": "u1", "plan": "standard"}).encode("utf-8")
    bad_sig = hmac.new(b"wrong", body, hashlib.sha256).hexdigest()

    res = client.post(
        "/api/v1/webhooks/subscription",
        content=body,
        headers={"Content-Type": "application/json", "X-FengJi-Signature": bad_sig},
    )
    assert res.status_code == 401


def test_webhook_activates_with_valid_signature(client: TestClient, monkeypatch) -> None:
    secret = "webhook-test-secret"
    user = _fake_user(plan_id="free", user_id="user-wh-1")
    updated = {**user, "plan_id": "standard"}
    order = {"id": "ord-3", "channel": "payment_webhook", "status": "active"}

    monkeypatch.setenv("FENGJI_PAYMENT_WEBHOOK_SECRET", secret)
    monkeypatch.setattr(main, "get_user_by_id", lambda uid: user if uid == user["id"] else None)
    monkeypatch.setattr(main, "activate_user_subscription", lambda **_: (updated, order))

    payload = {"user_id": user["id"], "plan": "standard", "transaction_id": "tx-001"}
    body = json.dumps(payload).encode("utf-8")
    sig = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()

    res = client.post(
        "/api/v1/webhooks/subscription",
        content=body,
        headers={"Content-Type": "application/json", "X-FengJi-Signature": sig},
    )
    assert res.status_code == 200
    assert res.json()["plan"] == "standard"
