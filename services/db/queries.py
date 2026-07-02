from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from db.models import Instrument
from db.session import get_engine


def list_instruments(
    market: str | None = None,
    query: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[dict]:
    stmt = select(Instrument).order_by(Instrument.market, Instrument.symbol).limit(limit).offset(offset)
    if market:
        stmt = stmt.where(Instrument.market == market.upper())
    if query:
        like = f"%{query.strip().upper()}%"
        stmt = stmt.where((Instrument.symbol.ilike(like)) | (Instrument.name.ilike(like)))

    with Session(get_engine()) as session:
        rows = session.scalars(stmt).all()
        return [
            {
                "id": row.id,
                "market": row.market,
                "symbol": row.symbol,
                "name": row.name,
                "is_whitelisted": row.is_whitelisted,
            }
            for row in rows
        ]
