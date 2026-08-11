"""Smoke tests for market_data_store import-futures-local."""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from market_data_store import connect, import_futures_local, init_db  # noqa: E402


def test_import_futures_local_short_code(tmp_path: Path) -> None:
    csv_dir = tmp_path / "data" / "15m"
    csv_dir.mkdir(parents=True)
    csv_path = csv_dir / "AG.csv"
    csv_path.write_text(
        "date,open,high,low,close,volume\n"
        "2026-01-01 09:00:00,100,101,99,100.5,10\n"
        "2026-01-01 09:15:00,100.5,102,100,101,12\n",
        encoding="utf-8",
    )
    db_path = tmp_path / "market_data.sqlite"
    conn = connect(db_path)
    init_db(conn)
    rows = import_futures_local(conn, tmp_path)
    assert len(rows) == 1
    assert rows[0]["status"] == "ok"
    assert rows[0]["rows"] == 2
    count = conn.execute(
        "SELECT COUNT(*) FROM bars WHERE market='FUTURES' AND symbol='AG' AND timeframe='15m'"
    ).fetchone()[0]
    assert count == 2


def test_import_futures_local_5m(tmp_path: Path) -> None:
    csv_dir = tmp_path / "data" / "futures" / "5m"
    csv_dir.mkdir(parents=True)
    csv_path = csv_dir / "AG.csv"
    csv_path.write_text(
        "date,open,high,low,close,volume\n"
        "2026-01-01 09:00:00,100,101,99,100.5,10\n"
        "2026-01-01 09:05:00,100.5,102,100,101,12\n",
        encoding="utf-8",
    )
    db_path = tmp_path / "market_data.sqlite"
    conn = connect(db_path)
    init_db(conn)
    rows = import_futures_local(conn, tmp_path)
    assert len(rows) == 1
    assert rows[0]["status"] == "ok"
    assert rows[0]["timeframe"] == "5m"
    count = conn.execute(
        "SELECT COUNT(*) FROM bars WHERE market='FUTURES' AND symbol='AG' AND timeframe='5m'"
    ).fetchone()[0]
    assert count == 2
