"""BulkQuery 单元测试（用临时 sqlite + 临时 cache + 临时 adj_factor CSV）。

Design inspired by free-stockdb MIT © 2026 hello245m.
"""
from __future__ import annotations

import asyncio
import sqlite3
from pathlib import Path

import pandas as pd
import pytest

from adj_factor import AdjFactorIndex
from bulk_query import (
    BulkQuery,
    filter_by_date,
    normalize_field,
    normalize_frequency,
    project_fields,
)
from market_data_store import connect, init_db
from market_data_resolve_a_stock import A_STOCK_MARKET


# ===== Fixtures =====

def _write_a_stock_csv(csv_path: Path, rows: int = 50, start: str = "2020-01-01") -> None:
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    frame = pd.DataFrame(
        {
            "date": pd.date_range(start, periods=rows, freq="D"),
            "open": [10.0 + i * 0.1 for i in range(rows)],
            "high": [11.0 + i * 0.1 for i in range(rows)],
            "low": [9.5 + i * 0.1 for i in range(rows)],
            "close": [10.5 + i * 0.1 for i in range(rows)],
            "volume": [100000] * rows,
        }
    )
    frame.to_csv(csv_path, index=False, encoding="utf-8-sig")


def _write_adj_csv(path: Path, rows: list[tuple[str, str, float]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    out = "code,date,adj_factor\n"
    for code, d, factor in rows:
        out += f"{code},{d},{factor}\n"
    path.write_text(out, encoding="utf-8")


@pytest.fixture
def a_stock_cache(tmp_path: Path) -> Path:
    """data/a_stock/{code}_1D_qfq.csv 模拟目录。"""
    cache = tmp_path / "data" / "a_stock"
    _write_a_stock_csv(cache / "000021_1D_qfq.csv", rows=30, start="2020-01-01")
    _write_a_stock_csv(cache / "600036_1D_qfq.csv", rows=30, start="2020-02-01")
    return cache


@pytest.fixture
def adj_csv(tmp_path: Path) -> Path:
    p = tmp_path / "adj.csv"
    # 000021：30 天全覆盖（早期 0.5 → 中期 0.75 → 最新 1.0）
    rows: list[tuple[str, str, float]] = []
    for day in range(1, 31):
        date = f"2020-01-{day:02d}"
        if day <= 5:
            factor = 0.5
        elif day <= 14:
            factor = 0.75
        else:
            factor = 1.0
        rows.append(("000021", date, factor))
    _write_adj_csv(p, rows)
    return p


@pytest.fixture
def bq(a_stock_cache: Path, adj_csv: Path) -> BulkQuery:
    return BulkQuery(
        cache_dir=a_stock_cache,
        db_path=str(a_stock_cache / "no.db"),
        adj_factor_csv=adj_csv,
    )


# ===== normalize_frequency =====

def test_normalize_frequency():
    assert normalize_frequency("1d") == "1D"
    assert normalize_frequency("DAY") == "1D"
    assert normalize_frequency("日线") == "1D"
    assert normalize_frequency("60m") == "1H"
    assert normalize_frequency("60分钟") == "1H"
    assert normalize_frequency("15m") == "15m"
    assert normalize_frequency("5m") == "5m"
    # 未识别 → 原样返回
    assert normalize_frequency("xx") == "xx"


# ===== normalize_field =====

def test_normalize_field_known():
    assert normalize_field("date") == "date"
    assert normalize_field("open") == "open"
    assert normalize_field("开盘") == "open"
    assert normalize_field("close") == "close"
    assert normalize_field("vol") == "volume"
    assert normalize_field("amount") == "amount"
    assert normalize_field("pct_chg") == "pct_chg"


def test_normalize_field_unknown():
    with pytest.raises(ValueError, match="unknown field"):
        normalize_field("xyz")


# ===== project_fields / filter_by_date =====

def test_project_fields_basic():
    df = pd.DataFrame({"a": [1, 2], "b": [3, 4], "c": [5, 6]})
    out = project_fields(df, ["a", "b"])
    assert list(out.columns) == ["a", "b"]


def test_project_fields_unknown_raises():
    df = pd.DataFrame({"a": [1, 2]})
    with pytest.raises(ValueError, match="no fields"):
        project_fields(df, ["b", "c"])


def test_filter_by_date_range():
    df = pd.DataFrame({"date": ["2020-01-01", "2020-01-15", "2020-02-01"], "close": [1, 2, 3]})
    out = filter_by_date(df, start="2020-01-10", end="2020-01-31")
    assert len(out) == 1
    assert out.iloc[0]["close"] == 2


# ===== BulkQuery.get_data 同步 =====

def test_get_data_qfq_returns_dataframe(bq: BulkQuery):
    out = bq.get_data("000021", frequency="1d", fq="qfq")
    assert isinstance(out, pd.DataFrame)
    assert len(out) == 30
    assert set(["date", "open", "high", "low", "close", "volume"]).issubset(out.columns)


def test_get_data_with_date_filter(bq: BulkQuery):
    out = bq.get_data("000021", start="2020-01-10", end="2020-01-20", frequency="1d")
    # 2020-01-10 到 2020-01-20 共 11 天
    assert len(out) == 11
    assert pd.Timestamp(out.iloc[0]["date"]) >= pd.Timestamp("2020-01-10")


def test_get_data_desc_returns_latest(bq: BulkQuery):
    out = bq.get_data("000021", frequency="1d", desc=True, limit=5)
    assert len(out) == 5
    # desc=True 时 limit=5 → 取最新 5 条（iloc[0] 是最新日期）
    assert pd.Timestamp(out.iloc[0]["date"]) >= pd.Timestamp(out.iloc[1]["date"])
    assert pd.Timestamp(out.iloc[0]["date"]) == pd.Timestamp("2020-01-30")


def test_get_data_fields_projection(bq: BulkQuery):
    out = bq.get_data("000021", frequency="1d", fields=["date", "close"])
    assert list(out.columns) == ["date", "close"]


def test_get_data_as_dict(bq: BulkQuery):
    out = bq.get_data("000021", frequency="1d", as_df=False, limit=2)
    assert isinstance(out, list)
    assert len(out) == 2
    assert "close" in out[0]


def test_get_data_invalid_fq(bq: BulkQuery):
    with pytest.raises(ValueError, match="unknown fq"):
        bq.get_data("000021", frequency="1d", fq="xxff")


def test_get_data_missing_code_raises(bq: BulkQuery):
    with pytest.raises(FileNotFoundError, match="no DB and no cache"):
        bq.get_data("999999", frequency="1d")


def test_get_data_hfq_applies_adj_factor(bq: BulkQuery):
    """qfq → hfq 应按 adj_factor 折算 OHLCV。"""
    out_qfq = bq.get_data("000021", frequency="1d", fq="qfq")
    out_hfq = bq.get_data("000021", frequency="1d", fq="hfq")
    # 2020-01-01 qfq.close=10.5, adj=0.5 → hfq.close=5.25
    first_qfq = out_qfq.iloc[0]["close"]
    first_hfq = out_hfq.iloc[0]["close"]
    assert first_hfq == pytest.approx(first_qfq * 0.5)


def test_get_data_none_applies_adj_factor(bq: BulkQuery):
    out_qfq = bq.get_data("000021", frequency="1d", fq="qfq")
    out_none = bq.get_data("000021", frequency="1d", fq="none")
    # to_none 公式 = qfq * adj_factor（同 hfq）— 语义区分由调用方负责
    first_qfq = out_qfq.iloc[0]["close"]
    first_none = out_none.iloc[0]["close"]
    assert first_none == pytest.approx(first_qfq * 0.5)


def test_get_data_hfq_missing_adj_factor_raises(a_stock_cache: Path):
    """adj_factor CSV 不存在 → raise AdjFactorMissingError。"""
    bq = BulkQuery(
        cache_dir=a_stock_cache,
        db_path=str(a_stock_cache / "no.db"),
        adj_factor_csv=str(a_stock_cache / "no_adj.csv"),
    )
    with pytest.raises(Exception) as info:
        bq.get_data("000021", frequency="1d", fq="hfq")
    # 可能是 AdjFactorMissingError 或 FileNotFoundError（取决于 AdjFactor 解析路径）
    assert info.value.__class__.__name__ in ("AdjFactorMissingError", "FileNotFoundError")


def test_get_data_with_explicit_adj_index(a_stock_cache: Path, adj_csv: Path):
    """显式传入 AdjFactorIndex 应跳过自动加载。"""
    idx = AdjFactorIndex.from_csv(adj_csv)
    bq = BulkQuery(
        cache_dir=a_stock_cache,
        db_path=str(a_stock_cache / "no.db"),
        adj_factor_index=idx,
    )
    out = bq.get_data("000021", frequency="1d", fq="hfq", limit=1)
    assert len(out) == 1


# ===== BulkQuery.get_data_async =====

def test_get_data_async_returns_same_as_sync(bq: BulkQuery):
    sync = bq.get_data("000021", frequency="1d", fq="qfq", limit=5)
    async_result = asyncio.run(
        bq.get_data_async("000021", frequency="1d", fq="qfq", limit=5)
    )
    pd.testing.assert_frame_equal(sync, async_result)


def test_get_data_async_gather_multiple(bq: BulkQuery):
    """asyncio.gather 多个代码并发。"""
    codes = ["000021", "600036"]

    async def run():
        return await asyncio.gather(*[
            bq.get_data_async(code, frequency="1d") for code in codes
        ])

    results = asyncio.run(run())
    assert len(results) == 2
    assert all(isinstance(r, pd.DataFrame) for r in results)
    assert all(len(r) == 30 for r in results)
