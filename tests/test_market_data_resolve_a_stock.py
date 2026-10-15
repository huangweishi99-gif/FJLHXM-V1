"""market_data_resolve_a_stock.py 单元测试（用临时 sqlite + 临时 cache）。

Design inspired by free-stockdb MIT © 2026 hello245m.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd
import pytest

from market_data_resolve_a_stock import (
    A_STOCK_MARKET,
    MIN_DB_ROWS,
    db_bar_count,
    resolve_a_stock_csv,
)
from market_data_store import connect, init_db, normalize_timeframe


# ===== Fixtures =====

def _seed_a_stock_db(db_path: Path, code: str, timeframe: str, rows: int = 100) -> None:
    """往临时 sqlite 写 A_STOCK 行情。"""
    conn = connect(db_path)
    init_db(conn)
    tf = normalize_timeframe(timeframe)
    start = pd.Timestamp("2020-01-01")
    for i in range(rows):
        dt = (start + pd.Timedelta(days=i)).strftime("%Y-%m-%d")
        conn.execute(
            """
            INSERT OR REPLACE INTO bars
                (market, symbol, timeframe, dt, open, high, low, close, volume, source)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (A_STOCK_MARKET, code.upper(), tf, dt, 10.0 + i * 0.1, 11.0 + i * 0.1, 9.5 + i * 0.1, 10.5 + i * 0.1, 100000, "test"),
        )
    conn.commit()
    conn.close()


def _write_a_stock_csv(csv_path: Path, rows: int = 50) -> None:
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    frame = pd.DataFrame(
        {
            "date": pd.date_range("2020-01-01", periods=rows, freq="D"),
            "open": [10.0 + i * 0.1 for i in range(rows)],
            "high": [11.0 + i * 0.1 for i in range(rows)],
            "low": [9.5 + i * 0.1 for i in range(rows)],
            "close": [10.5 + i * 0.1 for i in range(rows)],
            "volume": [100000] * rows,
        }
    )
    frame.to_csv(csv_path, index=False, encoding="utf-8-sig")


# ===== db_bar_count =====

def test_db_bar_count_zero_when_empty(tmp_path: Path):
    db = tmp_path / "test.db"
    conn = connect(db)
    init_db(conn)
    assert db_bar_count(conn, "000021", "1D") == 0
    conn.close()


def test_db_bar_count_matches(tmp_path: Path):
    db = tmp_path / "test.db"
    _seed_a_stock_db(db, "000021", "1D", rows=100)
    assert db_bar_count(connect(db), "000021", "1D") == 100
    # 1D 在 D1 别名下应等价
    assert db_bar_count(connect(db), "000021", "D1") == 100


# ===== resolve_a_stock_csv：DB 路径 =====

def test_resolve_db_hit(tmp_path: Path):
    db = tmp_path / "test.db"
    _seed_a_stock_db(db, "000021", "1D", rows=100)
    cache = tmp_path / "out" / "000021_1D_qfq.csv"
    path, source = resolve_a_stock_csv(
        "000021", "1D", cache, data_source="auto", db_path=db
    )
    assert source == "db"
    assert path == cache
    assert cache.exists()
    # 写出的 CSV 应至少 30 行
    frame = pd.read_csv(cache)
    assert len(frame) >= MIN_DB_ROWS


def test_resolve_db_miss_strict_raises(tmp_path: Path):
    db = tmp_path / "test.db"
    _seed_a_stock_db(db, "000021", "1D", rows=10)  # < 30 行
    cache = tmp_path / "000021_1D_qfq.csv"
    with pytest.raises(FileNotFoundError, match="DB missing A_STOCK"):
        resolve_a_stock_csv(
            "000021", "1D", cache, data_source="db", db_path=db
        )


# ===== resolve_a_stock_csv：cache 路径 =====

def test_resolve_cache_hit(tmp_path: Path):
    cache = tmp_path / "000021_1D_qfq.csv"
    _write_a_stock_csv(cache, rows=50)
    # 不存在 db → auto 回落 cache
    db = tmp_path / "no_such.db"  # 不创建
    path, source = resolve_a_stock_csv(
        "000021", "1D", cache, data_source="auto", db_path=db
    )
    assert source == "cache"
    assert path == cache


def test_resolve_missing_returns_missing_tag(tmp_path: Path):
    cache = tmp_path / "000021_1D_qfq.csv"
    db = tmp_path / "no_such.db"
    path, source = resolve_a_stock_csv(
        "000021", "1D", cache, data_source="auto", db_path=db
    )
    assert source == "missing"


def test_resolve_db_priority_over_cache(tmp_path: Path):
    """DB 满足 min_rows 时，DB 优先（即使 cache 也存在）。"""
    db = tmp_path / "test.db"
    _seed_a_stock_db(db, "000021", "1D", rows=100)
    cache = tmp_path / "000021_1D_qfq.csv"
    _write_a_stock_csv(cache, rows=50)  # 旧 cache
    path, source = resolve_a_stock_csv(
        "000021", "1D", cache, data_source="auto", db_path=db
    )
    # DB 优先 → 用 DB 写出
    assert source == "db"
    # 写出后 cache 内容应是 DB 的（100 行），不是原始 50 行
    frame = pd.read_csv(cache)
    assert len(frame) >= MIN_DB_ROWS


def test_resolve_timeframe_alias(tmp_path: Path):
    """frequency="DAY" 应等价 "1D"。"""
    db = tmp_path / "test.db"
    _seed_a_stock_db(db, "000021", "1D", rows=100)
    cache = tmp_path / "000021_1D_qfq.csv"
    path, source = resolve_a_stock_csv(
        "000021", "DAY", cache, data_source="auto", db_path=db
    )
    assert source == "db"
    assert path.exists()


# ===== 错误路径 =====

def test_resolve_cache_too_small_treated_as_missing(tmp_path: Path):
    """cache 文件 < 50 bytes 视为空（不命中 cache）。"""
    cache = tmp_path / "000021_1D_qfq.csv"
    cache.write_text("date\n2020-01-01\n", encoding="utf-8")  # < 50 字节
    db = tmp_path / "no_such.db"
    path, source = resolve_a_stock_csv(
        "000021", "1D", cache, data_source="auto", db_path=db
    )
    # 不到 50 字节 → 视为无 cache → missing
    assert source == "missing"
