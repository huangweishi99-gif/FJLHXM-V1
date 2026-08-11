"""Backtest page: symbol search parity with monitor (alias + ranked match)."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_backtest_symbol_list_uses_filter_query_not_display_value() -> None:
    html = (ROOT / "web" / "backtest.html").read_text(encoding="utf-8")
    assert "symbolFilterQuery" in html
    assert 'renderSymbolList("")' not in html or "symbolFilterQuery || symbolSearchEl.value.trim()" in html
    assert "renderSymbolList(symbolSearchEl.value)" not in html
    assert "symbolCatalog.length" in html


def test_backtest_uses_shared_catalog_search_helpers() -> None:
    html = (ROOT / "web" / "backtest.html").read_text(encoding="utf-8")
    for name in (
        "catalogRowMatchesQuery",
        "sortCatalogRowsByQuery",
        "resolveWatchEntryInput",
        "resolveBacktestSymbol",
        "applySymbolEntry",
    ):
        assert name in html
    assert "code.includes(q) || label.includes(q)" not in html


def test_backtest_custom_instrument_panel_all_markets() -> None:
    html = (ROOT / "web" / "backtest.html").read_text(encoding="utf-8")
    assert "symbolNeedsCustomSubmit" in html
    assert "customInstrumentHint" in html
    assert "当前仅支持虚拟货币自选回测" not in html


def test_backtest_script_cache_buster() -> None:
    html = (ROOT / "web" / "backtest.html").read_text(encoding="utf-8")
    assert "js/app.js?v=20260612d" in html
    assert "js/config.js?v=20260612d" in html
