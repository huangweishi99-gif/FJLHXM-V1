"""WAdmin overview aggregates."""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services"))

from admin_overview import _user_admin_view, build_admin_overview  # noqa: E402
from db.models import AuthUser  # noqa: E402


def test_user_admin_view_omits_password_hash() -> None:
    row = AuthUser(
        id="user-1",
        account="demo@test.local",
        password_hash="pbkdf2_sha256$120000$abc$def",
        plan_id="pro",
        plan_expires_at=datetime(2026, 7, 1, tzinfo=timezone.utc),
        created_at=datetime(2026, 6, 1, tzinfo=timezone.utc),
        updated_at=datetime(2026, 6, 1, tzinfo=timezone.utc),
    )
    view = _user_admin_view(row)
    assert view["account"] == "demo@test.local"
    assert view["plan_id"] == "pro"
    assert "password" not in view
    assert "password_hash" not in view


def test_build_admin_overview_includes_ws_lifetime() -> None:
    session = MagicMock()
    session.scalar.side_effect = [5, 2, 3]
    orders_result = MagicMock()
    orders_result.all.return_value = []
    users_result = MagicMock()
    users_result.all.return_value = [
        AuthUser(
            id="u1",
            account="a@test",
            password_hash="hash",
            plan_id="free",
            plan_expires_at=None,
            created_at=datetime(2026, 6, 1, tzinfo=timezone.utc),
            updated_at=datetime(2026, 6, 1, tzinfo=timezone.utc),
        )
    ]
    session.scalars.side_effect = [orders_result, users_result]
    session.execute.return_value.all.return_value = [("queued", 1)]

    ws_stats = {
        "active_total": 2,
        "lifetime": {"snapshots_sent": 3, "heartbeats_sent": 10, "deltas_sent": 4},
        "recent_events": [{"ts": "2026-06-09", "event": "delta_sent", "user_id": "u1"}],
    }

    with patch("admin_overview.Session") as session_cls:
        session_cls.return_value.__enter__.return_value = session
        body = build_admin_overview(ws_stats=ws_stats)

    assert body["auth_users"] == 5
    assert body["auth_users_recent"][0]["account"] == "a@test"
    assert body["monitor_ws"]["lifetime"]["deltas_sent"] == 4
    assert body["monitor_ws"]["recent_events"][0]["event"] == "delta_sent"
