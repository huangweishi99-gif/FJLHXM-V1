"""V1.1: per-user paper_accounts in PostgreSQL."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from db.models import PaperAccount, PaperAccountLedger
from db.session import get_engine

DEFAULT_INITIAL_CASH = 100_000.0
MARKET_GROUP_SCOPED_SHARED = "scoped_shared_v1_1"


def _account_to_dict(row: PaperAccount) -> dict[str, Any]:
    return {
        "id": row.id,
        "user_id": row.user_id,
        "market_group": row.market_group,
        "initial_cash": float(row.initial_cash),
        "cash": float(row.cash),
        "equity": float(row.equity),
        "storage_mode": row.storage_mode,
        "metadata": dict(row.metadata_json or {}),
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


def _ledger_to_dict(row: PaperAccountLedger) -> dict[str, Any]:
    return {
        "id": row.id,
        "account_id": row.account_id,
        "user_id": row.user_id,
        "event_type": row.event_type,
        "symbol": row.symbol,
        "market": row.market,
        "strategy_id": row.strategy_id,
        "amount": float(row.amount) if row.amount is not None else None,
        "metadata": dict(row.metadata_json or {}),
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


def get_paper_account(user_id: str) -> dict[str, Any] | None:
    uid = str(user_id or "").strip()
    if not uid:
        return None
    with Session(get_engine()) as session:
        row = session.scalar(select(PaperAccount).where(PaperAccount.user_id == uid))
        return _account_to_dict(row) if row else None


def get_or_create_paper_account(
    user_id: str,
    *,
    initial_cash: float = DEFAULT_INITIAL_CASH,
    market_group: str = MARKET_GROUP_SCOPED_SHARED,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    uid = str(user_id or "").strip()
    if not uid:
        raise ValueError("user_id required")
    now = datetime.now(timezone.utc)
    with Session(get_engine()) as session:
        row = session.scalar(select(PaperAccount).where(PaperAccount.user_id == uid))
        if row is None:
            account_id = uuid.uuid4().hex
            row = PaperAccount(
                id=account_id,
                user_id=uid,
                market_group=market_group,
                initial_cash=float(initial_cash),
                cash=float(initial_cash),
                equity=float(initial_cash),
                storage_mode="pg",
                metadata_json=dict(metadata or {}),
                created_at=now,
                updated_at=now,
            )
            session.add(row)
            session.add(
                PaperAccountLedger(
                    id=uuid.uuid4().hex,
                    account_id=account_id,
                    user_id=uid,
                    event_type="account_bootstrap",
                    amount=float(initial_cash),
                    metadata_json={"market_group": market_group},
                    created_at=now,
                )
            )
            session.commit()
            session.refresh(row)
            return _account_to_dict(row)

        if metadata:
            merged = dict(row.metadata_json or {})
            merged.update(metadata)
            row.metadata_json = merged
            row.updated_at = now
            session.commit()
            session.refresh(row)
        return _account_to_dict(row)


def update_paper_account_snapshot(
    user_id: str,
    *,
    equity: float,
    cash: float,
    metadata: dict[str, Any] | None = None,
    ledger_event: dict[str, Any] | None = None,
) -> dict[str, Any]:
    uid = str(user_id or "").strip()
    if not uid:
        raise ValueError("user_id required")
    now = datetime.now(timezone.utc)
    with Session(get_engine()) as session:
        row = session.scalar(select(PaperAccount).where(PaperAccount.user_id == uid))
        if row is None:
            raise ValueError("paper account not found")
        prev_equity = float(row.equity)
        row.equity = float(equity)
        row.cash = float(cash)
        row.updated_at = now
        if metadata:
            merged = dict(row.metadata_json or {})
            merged.update(metadata)
            row.metadata_json = merged
        if ledger_event or abs(prev_equity - float(equity)) >= 0.01:
            event = dict(ledger_event or {})
            session.add(
                PaperAccountLedger(
                    id=uuid.uuid4().hex,
                    account_id=row.id,
                    user_id=uid,
                    event_type=str(event.get("event_type") or "equity_snapshot"),
                    symbol=event.get("symbol"),
                    market=event.get("market"),
                    strategy_id=event.get("strategy_id"),
                    amount=float(event.get("amount") if event.get("amount") is not None else equity),
                    metadata_json={
                        "prev_equity": prev_equity,
                        "equity": float(equity),
                        "cash": float(cash),
                        **dict(event.get("metadata") or {}),
                    },
                    created_at=now,
                )
            )
        session.commit()
        session.refresh(row)
        return _account_to_dict(row)


def append_paper_ledger_event(
    user_id: str,
    *,
    event_type: str,
    amount: float | None = None,
    symbol: str | None = None,
    market: str | None = None,
    strategy_id: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Append ledger row without mutating account equity (Phase 4 shadow)."""
    uid = str(user_id or "").strip()
    if not uid:
        return None
    now = datetime.now(timezone.utc)
    with Session(get_engine()) as session:
        row = session.scalar(select(PaperAccount).where(PaperAccount.user_id == uid))
        if row is None:
            return None
        ledger = PaperAccountLedger(
            id=uuid.uuid4().hex,
            account_id=row.id,
            user_id=uid,
            event_type=str(event_type),
            symbol=symbol,
            market=market,
            strategy_id=strategy_id,
            amount=float(amount) if amount is not None else None,
            metadata_json=dict(metadata or {}),
            created_at=now,
        )
        session.add(ledger)
        session.commit()
        return _ledger_to_dict(ledger)


def list_recent_ledger(user_id: str, *, limit: int = 20) -> list[dict[str, Any]]:
    uid = str(user_id or "").strip()
    if not uid:
        return []
    with Session(get_engine()) as session:
        rows = session.scalars(
            select(PaperAccountLedger)
            .where(PaperAccountLedger.user_id == uid)
            .order_by(desc(PaperAccountLedger.created_at))
            .limit(max(1, min(int(limit), 200)))
        ).all()
        return [_ledger_to_dict(row) for row in rows]
