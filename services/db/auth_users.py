from __future__ import annotations

import hashlib
import hmac
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from db.models import AuthUser
from db.session import get_engine

PLAN_TRIAL_DAYS = 7


def normalize_account(account: str) -> str:
    return str(account or "").strip().lower()


def normalize_plan(plan: str | None) -> str:
    key = str(plan or "free").strip().lower()
    return key or "free"


def hash_password(password: str, *, salt: bytes | None = None) -> str:
    raw_salt = salt or secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), raw_salt, 120_000)
    return f"pbkdf2_sha256$120000${raw_salt.hex()}${digest.hex()}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        scheme, iterations, salt_hex, digest_hex = encoded.split("$", 3)
        if scheme != "pbkdf2_sha256":
            return False
        salt = bytes.fromhex(salt_hex)
        expected = bytes.fromhex(digest_hex)
        actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, int(iterations))
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False


def _user_to_dict(user: AuthUser) -> dict[str, Any]:
    return {
        "id": user.id,
        "account": user.account,
        "password_hash": user.password_hash,
        "plan_id": user.plan_id,
        "plan_expires_at": user.plan_expires_at.isoformat() if user.plan_expires_at else None,
        "created_at": user.created_at.isoformat() if user.created_at else None,
        "updated_at": user.updated_at.isoformat() if user.updated_at else None,
    }


def get_user_by_account(account: str) -> dict[str, Any] | None:
    normalized = normalize_account(account)
    if not normalized:
        return None
    with Session(get_engine()) as session:
        user = session.scalar(select(AuthUser).where(AuthUser.account == normalized))
        return _user_to_dict(user) if user else None


def get_user_by_id(user_id: str) -> dict[str, Any] | None:
    with Session(get_engine()) as session:
        user = session.get(AuthUser, user_id)
        return _user_to_dict(user) if user else None


def create_user(*, account: str, password: str, plan_id: str = "free") -> dict[str, Any]:
    normalized = normalize_account(account)
    if not normalized:
        raise ValueError("account required")
    if len(password) < 6:
        raise ValueError("password too short")
    plan = normalize_plan(plan_id)
    now = datetime.now(timezone.utc)
    expires = now + timedelta(days=PLAN_TRIAL_DAYS) if plan == "free" else None
    user = AuthUser(
        id=uuid.uuid4().hex,
        account=normalized,
        password_hash=hash_password(password),
        plan_id=plan,
        plan_expires_at=expires,
    )
    with Session(get_engine()) as session:
        existing = session.scalar(select(AuthUser).where(AuthUser.account == normalized))
        if existing:
            raise ValueError("account already exists")
        session.add(user)
        session.commit()
        session.refresh(user)
        return _user_to_dict(user)


def authenticate_user(*, account: str, password: str) -> dict[str, Any] | None:
    user = get_user_by_account(account)
    if not user:
        return None
    if not verify_password(password, str(user["password_hash"])):
        return None
    return user


def update_user_plan(*, user_id: str, plan_id: str, plan_expires_at: datetime | None) -> dict[str, Any]:
    plan = normalize_plan(plan_id)
    now = datetime.now(timezone.utc)
    with Session(get_engine()) as session:
        user = session.get(AuthUser, user_id)
        if not user:
            raise ValueError("user not found")
        user.plan_id = plan
        user.plan_expires_at = plan_expires_at
        user.updated_at = now
        session.commit()
        session.refresh(user)
        return _user_to_dict(user)
