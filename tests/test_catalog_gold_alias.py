"""黄金/白银等期货俗称须解析为 AU/AG，不能当 A 股代码。"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_futures_cn_aliases_include_gold_silver() -> None:
    js = (ROOT / "web" / "js" / "config.js").read_text(encoding="utf-8")
    assert "FUTURES_CN_ALIASES" in js
    assert "黄金" in js
    assert '黄金: "AU"' in js or '黄金":"AU"' in js.replace(" ", "")


def test_resolve_watch_entry_cross_market_gold() -> None:
    js = (ROOT / "web" / "js" / "app.js").read_text(encoding="utf-8")
    assert "crossFutures" in js
    assert "validateSymbolMarketPair" in js
    assert "不是 A 股代码" in js


def test_backtest_validates_market_pair() -> None:
    html = (ROOT / "web" / "backtest.html").read_text(encoding="utf-8")
    assert "validateSymbolMarketPair" in html
    assert "entry.market" in html
