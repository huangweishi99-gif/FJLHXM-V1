"""V1.1 Phase 3: PG mirror of per-user JSON paper execution state."""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import delete, desc, select
from sqlalchemy.orm import Session

from db.models import PaperUserOpenPosition, PaperUserPendingOrder
from db.session import get_engine

EXECUTION_MARKET = "CRYPTO"
ACTIVE_PENDING = {"ACTIVE", "READY_TRIGGERED", "PENDING"}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _safe_float(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def parse_open_positions_from_state(data: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    symbols = data.get("symbols") or {}
    if not isinstance(symbols, dict):
        return rows
    for sym, st in symbols.items():
        if not isinstance(st, dict):
            continue
        candidates: list[dict[str, Any]] = []
        open_one = st.get("open_position")
        if isinstance(open_one, dict) and open_one:
            candidates.append(open_one)
        for item in st.get("open_positions") or []:
            if isinstance(item, dict):
                candidates.append(item)
        for pos in candidates:
            position_key = str(pos.get("key") or pos.get("order_id") or f"{sym}|{pos.get('strategy_id')}|{pos.get('entry_time')}")
            rows.append(
                {
                    "market": EXECUTION_MARKET,
                    "symbol": str(pos.get("symbol") or sym),
                    "position_key": position_key,
                    "strategy_id": pos.get("strategy_id"),
                    "side": str(pos.get("direction") or pos.get("side") or ""),
                    "entry_price": _safe_float(pos.get("entry_price") or pos.get("trigger_price")),
                    "current_stop": _safe_float(pos.get("current_stop") or pos.get("stop_price") or pos.get("initial_stop")),
                    "status": "open",
                    "metadata_json": pos,
                }
            )
    return rows


def parse_pending_orders_from_json(data: Any) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    items: list[Any]
    if isinstance(data, list):
        items = data
    elif isinstance(data, dict):
        items = list(data.get("orders") or data.get("items") or [])
    else:
        return rows
    for raw in items:
        if not isinstance(raw, dict):
            continue
        status = str(raw.get("status") or "ACTIVE").upper()
        if status not in ACTIVE_PENDING:
            continue
        rows.append(
            {
                "market": EXECUTION_MARKET,
                "order_id": str(raw.get("order_id") or ""),
                "symbol": str(raw.get("symbol") or ""),
                "strategy_id": raw.get("strategy_id"),
                "side": raw.get("side"),
                "trigger_price": _safe_float(raw.get("trigger_price")),
                "stop_price": _safe_float(raw.get("stop_price")),
                "status": status,
                "metadata_json": raw,
            }
        )
    return [r for r in rows if r.get("order_id") and r.get("symbol")]


def _position_to_dict(row: PaperUserOpenPosition) -> dict[str, Any]:
    return {
        "id": row.id,
        "user_id": row.user_id,
        "market": row.market,
        "symbol": row.symbol,
        "position_key": row.position_key,
        "strategy_id": row.strategy_id,
        "side": row.side,
        "entry_price": float(row.entry_price) if row.entry_price is not None else None,
        "current_stop": float(row.current_stop) if row.current_stop is not None else None,
        "status": row.status,
        "metadata": dict(row.metadata_json or {}),
        "opened_at": row.opened_at.isoformat() if row.opened_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


def _pending_to_dict(row: PaperUserPendingOrder) -> dict[str, Any]:
    return {
        "id": row.id,
        "user_id": row.user_id,
        "market": row.market,
        "order_id": row.order_id,
        "symbol": row.symbol,
        "strategy_id": row.strategy_id,
        "side": row.side,
        "trigger_price": float(row.trigger_price) if row.trigger_price is not None else None,
        "stop_price": float(row.stop_price) if row.stop_price is not None else None,
        "status": row.status,
        "metadata": dict(row.metadata_json or {}),
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


def sync_user_execution_to_pg(
    user_id: str,
    *,
    paper_state_path: Path,
    pending_orders_path: Path,
) -> dict[str, Any]:
    uid = str(user_id or "").strip()
    if not uid:
        return {"ok": False, "error": "user_id required"}

    open_rows: list[dict[str, Any]] = []
    pending_rows: list[dict[str, Any]] = []
    if paper_state_path.is_file():
        try:
            open_rows = parse_open_positions_from_state(json.loads(paper_state_path.read_text(encoding="utf-8")))
        except Exception:
            open_rows = []
    if pending_orders_path.is_file():
        try:
            pending_rows = parse_pending_orders_from_json(json.loads(pending_orders_path.read_text(encoding="utf-8")))
        except Exception:
            pending_rows = []

    now = _now()
    with Session(get_engine()) as session:
        session.execute(delete(PaperUserOpenPosition).where(PaperUserOpenPosition.user_id == uid))
        session.execute(delete(PaperUserPendingOrder).where(PaperUserPendingOrder.user_id == uid))
        for row in open_rows:
            session.add(
                PaperUserOpenPosition(
                    id=uuid.uuid4().hex,
                    user_id=uid,
                    market=str(row.get("market") or EXECUTION_MARKET),
                    symbol=str(row["symbol"]),
                    position_key=str(row["position_key"]),
                    strategy_id=row.get("strategy_id"),
                    side=row.get("side"),
                    entry_price=row.get("entry_price"),
                    current_stop=row.get("current_stop"),
                    status=str(row.get("status") or "open"),
                    metadata_json=dict(row.get("metadata_json") or {}),
                    opened_at=now,
                    updated_at=now,
                )
            )
        for row in pending_rows:
            session.add(
                PaperUserPendingOrder(
                    id=uuid.uuid4().hex,
                    user_id=uid,
                    market=str(row.get("market") or EXECUTION_MARKET),
                    order_id=str(row["order_id"]),
                    symbol=str(row["symbol"]),
                    strategy_id=row.get("strategy_id"),
                    side=row.get("side"),
                    trigger_price=row.get("trigger_price"),
                    stop_price=row.get("stop_price"),
                    status=str(row.get("status") or "ACTIVE"),
                    metadata_json=dict(row.get("metadata_json") or {}),
                    created_at=now,
                    updated_at=now,
                )
            )
        session.commit()

    return {
        "ok": True,
        "user_id": uid,
        "open_positions": len(open_rows),
        "pending_orders": len(pending_rows),
    }


def list_user_open_positions(user_id: str, *, limit: int = 50) -> list[dict[str, Any]]:
    uid = str(user_id or "").strip()
    if not uid:
        return []
    with Session(get_engine()) as session:
        rows = session.scalars(
            select(PaperUserOpenPosition)
            .where(PaperUserOpenPosition.user_id == uid)
            .order_by(desc(PaperUserOpenPosition.updated_at))
            .limit(max(1, min(int(limit), 200)))
        ).all()
        return [_position_to_dict(row) for row in rows]


def list_user_pending_orders(user_id: str, *, limit: int = 50) -> list[dict[str, Any]]:
    uid = str(user_id or "").strip()
    if not uid:
        return []
    with Session(get_engine()) as session:
        rows = session.scalars(
            select(PaperUserPendingOrder)
            .where(PaperUserPendingOrder.user_id == uid)
            .order_by(desc(PaperUserPendingOrder.updated_at))
            .limit(max(1, min(int(limit), 200)))
        ).all()
        return [_pending_to_dict(row) for row in rows]
