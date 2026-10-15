"""行为测试：统计可信度闸门（Wilson 置信下界 / 决策门槛 / 多重检验校正）。

背景：分桶维度 6 个 → 桶数上千 → 30 样本胜率标准误 ±9pp，直接拿点估计挑「优质桶」
就是多重检验下的过拟合。本文件锁定「分级只看置信下界、下单要过更严闸门」的契约。
"""
from __future__ import annotations

import pandas as pd
import pytest

from fengji_core.context_score import (
    ACTIONABLE_MIN_SAMPLES,
    benjamini_hochberg,
    bucket_p_value,
    is_actionable,
    score_bucket_row,
    wilson_lower_bound,
)
from fengji_core.context_stats import aggregate_bucket_stats


def test_wilson_lower_bound_shrinks_small_samples() -> None:
    assert wilson_lower_bound(0, 0) == 0.0
    low = wilson_lower_bound(9, 10)  # 点估计 0.9，样本极小
    assert 0.5 < low < 0.7
    assert low < 0.9


def test_wilson_lower_bound_tightens_with_more_samples() -> None:
    small = wilson_lower_bound(60, 100)
    large = wilson_lower_bound(600, 1000)
    assert large > small  # 样本越大，下界越贴近真实胜率


def test_conservative_score_penalizes_small_samples() -> None:
    row = score_bucket_row(count=10, wins=9, avg_r=1.0, market=None)
    assert row["win_rate"] == pytest.approx(0.9)
    assert row["signal_score_conservative"] < row["signal_score"]
    # 样本低于最小阈值 → 不论分数多高都不得出分级结论
    assert row["signal_tier"] == "INSUFFICIENT_DATA"


def test_tier_uses_conservative_not_point_estimate() -> None:
    """样本刚够阈值、胜率看着漂亮时，保守分必须显著低于点估计分。"""
    row = score_bucket_row(count=30, wins=24, avg_r=1.0, market=None)
    assert row["win_rate_smoothed"] > row["win_rate_ci_low"]
    assert row["signal_score_conservative"] < row["signal_score"]


def test_is_actionable_requires_samples_and_edge() -> None:
    few = score_bucket_row(count=10, wins=10, avg_r=1.0, market=None)
    assert is_actionable(few) is False  # 样本不足，哪怕全胜

    no_edge = score_bucket_row(count=200, wins=100, avg_r=1.0, market=None)
    assert is_actionable(no_edge) is False  # 样本足但没有正优势（下界 <= 0.5）

    solid = score_bucket_row(count=200, wins=130, avg_r=1.0, market=None)
    assert is_actionable(solid) is True


def test_is_actionable_custom_threshold() -> None:
    row = score_bucket_row(count=40, wins=32, avg_r=1.0, market=None)
    assert is_actionable(row) is False  # 默认门槛 80
    assert is_actionable(row, min_samples=30) is True
    assert ACTIONABLE_MIN_SAMPLES == 80


def test_benjamini_hochberg_controls_false_discovery() -> None:
    flags = benjamini_hochberg([0.001, 0.04, 0.5, 0.9], alpha=0.05)
    assert flags == [True, False, False, False]
    assert benjamini_hochberg([], alpha=0.05) == []


def test_bucket_p_value_detects_real_edge() -> None:
    assert bucket_p_value(65, 100) < 0.01
    assert bucket_p_value(51, 100) > 0.5
    assert bucket_p_value(0, 0) == 1.0


def test_aggregate_exposes_confidence_columns() -> None:
    snapshots = pd.DataFrame(
        [
            {"trade_id": f"t{i}", "strategy_id": "DS01", "market": "CRYPTO", "net_pnl": 10.0 if i % 2 else -5.0, "r_multiple": 1.0}
            for i in range(10)
        ]
        + [
            {"trade_id": f"c{i}", "strategy_id": "DS01", "market": "CRYPTO", "net_pnl": 20.0, "r_multiple": 2.0}
            for i in range(30)
        ]
    )
    stats = aggregate_bucket_stats(snapshots)
    for column in ("win_rate_ci_low", "signal_score_conservative", "actionable", "signal_score", "signal_tier"):
        assert column in stats.columns
    row = stats.iloc[0]
    assert row["count"] == 40
    assert row["win_rate_ci_low"] <= row["win_rate_smoothed"]
    # 样本 40 < 决策门槛 80：可用于展示，但不足以支撑下单
    assert bool(row["actionable"]) is False
