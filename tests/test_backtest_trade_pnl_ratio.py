"""回测页净盈亏百分比：PG 样本不得批量出现 ±100% 假值。"""
from __future__ import annotations

import pytest

from services.db.context_queries import list_trades_with_strength


def _trade_return_ratio(trade: dict) -> float | None:
    entry = trade.get("entry_price") or trade.get("avg_entry_price")
    exit_p = trade.get("exit_price")
    side = trade.get("side")
    try:
        entry_f = float(entry)
        exit_f = float(exit_p)
    except (TypeError, ValueError):
        entry_f = exit_f = 0.0
    if entry_f <= 0 or exit_f <= 0:
        pnl = trade.get("net_pnl")
        try:
            return float(pnl) / 100_000.0 if pnl is not None else None
        except (TypeError, ValueError):
            return None
    is_short = side in (-1, "-1", "short")
    return (entry_f - exit_f) / entry_f if is_short else (exit_f - entry_f) / entry_f


@pytest.mark.parametrize(
    "symbol,market,strategy",
    [
        ("SOLUSDT", "CRYPTO", "DS01"),
        ("沪金", "FUTURES", "DS01"),
        ("000021", "A_STOCK", "DS01"),
    ],
)
def test_pg_trades_pnl_not_fake_hundred_pct(symbol: str, market: str, strategy: str) -> None:
    try:
        rows = list_trades_with_strength(symbol=symbol, market=market, strategy_id=strategy, limit=80)
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"PG unavailable: {exc}")
    if not rows:
        pytest.skip(f"no PG trades for {symbol}/{strategy}")

    fake = []
    for row in rows:
        ratio = _trade_return_ratio(row)
        if ratio is None:
            continue
        if abs(abs(ratio) - 1.0) < 1e-9:
            fake.append(row.get("trade_id"))
    assert len(fake) <= max(1, len(rows) // 20), f"too many ±100% trades for {symbol}: {fake[:5]}"


def test_pg_trades_have_exit_price_majority() -> None:
    try:
        rows = list_trades_with_strength(symbol="SOLUSDT", market="CRYPTO", strategy_id="DS01", limit=50)
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"PG unavailable: {exc}")
    if len(rows) < 5:
        pytest.skip("insufficient SOLUSDT samples")
    with_exit = sum(1 for r in rows if r.get("exit_price") not in (None, "", 0))
    assert with_exit / len(rows) >= 0.8
