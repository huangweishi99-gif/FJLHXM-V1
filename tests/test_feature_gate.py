"""Unit tests for services/feature_gate.py."""
from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services"))

from feature_gate import (  # noqa: E402
    FeatureGateError,
    effective_plan,
    ensure_plan_active,
    is_plan_active,
    plan_expires_at_dt,
)


def test_effective_plan_ignores_client_plan_without_auth() -> None:
    assert effective_plan(auth_user=None, client_plan="pro") == "free"


def test_effective_plan_uses_auth_user_plan() -> None:
    assert effective_plan(auth_user={"plan_id": "standard"}) == "standard"


def test_plan_expires_at_from_explicit_field() -> None:
    user = {"plan_id": "free", "plan_expires_at": "2026-07-01T00:00:00+00:00", "created_at": "2026-06-01T00:00:00+00:00"}
    assert plan_expires_at_dt(user).isoformat() == "2026-07-01T00:00:00+00:00"


def test_plan_expires_at_free_fallback_created_plus_trial() -> None:
    user = {"plan_id": "free", "plan_expires_at": None, "created_at": "2026-06-01T00:00:00+00:00"}
    assert plan_expires_at_dt(user).isoformat() == "2026-06-08T00:00:00+00:00"


def test_is_plan_active_respects_expiry() -> None:
    now = datetime(2026, 6, 10, tzinfo=timezone.utc)
    user = {"plan_id": "free", "plan_expires_at": "2026-06-09T00:00:00+00:00"}
    assert is_plan_active(user, now=now) is False
    assert is_plan_active(user, now=datetime(2026, 6, 8, tzinfo=timezone.utc)) is True


def test_ensure_plan_active_raises_when_expired() -> None:
    now = datetime(2026, 6, 10, tzinfo=timezone.utc)
    user = {"plan_id": "standard", "plan_expires_at": "2026-06-09T00:00:00+00:00"}
    with pytest.raises(FeatureGateError, match="subscription expired"):
        ensure_plan_active(user)
    assert is_plan_active(user, now=now) is False


def test_ensure_plan_active_skips_anonymous() -> None:
    ensure_plan_active(None)
