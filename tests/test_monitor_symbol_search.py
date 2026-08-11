"""Monitor page: full catalog search (W16/W14 parity with backtest symbol-summary)."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_monitor_html_uses_symbol_search_not_static_pick() -> None:
    html = (ROOT / "web" / "monitor.html").read_text(encoding="utf-8")
    assert 'id="symbolSearch"' in html
    assert 'id="symbolPick"' in html
    assert 'id="marketFilter"' in html
    assert "monitor-page-main" in html
    assert "monitor-page-head" in html
    assert "fetchAllSymbolSummary" in html
    assert "symbolFilterQuery" in html


def test_monitor_html_market_tabs_filter_table() -> None:
    html = (ROOT / "web" / "monitor.html").read_text(encoding="utf-8")
    assert 'id="marketTabs"' in html
    assert 'data-market="FUTURES"' in html
    assert "filterRowsForTableTab" in html
    assert "setMarketView" in html
    assert 'role="tablist"' in html


def test_monitor_html_v1_plus_panels() -> None:
    html = (ROOT / "web" / "monitor.html").read_text(encoding="utf-8")
    assert 'id="monitorNotifications"' in html
    assert 'id="paperAccountCard"' in html
    assert 'id="ledgerPanel"' in html
    assert "refreshLedger" in html
    assert "badAuditsForItem" in html
    assert "monitor-audit-badge" in html
    assert "pushMonitorNotification" in html
    assert "queueMicrotask(bootMonitorTransport)" in html


def test_monitor_css_v1_plus_styles() -> None:
    css = (ROOT / "web" / "css" / "apple.css").read_text(encoding="utf-8")
    for cls in (
        ".monitor-notifications",
        ".monitor-paper-card",
        ".monitor-ledger-card",
        ".monitor-audit-badge",
    ):
        assert cls in css


def test_monitor_css_market_tabs_bar() -> None:
    css = (ROOT / "web" / "css" / "apple.css").read_text(encoding="utf-8")
    assert ".monitor-market-tabs-bar" in css
    assert ".monitor-market-tabs" in css


def test_monitor_html_balances_all_markets_catalog_slice() -> None:
    html = (ROOT / "web" / "monitor.html").read_text(encoding="utf-8")
    assert "sliceCatalogRows" in html
    assert "catalogRowMatchesQuery" in html
    assert "resolveWatchEntryInput" in html
    assert "data-manual" in html
    assert ".slice(0, 200)" not in html


def test_monitor_css_allows_search_dropdown_overflow() -> None:
    css = (ROOT / "web" / "css" / "apple.css").read_text(encoding="utf-8")
    assert ".monitor-watch-card.bt-card" in css
    assert ".monitor-add-bar" in css
    add_bar = css.split(".monitor-add-bar {", 1)[1].split("}", 1)[0]
    watch_card = css.split(".monitor-watch-card {", 1)[1].split("}", 1)[0]
    assert "overflow: visible" in add_bar
    assert "overflow: visible" in watch_card


def test_config_has_futures_cn_names_for_search_aliases() -> None:
    js = (ROOT / "web" / "js" / "config.js").read_text(encoding="utf-8")
    assert "FUTURES_CN_NAMES" in js
    assert 'V: "PVC"' in js


def test_app_js_exports_monitor_catalog_helpers() -> None:
    js = (ROOT / "web" / "js" / "app.js").read_text(encoding="utf-8")
    for name in (
        "fetchAllSymbolSummary",
        "lookupSymbolCatalogRow",
        "catalogRowToWatchEntry",
        "catalogDisplayLabel",
        "sliceCatalogRows",
        "catalogRowMatchesQuery",
        "sortCatalogRowsByQuery",
        "resolveWatchEntryInput",
        "symbolSummaryRowCode",
    ):
        assert name in js
        assert f"{name}," in js or f"{name}\n" in js
