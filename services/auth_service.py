"""W17-prod MVP: JWT auth helpers."""
from __future__ import annotations

import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt

DEFAULT_ACCESS_MINUTES = 60
DEFAULT_REFRESH_DAYS = 14


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def jwt_secret() -> str:
    secret = os.getenv("FENGJI_JWT_SECRET", "").strip()
    if secret:
        return secret
    if os.getenv("FENGJI_AUTH_ALLOW_DEV_SECRET", "").lower() in {"1", "true", "yes"}:
        return "fengji-dev-only-change-me"
    raise RuntimeError("FENGJI_JWT_SECRET is required for auth")


def normalize_plan(plan: str | None) -> str:
    key = str(plan or "free").strip().lower()
    return key or "free"


def create_access_token(*, user_id: str, account: str, plan: str) -> str:
    now = _utcnow()
    payload = {
        "sub": user_id,
        "account": account,
        "plan": normalize_plan(plan),
        "type": "access",
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=DEFAULT_ACCESS_MINUTES)).timestamp()),
    }
    return jwt.encode(payload, jwt_secret(), algorithm="HS256")


def create_refresh_token(*, user_id: str) -> str:
    now = _utcnow()
    payload = {
        "sub": user_id,
        "type": "refresh",
        "jti": uuid.uuid4().hex,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(days=DEFAULT_REFRESH_DAYS)).timestamp()),
    }
    return jwt.encode(payload, jwt_secret(), algorithm="HS256")


def decode_token(token: str, *, expected_type: str | None = None) -> dict[str, Any]:
    payload = jwt.decode(token, jwt_secret(), algorithms=["HS256"])
    if expected_type and payload.get("type") != expected_type:
        raise jwt.InvalidTokenError(f"unexpected token type: {payload.get('type')}")
    return payload


def user_public_view(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row["id"],
        "account": row["account"],
        "plan": normalize_plan(row.get("plan_id")),
        "plan_expires_at": row.get("plan_expires_at"),
        "created_at": row.get("created_at"),
    }


def auth_response_from_user(row: dict[str, Any]) -> dict[str, Any]:
    user_id = str(row["id"])
    account = str(row["account"])
    plan = normalize_plan(row.get("plan_id"))
    return {
        "access_token": create_access_token(user_id=user_id, account=account, plan=plan),
        "refresh_token": create_refresh_token(user_id=user_id),
        "token_type": "bearer",
        "expires_in": DEFAULT_ACCESS_MINUTES * 60,
        "user": user_public_view(row),
    }
