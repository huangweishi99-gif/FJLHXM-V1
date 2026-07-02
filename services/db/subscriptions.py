"""W17-prod: subscription activation and order audit."""
from __future__ import annotations

import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy.orm import Session

from db.auth_users import normalize_plan
from db.models import AuthUser, SubscriptionOrder
from db.session import get_engine

PAID_PLANS = frozenset({"standard", "pro"})
DEFAULT_SUBSCRIPTION_DAYS = 30


def subscription_period_days() -> int:
    raw = os.getenv("FENGJI_SUBSCRIPTION_PERIOD_DAYS", str(DEFAULT_SUBSCRIPTION_DAYS)).strip()
    try:
        days = int(raw)
    except ValueError:
        days = DEFAULT_SUBSCRIPTION_DAYS
    return max(1, days)


def validate_subscription_intent(*, current_plan: str, requested_plan: str) -> None:
    target = normalize_plan(requested_plan)
    current = normalize_plan(current_plan)
    if target not in PAID_PLANS:
        raise ValueError("invalid subscription plan")
    if current == target:
        raise ValueError("subscription already active")
    if current == "pro" and target == "standard":
        raise ValueError("downgrade to standard is not allowed")


def _order_to_dict(row: SubscriptionOrder) -> dict[str, Any]:
    return {
        "id": row.id,
        "user_id": row.user_id,
        "plan_id": row.plan_id,
        "channel": row.channel,
        "status": row.status,
        "external_ref": row.external_ref,
        "metadata": dict(row.metadata_json or {}),
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "activated_at": row.activated_at.isoformat() if row.activated_at else None,
    }


def activate_user_subscription(
    *,
    user_id: str,
    plan_id: str,
    channel: str,
    external_ref: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Update auth_users plan and append subscription_orders audit row."""
    plan = normalize_plan(plan_id)
    if plan not in PAID_PLANS:
        raise ValueError("invalid subscription plan")
    now = datetime.now(timezone.utc)
    expires = now + timedelta(days=subscription_period_days())
    order_id = uuid.uuid4().hex
    with Session(get_engine()) as session:
        user = session.get(AuthUser, user_id)
        if not user:
            raise ValueError("user not found")
        validate_subscription_intent(current_plan=user.plan_id, requested_plan=plan)
        user.plan_id = plan
        user.plan_expires_at = expires
        user.updated_at = now
        order = SubscriptionOrder(
            id=order_id,
            user_id=user_id,
            plan_id=plan,
            channel=channel,
            status="active",
            external_ref=external_ref,
            metadata_json=dict(metadata or {}),
            activated_at=now,
        )
        session.add(order)
        session.commit()
        session.refresh(user)
        session.refresh(order)
        from db.auth_users import _user_to_dict

        return _user_to_dict(user), _order_to_dict(order)


def parse_redeem_codes() -> dict[str, str]:
    """Env format: standard:CODE1,pro:CODE2 (codes compared uppercase)."""
    raw = os.getenv("FENGJI_SUBSCRIPTION_REDEEM_CODES", "").strip()
    mapping: dict[str, str] = {}
    for part in raw.split(","):
        piece = part.strip()
        if ":" not in piece:
            continue
        plan, code = piece.split(":", 1)
        normalized_plan = normalize_plan(plan)
        normalized_code = code.strip().upper()
        if normalized_plan in PAID_PLANS and normalized_code:
            mapping[normalized_code] = normalized_plan
    return mapping


def redeem_code_for_plan(code: str) -> str | None:
    key = str(code or "").strip().upper()
    if not key:
        return None
    return parse_redeem_codes().get(key)
