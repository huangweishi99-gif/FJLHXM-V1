"""行为测试：风险平价仓位（src/fengji_futures_pending_order_monitor.resolve_lots）。

固定 1 手的问题：同样 1 手，高波动品种的止损金额可能是低波动品种的数倍。
risk 模式让每笔「打到止损」的亏损金额一致。默认仍是 fixed（行为不变）。
"""
from __future__ import annotations

import argparse

from fengji_futures_pending_order_monitor import DEFAULT_SYMBOL_EQUITY, resolve_lots


def _args(**overrides) -> argparse.Namespace:
    base = dict(lots=1, sizing="fixed", risk_per_trade=0.01, max_lots=10)
    base.update(overrides)
    return argparse.Namespace(**base)


def test_fixed_mode_keeps_legacy_behaviour() -> None:
    """回归契约：默认 fixed 模式手数就是 --lots，与改动前完全一致。"""
    state = {"equity": DEFAULT_SYMBOL_EQUITY}
    assert resolve_lots(_args(lots=3), state, entry=100.0, stop=90.0, multiplier=10) == 3
    assert resolve_lots(_args(), state, entry=100.0, stop=90.0, multiplier=10) == 1


def test_risk_mode_sizes_by_stop_distance() -> None:
    state = {"equity": 100_000.0}
    args = _args(sizing="risk", risk_per_trade=0.01)
    # 预算 1000；每手风险 = (100-90) × 10 = 100 → 10 手
    assert resolve_lots(args, state, entry=100.0, stop=90.0, multiplier=10) == 10
    # 止损更远（每手风险 500）→ 2 手
    assert resolve_lots(args, state, entry=100.0, stop=50.0, multiplier=10) == 2


def test_risk_mode_never_exceeds_budget() -> None:
    state = {"equity": 100_000.0}
    args = _args(sizing="risk", risk_per_trade=0.01)
    lots = resolve_lots(args, state, entry=100.0, stop=97.0, multiplier=10)
    assert lots * (3.0 * 10) <= 1000.0  # 向下取整，绝不超预算


def test_risk_mode_respects_max_lots() -> None:
    state = {"equity": 10_000_000.0}
    args = _args(sizing="risk", risk_per_trade=0.01, max_lots=5)
    assert resolve_lots(args, state, entry=100.0, stop=99.0, multiplier=10) == 5


def test_risk_mode_falls_back_when_inputs_missing() -> None:
    state = {"equity": 100_000.0}
    args = _args(sizing="risk", lots=2)
    assert resolve_lots(args, state, entry=100.0, stop=0.0, multiplier=10) == 2  # 无止损价
    assert resolve_lots(args, state, entry=0.0, stop=90.0, multiplier=10) == 2  # 无入场价
    assert resolve_lots(args, state, entry=100.0, stop=90.0, multiplier=0) == 2  # 无乘数


def test_risk_mode_always_at_least_one_lot() -> None:
    state = {"equity": 1000.0}  # 预算 10，每手风险 100 → 0 手，但至少 1 手
    args = _args(sizing="risk", risk_per_trade=0.01)
    assert resolve_lots(args, state, entry=100.0, stop=90.0, multiplier=10) == 1


def test_risk_equalizes_loss_across_volatility() -> None:
    """核心目的：不同波动的品种，止损亏损金额被拉到同一水平。"""
    state = {"equity": 200_000.0}
    args = _args(sizing="risk", risk_per_trade=0.01, max_lots=100)
    calm_lots = resolve_lots(args, state, entry=3000.0, stop=2980.0, multiplier=10)
    wild_lots = resolve_lots(args, state, entry=3000.0, stop=2900.0, multiplier=10)
    calm_loss = calm_lots * 20.0 * 10
    wild_loss = wild_lots * 100.0 * 10
    assert calm_lots > wild_lots  # 波动大的少买
    assert abs(calm_loss - wild_loss) <= max(calm_loss, wild_loss) * 0.35  # 风险大致持平
