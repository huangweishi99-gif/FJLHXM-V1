"""D6: market data coverage boundaries."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages" / "fengji_core"))

from fengji_core.market_coverage import (  # noqa: E402
    A_STOCK_H1_MIN_ROWS_DS07_DS08,
    filter_strategies_for_a_stock_data,
    futures_symbols_missing_night_map,
    h1_eligible_for_ds07_ds08,
)


def test_h1_threshold() -> None:
    assert not h1_eligible_for_ds07_ds08(128)
    assert h1_eligible_for_ds07_ds08(A_STOCK_H1_MIN_ROWS_DS07_DS08)


def test_filter_drops_ds07_ds08_on_partial_h1() -> None:
    allowed, skipped = filter_strategies_for_a_stock_data(
        ["DS01", "DS06", "DS07", "DS08"],
        h1_rows=200,
        m15_rows=1000,
    )
    assert allowed == ["DS01", "DS06"]
    assert any("DS07" in s for s in skipped)


def test_futures_night_map_covers_sim_symbols() -> None:
    symbols = ["SA", "RB", "AU", "SC", "LC", "EC"]
    assert futures_symbols_missing_night_map(symbols) == []


def test_backtest_imports_market_coverage() -> None:
    sys.path.insert(0, str(ROOT / "src"))
    import backtest_a_stock_fengji as mod

    assert mod.filter_strategies_for_a_stock_data is filter_strategies_for_a_stock_data
