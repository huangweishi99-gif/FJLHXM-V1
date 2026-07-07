from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from db.models import PaperWatchlist
from db.session import get_engine

WATCHLIST_STATUS_PENDING_RUNTIME = "pending_runtime"
WATCHLIST_STATUS_PAUSED = "paused"
WATCHLIST_STATUS_CANCELLED = "cancelled"
WATCHLIST_ALLOWED_STATUSES = {
    WATCHLIST_STATUS_PENDING_RUNTIME,
    WATCHLIST_STATUS_PAUSED,
    WATCHLIST_STATUS_CANCELLED,
}


def _watchlist_to_dict(row: PaperWatchlist) -> dict[str, Any]:
    return {
        "id": row.id,
        "request_id": row.request_id,
        "user_id": row.user_id,
        "plan_id": row.plan_id,
        "market": row.market,
        "symbol": row.symbol,
        "name": row.name,
        "strategies": row.strategies_json,
        "status": row.status,
        "source": row.source,
        "params": row.params_json,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


def create_or_get_paper_watchlist_entry(
    *,
    request_id: str,
    user_id: str,
    plan_id: str | None,
    market: str,
    symbol: str,
    strategies: list[str],
    years: int,
    name: str | None = None,
) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    params = {
        "request_id": request_id,
        "market": market,
        "symbol": symbol,
        "strategies": strategies,
        "years": int(years),
        "mode": "paper_watchlist_only",
        "runtime_binding": "pending",
    }
    with Session(get_engine()) as session:
        existing = session.scalar(
            select(PaperWatchlist)
            .where(PaperWatchlist.request_id == request_id)
            .limit(1)
        )
        if existing is not None:
            return _watchlist_to_dict(existing)
        row = PaperWatchlist(
            id=str(uuid.uuid4()),
            request_id=request_id,
            user_id=user_id,
            plan_id=plan_id,
            market=market,
            symbol=symbol,
            name=name,
            strategies_json=strategies,
            status=WATCHLIST_STATUS_PENDING_RUNTIME,
            source="custom_instrument_request",
            params_json=params,
            updated_at=now,
        )
        session.add(row)
        session.commit()
        session.refresh(row)
        return _watchlist_to_dict(row)


def list_paper_watchlist(*, user_id: str, status: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
    with Session(get_engine()) as session:
        stmt = (
            select(PaperWatchlist)
            .where(PaperWatchlist.user_id == user_id)
            .order_by(PaperWatchlist.created_at.desc())
            .limit(limit)
        )
        if status:
            stmt = stmt.where(PaperWatchlist.status == status)
        return [_watchlist_to_dict(row) for row in session.scalars(stmt).all()]


def list_distinct_watchlist_user_ids(*, status: str | None = None, limit_users: int = 200) -> list[str]:
    """Distinct user ids with at least one paper_watchlist row (for runtime cache jobs)."""
    with Session(get_engine()) as session:
        stmt = select(PaperWatchlist.user_id).distinct().order_by(PaperWatchlist.user_id.asc())
        if status:
            stmt = stmt.where(PaperWatchlist.status == status)
        if limit_users > 0:
            stmt = stmt.limit(limit_users)
        return [uid for uid in session.scalars(stmt).all() if uid]


def update_paper_watchlist_status(*, watchlist_id: str, user_id: str, status: str) -> dict[str, Any] | None:
    if status not in WATCHLIST_ALLOWED_STATUSES:
        raise ValueError(f"unsupported paper watchlist status: {status}")
    with Session(get_engine()) as session:
        row = session.scalar(
            select(PaperWatchlist)
            .where(
                PaperWatchlist.id == watchlist_id,
                PaperWatchlist.user_id == user_id,
            )
            .limit(1)
        )
        if row is None:
            return None
        row.status = status
        row.updated_at = datetime.now(timezone.utc)
        params = dict(row.params_json or {})
        params["runtime_binding"] = "disabled" if status in {WATCHLIST_STATUS_PAUSED, WATCHLIST_STATUS_CANCELLED} else "pending"
        params["last_status_change"] = {"status": status, "updated_at": row.updated_at.isoformat()}
        row.params_json = params
        session.commit()
        session.refresh(row)
        return _watchlist_to_dict(row)
