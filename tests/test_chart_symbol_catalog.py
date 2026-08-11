from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services"))
sys.path.insert(0, str(ROOT / "packages" / "fengji_core"))

from chart_symbol_catalog import (  # noqa: E402
    list_a_stock_csv_symbols,
    list_crypto_csv_symbols,
    list_futures_csv_symbols,
    merge_symbol_summary,
)


def test_local_csv_catalog_not_empty() -> None:
    assert len(list_a_stock_csv_symbols()) >= 100
    assert len(list_futures_csv_symbols()) >= 30
    assert len(list_crypto_csv_symbols()) >= 10


def test_crypto_catalog_excludes_futures_mis_tags() -> None:
    codes = list_crypto_csv_symbols()
    for sym in ("AGUSDT", "BRUSDT", "ECUSDT"):
        assert sym not in codes, f"{sym} is domestic futures mis-tag, not crypto"


def test_futures_catalog_excludes_usdt_and_corrupt_stems() -> None:
    names = {n.upper() for n in list_futures_csv_symbols()}
    for bad in ("APTUSDT", "AGUSDT", "LC_CORRUPT"):
        assert bad not in names


def test_merge_symbol_summary_adds_chart_only_and_keeps_pg_stats() -> None:
    pg = [
        {"market": "A_STOCK", "symbol": "2475", "trade_count": 409, "strategy_count": 6},
    ]
    merged = merge_symbol_summary(pg, "A_STOCK", chart_symbols=["2475", "600519"])
    by_sym = {row["symbol"]: row for row in merged}
    assert by_sym["2475"]["trade_count"] == 409
    assert "600519" in by_sym or any(r.get("display_symbol") == "600519" for r in merged)
    chart_only = [r for r in merged if not r.get("has_pg_context", True)]
    assert any(r.get("display_symbol") == "600519" for r in chart_only)


def test_merge_futures_cn_name_and_code_same_key() -> None:
    pg = [{"market": "FUTURES", "symbol": "豆粕", "trade_count": 100, "strategy_count": 3}]
    merged = merge_symbol_summary(pg, "FUTURES", chart_symbols=["豆粕", "螺纹钢"])
    assert len(merged) >= 2
    names = {row["symbol"] for row in merged}
    assert "豆粕" in names
    assert "螺纹钢" in names
