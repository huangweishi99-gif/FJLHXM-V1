"""Catalog display labels must not duplicate futures Chinese names."""
from __future__ import annotations

from services.chart_symbol_catalog import merge_symbol_summary


def test_futures_merged_display_includes_code_not_dup_name() -> None:
    rows = merge_symbol_summary(
        [{"market": "FUTURES", "symbol": "豆粕", "trade_count": 10, "strategy_count": 2}],
        "FUTURES",
        chart_symbols=["M"],
    )
    hit = next(r for r in rows if r.get("symbol") == "豆粕" or r.get("display_symbol", "").startswith("豆粕"))
    assert hit["display_symbol"] == "豆粕(M)"
    assert hit["symbol_name"] == "豆粕"


def test_symbol_summary_row_label_dedup_in_app_js() -> None:
    from pathlib import Path

    js = (Path(__file__).resolve().parents[1] / "web" / "js" / "app.js").read_text(encoding="utf-8")
    assert "function catalogDisplayLabel" in js
    assert "code.includes(name)" in js
