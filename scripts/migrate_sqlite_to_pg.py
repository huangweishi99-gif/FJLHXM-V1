#!/usr/bin/env python3
"""SQLite market_data.sqlite → PostgreSQL instruments + bars (FJLHXM-V1 W10)."""
from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services"))

from db.models import Bar, Instrument  # noqa: E402
from db.session import get_engine  # noqa: E402

DEFAULT_SQLITE = ROOT / "data" / "market_data.sqlite"
BATCH_SIZE = 5000


def upsert_instrument(conn, market: str, symbol: str, name: str | None) -> int:
    stmt = (
        insert(Instrument)
        .values(market=market, symbol=symbol, name=name)
        .on_conflict_do_update(
            index_elements=["market", "symbol"],
            set_={"name": name, "updated_at": text("now()")},
        )
        .returning(Instrument.id)
    )
    return conn.execute(stmt).scalar_one()


def import_bars(conn, instrument_id: int, rows: list[dict]) -> int:
    if not rows:
        return 0
    stmt = insert(Bar).values(rows)
    stmt = stmt.on_conflict_do_nothing(index_elements=["instrument_id", "timeframe", "dt"])
    conn.execute(stmt)
    return len(rows)


def migrate(sqlite_path: Path, market_filter: str | None, dry_run: bool) -> None:
    if not sqlite_path.exists():
        raise FileNotFoundError(sqlite_path)

    sqlite = sqlite3.connect(sqlite_path)
    sqlite.row_factory = sqlite3.Row
    engine = get_engine()

    inst_query = "SELECT market, symbol, name, source FROM instruments"
    params: tuple = ()
    if market_filter:
        inst_query += " WHERE market = ?"
        params = (market_filter.upper(),)

    instruments = sqlite.execute(inst_query, params).fetchall()
    print(f"instruments to sync: {len(instruments)}")

    total_bars = 0
    with engine.begin() as conn:
        for inst in instruments:
            instrument_id = upsert_instrument(
                conn,
                market=inst["market"],
                symbol=inst["symbol"],
                name=inst["name"],
            )
            bar_rows = sqlite.execute(
                """
                SELECT timeframe, dt, open, high, low, close, volume, source
                FROM bars
                WHERE market = ? AND symbol = ?
                ORDER BY timeframe, dt
                """,
                (inst["market"], inst["symbol"]),
            ).fetchall()

            batch: list[dict] = []
            for row in bar_rows:
                batch.append(
                    {
                        "instrument_id": instrument_id,
                        "timeframe": row["timeframe"],
                        "dt": row["dt"],
                        "open": row["open"],
                        "high": row["high"],
                        "low": row["low"],
                        "close": row["close"],
                        "volume": row["volume"],
                        "source": row["source"],
                    }
                )
                if len(batch) >= BATCH_SIZE:
                    total_bars += import_bars(conn, instrument_id, batch)
                    batch = []
            total_bars += import_bars(conn, instrument_id, batch)
            print(f"  {inst['market']}/{inst['symbol']}: {len(bar_rows)} bars")

        if dry_run:
            raise RuntimeError("dry-run: rolling back transaction")

    print(f"done: {len(instruments)} instruments, {total_bars} bar rows inserted (conflicts skipped)")


def main() -> None:
    parser = argparse.ArgumentParser(description="Migrate SQLite market data to PostgreSQL")
    parser.add_argument("--sqlite", type=Path, default=DEFAULT_SQLITE)
    parser.add_argument("--market", help="Only migrate one market, e.g. CRYPTO or A_STOCK")
    parser.add_argument("--dry-run", action="store_true", help="Run in a transaction then rollback")
    args = parser.parse_args()
    migrate(args.sqlite, args.market, args.dry_run)


if __name__ == "__main__":
    main()
