from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SERVICES = str(ROOT / "services")
if SERVICES not in sys.path:
    sys.path.insert(0, SERVICES)

from db.context_queries import _context_float, _futures_symbol_aliases  # noqa: E402
from services.api.main import _with_chart_data_flag, resolve_csv  # noqa: E402


def test_futures_symbol_aliases_strip_usdt_suffix() -> None:
    assert _futures_symbol_aliases("PVCUSDT") == ["PVCUSDT", "PVC"]
    assert _futures_symbol_aliases("PVC") == ["PVC"]


def test_context_float_parses_exit_price_for_web_csv() -> None:
    assert _context_float({"exit_price": "123.45"}, "exit_price") == 123.45
    assert _context_float({"exit_price": 678}, "exit_price") == 678.0
    assert _context_float({"exit_price": ""}, "exit_price") is None
    assert _context_float({}, "exit_price") is None


def test_resolve_csv_supports_us_stock_cache() -> None:
    path = resolve_csv("AAPL", "US_STOCK")
    assert path.name == "AAPL_1D.csv"


def test_symbol_summary_marks_chart_data_availability() -> None:
    rows = _with_chart_data_flag(
        [
            {"market": "US_STOCK", "symbol": "AAPL", "trade_count": 1},
            {"market": "CRYPTO", "symbol": "NO_SUCH_SYMBOL", "trade_count": 1},
        ]
    )
    assert rows[0]["has_chart_data"] is True
    assert rows[0]["chart_source_file"] == "AAPL_1D.csv"
    assert rows[1]["has_chart_data"] is False
    assert rows[1]["chart_source_file"] is None
