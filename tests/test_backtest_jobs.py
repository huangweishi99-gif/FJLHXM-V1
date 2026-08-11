from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SERVICES = str(ROOT / "services")
if SERVICES not in sys.path:
    sys.path.insert(0, SERVICES)

from db.backtest_jobs import build_backtest_cache_key  # noqa: E402
from services.api.main import BacktestCreateRequest  # noqa: E402


def test_backtest_cache_key_is_normalized_and_stable() -> None:
    a = build_backtest_cache_key(market="crypto", symbol="ethusdt", strategy_id="total", years=3)
    b = build_backtest_cache_key(market="CRYPTO", symbol="ETHUSDT", strategy_id="TOTAL", years=3)
    c = build_backtest_cache_key(market="CRYPTO", symbol="ETHUSDT", strategy_id="DS03", years=3)
    assert a == b
    assert a.startswith("backtest:CRYPTO|ETHUSDT|TOTAL|3:")
    assert a != c


def test_backtest_create_request_bounds_years() -> None:
    req = BacktestCreateRequest(market="CRYPTO", symbol="ETHUSDT", strategy_id="DS07", years=5)
    assert req.years == 5
    assert req.strategy_id == "DS07"
