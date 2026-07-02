"""WAdmin MVP: read-only overview aggregates (local / ops)."""
from __future__ import annotations

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from db.models import AuthUser, BacktestJob, CustomInstrumentRequest, SubscriptionOrder
from db.session import get_engine
from db.subscriptions import _order_to_dict


def _count_jobs_by_status(session: Session) -> dict[str, int]:
    rows = session.execute(
        select(BacktestJob.status, func.count()).group_by(BacktestJob.status)
    ).all()
    out = {str(status): int(count) for status, count in rows}
    out["total"] = sum(out.values())
    return out


def _user_admin_view(row: AuthUser) -> dict[str, Any]:
    return {
        "id": row.id,
        "account": row.account,
        "plan_id": row.plan_id,
        "plan_expires_at": row.plan_expires_at.isoformat() if row.plan_expires_at else None,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


def build_admin_overview(*, ws_stats: dict[str, Any]) -> dict[str, Any]:
    with Session(get_engine()) as session:
        auth_users = int(session.scalar(select(func.count()).select_from(AuthUser)) or 0)
        custom_requests = int(session.scalar(select(func.count()).select_from(CustomInstrumentRequest)) or 0)
        subscription_orders = int(session.scalar(select(func.count()).select_from(SubscriptionOrder)) or 0)
        recent_orders = session.scalars(
            select(SubscriptionOrder).order_by(SubscriptionOrder.created_at.desc()).limit(10)
        ).all()
        recent_users = session.scalars(
            select(AuthUser).order_by(AuthUser.created_at.desc()).limit(20)
        ).all()
        jobs = _count_jobs_by_status(session)

    ws_lifetime = dict(ws_stats.get("lifetime") or {})
    return {
        "auth_users": auth_users,
        "auth_users_recent": [_user_admin_view(row) for row in recent_users],
        "subscription_orders_total": subscription_orders,
        "subscription_orders_recent": [_order_to_dict(row) for row in recent_orders],
        "custom_instrument_requests_total": custom_requests,
        "backtest_jobs": jobs,
        "monitor_ws": {
            **ws_stats,
            "lifetime": ws_lifetime,
        },
    }
