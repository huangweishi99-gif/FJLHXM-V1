"""A 股 K 线 CSV 解析入口（仿 resolve_futures_csv 设计）。

Design inspired by free-stockdb MIT © 2026 hello245m.
对应文档：docs/FREE_STOCKDB_AUDIT.md §4.5

职责：
- resolve_a_stock_csv(code, timeframe, cache_path, ...) → (csv_path, source_tag)
  - source_tag ∈ {"db", "cache", "missing"}
  - DB 优先（data/market_data.sqlite 的 bars 表，market="A_STOCK"）
  - 回落 cache（data/a_stock/{code}_{timeframe}_qfq.csv）
  - 缺失时按 data_source 策略决定行为
- 不动 A 股 CSV / sqlite 写入路径（仅读）
- 复用 src/market_data_store 的 connect / init_db / export_csv / normalize_timeframe

与 market_data_resolve.py 的关系：
- 现有 resolve_crypto_csv / resolve_futures_csv 同模式，本文件补 A 股分支
- 调用方用法一致：resolve_*_csv(code, timeframe, cache_path, *, data_source, db_path, min_rows)
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd

from market_data_store import connect, export_csv, init_db, normalize_timeframe


MIN_DB_ROWS = 30
A_STOCK_MARKET = "A_STOCK"


def db_bar_count(conn: sqlite3.Connection, code: str, timeframe: str) -> int:
    """统计 A_STOCK 单只代码在指定 timeframe 的行数。"""
    code = code.upper()
    timeframe = normalize_timeframe(timeframe)
    row = conn.execute(
        "SELECT COUNT(*) FROM bars WHERE market = ? AND symbol = ? AND timeframe = ?",
        (A_STOCK_MARKET, code, timeframe),
    ).fetchone()
    return int(row[0] if row else 0)


def resolve_a_stock_csv(
    code: str,
    timeframe: str,
    cache_path: Path,
    *,
    data_source: str = "auto",
    db_path: str | Path = "data/market_data.sqlite",
    min_rows: int = MIN_DB_ROWS,
    start: str = "",
    end: str = "",
) -> tuple[Path, str]:
    """A 股 K 线 CSV 解析：DB → cache → missing。"""
    code = code.upper().zfill(6)
    timeframe = normalize_timeframe(timeframe)
    data_source = data_source.lower()
    cache_path = Path(cache_path)

    if data_source in {"auto", "db"}:
        db_file = Path(db_path)
        if db_file.exists():
            conn = connect(db_file)
            init_db(conn)
            if db_bar_count(conn, code, timeframe) >= min_rows:
                cache_path.parent.mkdir(parents=True, exist_ok=True)
                rows = export_csv(
                    conn, A_STOCK_MARKET, code, timeframe, cache_path, start=start, end=end
                )
                if rows >= min_rows:
                    return cache_path, "db"
            if data_source == "db":
                raise FileNotFoundError(
                    f"DB missing A_STOCK {code} {timeframe} "
                    f"(need>={min_rows} rows) in {db_file}"
                )

    if cache_path.exists() and cache_path.stat().st_size > 50:
        return cache_path, "cache"
    if data_source == "db":
        raise FileNotFoundError(f"DB export failed and no cache: {cache_path}")
    return cache_path, "missing"
