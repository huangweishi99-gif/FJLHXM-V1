#!/usr/bin/env python3
"""Import crypto daily CSV files into PostgreSQL instruments + bars."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd
from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services"))

from db.models import Bar, Instrument  # noqa: E402
from db.session import get_engine  # noqa: E402

DEFAULT_DIRS = (
    ROOT / "data" / "overseas_1d",
    ROOT / "data" / "1d",
)
BATCH_SIZE = 5000


def upsert_instrument(conn, symbol: str) -> int:
    stmt = (
        insert(Instrument)
        .values(market="CRYPTO", symbol=symbol, name=symbol)
        .on_conflict_do_update(
            index_elements=["market", "symbol"],
            set_={"updated_at": text("now()")},
        )
        .returning(Instrument.id)
    )
    return conn.execute(stmt).scalar_one()


def load_bars(csv_path: Path) -> pd.DataFrame:
    df = pd.read_csv(csv_path)
    df.columns = [str(c).strip().lower() for c in df.columns]
    date_col = "timestamp" if "timestamp" in df.columns else "date"
    df = df.rename(columns={date_col: "dt"})
    for col in ("open", "high", "low", "close"):
        df[col] = pd.to_numeric(df[col], errors="coerce")
    if "volume" in df.columns:
        df["volume"] = pd.to_numeric(df["volume"], errors="coerce").fillna(0)
    else:
        df["volume"] = 0
    df["dt"] = pd.to_datetime(df["dt"])
    return df.dropna(subset=["dt", "open", "high", "low", "close"])


def import_csv(conn, instrument_id: int, csv_path: Path) -> int:
    df = load_bars(csv_path)
    total = 0
    batch: list[dict] = []
    for row in df.itertuples(index=False):
        batch.append(
            {
                "instrument_id": instrument_id,
                "timeframe": "1D",
                "dt": row.dt.to_pydatetime() if hasattr(row.dt, "to_pydatetime") else row.dt,
                "open": float(row.open),
                "high": float(row.high),
                "low": float(row.low),
                "close": float(row.close),
                "volume": float(getattr(row, "volume", 0)),
                "source": csv_path.parent.name,
            }
        )
        if len(batch) >= BATCH_SIZE:
            stmt = insert(Bar).values(batch).on_conflict_do_nothing()
            conn.execute(stmt)
            total += len(batch)
            batch = []
    if batch:
        stmt = insert(Bar).values(batch).on_conflict_do_nothing()
        conn.execute(stmt)
        total += len(batch)
    return total


def main() -> None:
    parser = argparse.ArgumentParser(description="Import crypto CSV daily bars to PostgreSQL")
    parser.add_argument("--dir", action="append", type=Path, help="CSV directory (repeatable)")
    parser.add_argument("--symbol", help="Only import one symbol, e.g. SOLUSDT")
    args = parser.parse_args()

    dirs = args.dir or list(DEFAULT_DIRS)
    csv_files: list[Path] = []
    seen: set[str] = set()
    for folder in dirs:
        if not folder.exists():
            continue
        for path in sorted(folder.glob("*.csv")):
            sym = path.stem.upper().replace("-", "")
            if args.symbol and sym != args.symbol.upper():
                continue
            if sym in seen:
                continue
            seen.add(sym)
            csv_files.append(path)

    if not csv_files:
        print("no csv files found")
        return

    engine = get_engine()
    grand_total = 0
    with engine.begin() as conn:
        for path in csv_files:
            symbol = path.stem.upper().replace("-", "")
            instrument_id = upsert_instrument(conn, symbol)
            count = import_csv(conn, instrument_id, path)
            grand_total += count
            print(f"  CRYPTO/{symbol}: {count} bars from {path.name}")

    print(f"done: {len(csv_files)} instruments, {grand_total} bar rows")


if __name__ == "__main__":
    main()
