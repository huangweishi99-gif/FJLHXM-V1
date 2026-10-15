"""行为测试：fengji_core.strategy_decay（策略衰退检测，纯只读告警）。"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from fengji_core.live_ops_stats import LiveOpsStats
from fengji_core.strategy_decay import detect, evaluate_strategy, format_report


def _close(strategy: str = "DS01", net: float = 10.0, r: float = 1.0, reason: str = "target") -> dict:
    return {
        "event_type": "close",
        "strategy_id": strategy,
        "symbol": "RB2601",
        "side": 1,
        "entry_price": 100.0,
        "exit_price": 110.0 if net > 0 else 95.0,
        "initial_stop": 90.0,
        "net_pnl": net,
        "exit_reason": reason,
    }


def _seed(
    stats: LiveOpsStats,
    *,
    wins: int,
    losses: int,
    strategy: str = "DS01",
    net_win: float = 10.0,
    net_loss: float = -8.0,
) -> None:
    """交错写入胜负，避免「先全胜后全负」让近期窗口自带偏差。"""
    events: list[dict] = []
    for index in range(max(wins, losses)):
        if index < wins:
            events.append(_close(strategy=strategy, net=net_win))
        if index < losses:
            events.append(_close(strategy=strategy, net=net_loss, r=-0.8, reason="stop"))
    stats.record(events)


def test_stable_strategy_has_no_alert(tmp_path: Path) -> None:
    stats = LiveOpsStats(tmp_path / "s.json", "FUTURES")
    _seed(stats, wins=60, losses=40)  # 历史 60% 胜率
    # 近期延续同样表现
    _seed(stats, wins=12, losses=8)

    result = evaluate_strategy(stats.snapshot(), "DS01", window=20)
    assert result["enough_evidence"] is True
    assert result["level"] is None
    assert result["recent"]["win_rate"] == pytest.approx(0.6)


def test_decaying_strategy_raises_alert(tmp_path: Path) -> None:
    stats = LiveOpsStats(tmp_path / "s.json", "CRYPTO")
    _seed(stats, wins=60, losses=40)  # 基线 60% 胜率、正 R
    # 近期崩塌：20 笔里只赢 4 笔，R 转负
    stats.record([_close(net=10.0) for _ in range(4)] + [_close(net=-8.0, r=-0.8, reason="stop") for _ in range(16)])

    result = evaluate_strategy(stats.snapshot(), "DS01", window=20)
    assert result["level"] == "severe"
    assert result["recent"]["win_rate"] == pytest.approx(0.2)
    assert result["baseline"]["count"] == 100  # 累计 120 - 近期 20
    assert any("胜率下滑" in text for text in result["reasons"])


def test_insufficient_evidence_is_not_flagged(tmp_path: Path) -> None:
    stats = LiveOpsStats(tmp_path / "s.json", "FUTURES")
    _seed(stats, wins=6, losses=4)
    stats.record([_close(net=-8.0, r=-0.8, reason="stop") for _ in range(5)])

    result = evaluate_strategy(stats.snapshot(), "DS01", window=20)
    assert result["enough_evidence"] is False
    assert result["level"] is None


def test_detect_groups_all_strategies(tmp_path: Path) -> None:
    stats = LiveOpsStats(tmp_path / "s.json", "FUTURES")
    _seed(stats, wins=60, losses=40)  # DS01：稳定，基线 60% 胜率
    _seed(stats, wins=24, losses=16, strategy="DS09")  # DS09：先攒够基线样本
    # DS09 近期崩塌（基线样本已 >= 30，应被判定）
    stats.record([_close(strategy="DS09", net=10.0) for _ in range(3)] + [_close(strategy="DS09", net=-8.0, r=-0.8, reason="stop") for _ in range(17)])

    report = detect(stats.snapshot(), window=20)
    assert report["market"] == "FUTURES"
    assert report["strategies"] == 2
    flagged = {item["strategy"]: item["level"] for item in report["alerts"]}
    assert flagged.get("DS09") == "severe"
    assert "DS01" not in flagged  # 稳定策略不告警


def test_detect_handles_empty_stats() -> None:
    report = detect({"market": "FUTURES", "buckets": {}, "recent": []})
    assert report["alerts"] == []
    assert report["strategies"] == 0


def test_format_report_mentions_alerts(tmp_path: Path) -> None:
    stats = LiveOpsStats(tmp_path / "s.json", "FUTURES")
    _seed(stats, wins=60, losses=40)
    stats.record([_close(net=-8.0, r=-0.8, reason="stop") for _ in range(20)])
    text = format_report(detect(stats.snapshot(), window=20))
    assert "DS01" in text and "SEVERE" in text


def test_recent_window_is_bounded(tmp_path: Path) -> None:
    stats = LiveOpsStats(tmp_path / "s.json", "FUTURES")
    _seed(stats, wins=150, losses=150)
    data = json.loads((tmp_path / "s.json").read_text(encoding="utf-8"))
    assert len(data["recent"]) <= 200  # RECENT_LIMIT，防止统计文件无限增长
