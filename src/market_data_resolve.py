"""Resolve backtest K-line CSV paths: SQLite DB first, then cache / download fallback."""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd

from market_data_store import connect, export_csv, init_db, normalize_timeframe


DEFAULT_DB_PATH = Path("data/market_data.sqlite")
MIN_DB_ROWS = 30


def db_bar_count(conn: sqlite3.Connection, market: str, symbol: str, timeframe: str) -> int:
    market = market.upper()
    symbol = symbol.upper()
    timeframe = normalize_timeframe(timeframe)
    row = conn.execute(
        "SELECT COUNT(*) FROM bars WHERE market = ? AND symbol = ? AND timeframe = ?",
        (market, symbol, timeframe),
    ).fetchone()
    return int(row[0] if row else 0)


def export_crypto_frame(
    conn: sqlite3.Connection,
    inst_id: str,
    timeframe: str,
    out_path: Path,
    *,
    days: int | None = None,
) -> int:
    inst_id = inst_id.upper()
    timeframe = normalize_timeframe(timeframe)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    start = ""
    if days is not None and days > 0:
        row = conn.execute(
            """
            SELECT MAX(dt) FROM bars
            WHERE market = ? AND symbol = ? AND timeframe = ?
            """,
            ("CRYPTO", inst_id, timeframe),
        ).fetchone()
        max_dt = row[0] if row else None
        if not max_dt:
            return 0
        start = (pd.Timestamp(max_dt) - pd.Timedelta(days=days)).isoformat(sep=" ")
    return export_csv(conn, "CRYPTO", inst_id, timeframe, out_path, start=start)


def resolve_crypto_csv(
    inst_id: str,
    timeframe: str,
    cache_path: Path,
    *,
    data_source: str = "auto",
    db_path: str | Path = DEFAULT_DB_PATH,
    min_rows: int = MIN_DB_ROWS,
    days: int | None = None,
) -> tuple[Path, str]:
    """Return (csv_path, source_tag). source_tag: db | cache | missing."""
    inst_id = inst_id.upper()
    timeframe = normalize_timeframe(timeframe)
    data_source = data_source.lower()

    if data_source in {"auto", "db"}:
        db_file = Path(db_path)
        if db_file.exists():
            conn = connect(db_file)
            init_db(conn)
            if db_bar_count(conn, "CRYPTO", inst_id, timeframe) >= min_rows:
                rows = export_crypto_frame(conn, inst_id, timeframe, cache_path, days=days)
                if rows >= min_rows:
                    return cache_path, "db"
            if data_source == "db":
                raise FileNotFoundError(
                    f"DB missing CRYPTO {inst_id} {timeframe} (need>={min_rows} rows) in {db_file}"
                )

    if cache_path.exists() and cache_path.stat().st_size > 50:
        return cache_path, "cache"
    if data_source == "db":
        raise FileNotFoundError(f"DB export failed and no cache: {cache_path}")
    return cache_path, "missing"


def resolve_futures_csv(
    symbol: str,
    timeframe: str,
    cache_path: Path,
    *,
    data_source: str = "auto",
    db_path: str | Path = DEFAULT_DB_PATH,
    min_rows: int = MIN_DB_ROWS,
) -> tuple[Path, str]:
    symbol = symbol.upper()
    timeframe = normalize_timeframe(timeframe)
    data_source = data_source.lower()

    if data_source in {"auto", "db"}:
        db_file = Path(db_path)
        if db_file.exists():
            conn = connect(db_file)
            init_db(conn)
            if db_bar_count(conn, "FUTURES", symbol, timeframe) >= min_rows:
                cache_path.parent.mkdir(parents=True, exist_ok=True)
                rows = export_csv(conn, "FUTURES", symbol, timeframe, cache_path)
                if rows >= min_rows:
                    return cache_path, "db"
            if data_source == "db":
                raise FileNotFoundError(
                    f"DB missing FUTURES {symbol} {timeframe} in {db_file}"
                )

    if cache_path.exists() and cache_path.stat().st_size > 50:
        return cache_path, "cache"
    if data_source == "db":
        raise FileNotFoundError(f"no futures cache: {cache_path}")
    return cache_path, "missing"
