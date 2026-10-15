"""行为测试：fengji_core.radar_ranking（期望值排序，默认关闭 + 影子对比）。"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from fengji_core.radar_ranking import (
    annotate_rows,
    expectancy_for,
    format_shadow_report,
    load_bucket_stats,
    negative_evidence,
    rank_rows,
    shadow_compare,
    strategy_level_stats,
)


def _stats() -> dict[str, dict]:
    return {
        # 样本 100、胜率下界 > 0.5：可用于决策
        "DS01|camp=UNKNOWN": {"count": 100, "wins": 65, "avg_r": 0.9, "sample_confidence": 1.0},
        # 期望明显更低但仍可信
        "DS09|camp=UNKNOWN": {"count": 100, "wins": 62, "avg_r": 0.2, "sample_confidence": 1.0},
        # 样本不足：不可用于决策
        "DS03|camp=UNKNOWN": {"count": 12, "wins": 11, "avg_r": 2.0, "sample_confidence": 0.4},
    }


def _row(symbol: str, strategy: str, score: float) -> dict:
    return {"symbol": symbol, "strategy_id": strategy, "status": "PENDING", "score": score}


def test_load_bucket_stats_json_and_csv(tmp_path: Path) -> None:
    json_path = tmp_path / "ops.json"
    json_path.write_text(json.dumps({"market": "FUTURES", "buckets": _stats()}), encoding="utf-8")
    assert len(load_bucket_stats(json_path)) == 3

    csv_path = tmp_path / "stats.csv"
    csv_path.write_text(
        "strategy_id,market,bucket_key,count,wins,avg_r,sample_confidence\n"
        "DS01,FUTURES,DS01|camp=UNKNOWN,100,65,0.9,1.0\n",
        encoding="utf-8",
    )
    loaded = load_bucket_stats(csv_path)
    assert loaded["DS01|camp=UNKNOWN"]["avg_r"] == pytest.approx(0.9)


def test_load_bucket_stats_missing_file_returns_empty(tmp_path: Path) -> None:
    assert load_bucket_stats(tmp_path / "nope.json") == {}


def test_strategy_level_stats_weighted_by_count() -> None:
    merged = strategy_level_stats(_stats())
    assert set(merged) == {"DS01", "DS09", "DS03"}
    assert merged["DS01"]["count"] == 100
    assert merged["DS01"]["avg_r"] == pytest.approx(0.9)


def test_expectancy_requires_actionable_evidence() -> None:
    assert expectancy_for(_stats()["DS01|camp=UNKNOWN"]) == pytest.approx(0.9)
    # 样本 12、看着 2.0R 的暴利桶：证据不足 → 不给正期望（防小样本噪声排到最前）
    assert expectancy_for(_stats()["DS03|camp=UNKNOWN"]) is None
    assert expectancy_for(None) is None
    assert expectancy_for({}) is None


def test_expectancy_shrinks_with_low_confidence() -> None:
    solid = expectancy_for({"count": 100, "wins": 65, "avg_r": 0.9, "sample_confidence": 1.0})
    shaky = expectancy_for({"count": 100, "wins": 65, "avg_r": 0.9, "sample_confidence": 0.3})
    assert shaky is not None and solid is not None
    assert shaky < solid


def test_rank_rows_puts_high_expectancy_first() -> None:
    payload = [_row("AAA", "DS09", 1.0), _row("BBB", "DS01", 50.0)]
    ranked = rank_rows(payload, _stats())
    # DS01 期望更高 → 尽管距离（score）更大，仍排前面
    assert ranked[0]["strategy_id"] == "DS01"
    assert ranked[1]["strategy_id"] == "DS09"


def test_rows_without_evidence_fall_back_to_distance() -> None:
    payload = [_row("AAA", "DS03", 5.0), _row("BBB", "DS01", 50.0), _row("CCC", "UNKNOWN", 1.0)]
    ranked = rank_rows(payload, _stats())
    assert ranked[0]["strategy_id"] == "DS01"  # 有正期望
    # 无统计证据的两个按距离排序：score 1.0 的 CCC 先于 score 5.0 的 DS03
    assert [row["symbol"] for row in ranked[1:]] == ["CCC", "AAA"]


def test_annotate_rows_marks_stats_count() -> None:
    annotated = annotate_rows([_row("AAA", "DS01", 1.0)], _stats())
    assert annotated[0]["stats_count"] == 100
    assert annotated[0]["expectancy"] == pytest.approx(0.9)


def test_negative_evidence_requires_enough_samples() -> None:
    # 样本不足：即便看着巨亏也不能判负（避免小样本噪声误杀）
    assert negative_evidence({"count": 10, "wins": 1, "avg_r": -1.0}) is False
    # 样本足够且 R 为负
    assert negative_evidence({"count": 272, "wins": 67, "avg_r": -0.21}) is True
    # R 缺失（国内台账无 initial_stop）时用 avg_net 判负
    assert negative_evidence({"count": 193, "wins": 34, "avg_r": None, "avg_net": -595.76}) is True
    assert negative_evidence({"count": 100, "wins": 60, "avg_r": None, "avg_net": 12.0}) is False
    assert negative_evidence(None) is False


def test_negative_expectancy_ranks_behind_no_evidence() -> None:
    """实测缺口：DS01 n=272、avg_r=-0.21 若只按「无正期望」处理，会与样本不足的
    新策略同级按距离排，继续被优先推荐。负期望必须单独垫后。"""
    stats = {
        "DS01|camp=UNKNOWN": {"count": 272, "wins": 67, "avg_r": -0.21, "sample_confidence": 1.0},
        "DS03|camp=UNKNOWN": {"count": 12, "wins": 6, "avg_r": 0.5, "sample_confidence": 0.4},
    }
    payload = [_row("AAA", "DS01", 0.1), _row("BBB", "DS03", 5.0)]
    ranked = rank_rows(payload, stats)
    # DS01 距触发更近（score 0.1）但历史为负 → 排在样本不足的 DS03 之后
    assert [row["strategy_id"] for row in ranked] == ["DS03", "DS01"]
    assert rank_rows(payload, stats)[1]["negative"] is True


def test_shadow_compare_reports_negative_demotion() -> None:
    stats = {"DS01|camp=UNKNOWN": {"count": 272, "wins": 67, "avg_r": -0.21, "sample_confidence": 1.0}}
    report = shadow_compare([_row("AAA", "DS01", 0.1), _row("BBB", "DS09", 5.0)], stats, top_n=2)
    assert report["scored_rows"] == 0
    assert report["negative_rows"] == 1
    assert report["negative_strategies"] == ["DS01(n=272)"]
    assert "负期望降权=1" in format_shadow_report(report)


def test_shadow_compare_reports_churn() -> None:
    payload = [_row("AAA", "DS09", 1.0), _row("BBB", "DS01", 50.0), _row("CCC", "DS09", 2.0)]
    report = shadow_compare(payload, _stats(), top_n=2)
    assert report["top_n"] == 2
    # 按距离取前 2：AAA、CCC；按期望取前 2：BBB(DS01) + AAA/CCC 中期望较高者
    assert "BBB|DS01|PENDING" in report["enter"]
    assert len(report["exit"]) == 1
    assert "strategy-decay" not in format_shadow_report(report)


def test_shadow_compare_without_stats_is_noop_safe() -> None:
    payload = [_row("AAA", "DS09", 1.0)]
    report = shadow_compare(payload, {}, top_n=1)
    assert report["scored_rows"] == 0
    assert report["enter"] == [] and report["exit"] == []


def test_pending_order_priority_unchanged_when_weight_zero() -> None:
    """回归契约：期望值权重为 0（默认）时，挂单优先级必须与改动前完全一致。"""
    from fengji_pending_orders import convert_radar_rows

    rows = [
        {
            "symbol": "RB2601",
            "strategy_id": "DS01",
            "timeframe": "1d",
            "side": "long",
            "status": "PENDING",
            "trigger_price": 100.0,
            "current_price": 99.0,
            "stop_price": 90.0,
            "distance_pct": 0.01,
            "setup_key": "",
            "os_camp": "",
            "latest_time": "2026-10-07 10:00:00",
            "setup": "",
            "reason": "",
        }
    ]
    base = convert_radar_rows(rows, include_strategies={"DS01"}, include_triggered=False, max_distance_pct=0.08)
    with_stats = convert_radar_rows(
        rows,
        include_strategies={"DS01"},
        include_triggered=False,
        max_distance_pct=0.08,
        stats=_stats(),
        expectancy_weight=0.0,
    )
    assert base and with_stats
    assert base[0].priority == with_stats[0].priority

    weighted = convert_radar_rows(
        rows,
        include_strategies={"DS01"},
        include_triggered=False,
        max_distance_pct=0.08,
        stats=_stats(),
        expectancy_weight=10.0,
    )
    assert weighted[0].priority < base[0].priority  # 正期望 → 优先级提升（值更小）
