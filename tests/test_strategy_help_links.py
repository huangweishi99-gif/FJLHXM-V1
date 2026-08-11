"""O2 · 定式帮助深链到 strategies.html."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP_JS = ROOT / "web" / "js" / "app.js"


def test_strategy_help_helper_exported() -> None:
    text = APP_JS.read_text(encoding="utf-8")
    assert "function strategyHelpLinkHtml" in text
    assert "strategyHelpLinkHtml," in text
    assert "定式帮助" in text


def test_strategy_help_wired_in_core_pages() -> None:
    pages = {
        "index.html": "strategyHelpLinkHtml",
        "backtest.html": "strategyHelpLinkHtml",
        "monitor.html": "strategyHelpLinkHtml",
        "symbol.html": "strategyHelpLink",
    }
    for name, marker in pages.items():
        html = (ROOT / "web" / name).read_text(encoding="utf-8")
        assert marker in html, f"missing {marker} in {name}"


def test_strategy_deep_link_url_pattern() -> None:
    text = APP_JS.read_text(encoding="utf-8")
    assert 'p.set("open", "1")' in text
    assert "strategies.html?" in text
