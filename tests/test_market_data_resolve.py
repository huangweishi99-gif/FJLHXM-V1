"""Tests for market_data_resolve DB-first CSV resolution."""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from market_data_resolve import resolve_crypto_csv  # noqa: E402
from market_data_store import connect, import_frame, init_db  # noqa: E402


def test_resolve_crypto_csv_from_db(tmp_path: Path) -> None:
    db_path = tmp_path / "market_data.sqlite"
    cache_path = tmp_path / "BTC-USDT_1D_180d.csv"
    conn = connect(db_path)
    init_db(conn)
    frame = pd.DataFrame(
        {
            "date": pd.date_range("2026-01-01", periods=5, freq="D"),
            "open": [1, 2, 3, 4, 5],
            "high": [1, 2, 3, 4, 5],
            "low": [1, 2, 3, 4, 5],
            "close": [1, 2, 3, 4, 5],
            "volume": [10, 10, 10, 10, 10],
        }
    )
    import_frame(conn, frame, "CRYPTO", "BTC-USDT", "1D", "test", name="BTC")
    path, tag = resolve_crypto_csv(
        "BTC-USDT",
        "1D",
        cache_path,
        data_source="db",
        db_path=db_path,
        min_rows=3,
        days=180,
    )
    assert tag == "db"
    assert path == cache_path
    assert cache_path.exists()
    exported = pd.read_csv(cache_path)
    assert len(exported) == 5


def test_resolve_crypto_csv_db_required_missing(tmp_path: Path) -> None:
    db_path = tmp_path / "empty.sqlite"
    conn = connect(db_path)
    init_db(conn)
    try:
        resolve_crypto_csv(
            "ETH-USDT",
            "1D",
            tmp_path / "missing.csv",
            data_source="db",
            db_path=db_path,
        )
        raised = False
    except FileNotFoundError:
        raised = True
    assert raised
