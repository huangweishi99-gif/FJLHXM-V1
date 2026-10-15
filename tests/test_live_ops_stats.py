"""行为测试：fengji_core.live_ops_stats（两端监控的实时操作统计，旁路可观测）。"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from fengji_core.context_score import score_bucket_row
from fengji_core.live_ops_stats import (
    LiveOpsStats,
    _r_multiple,
    _slippage,
    build_close_event,
    record_round,
    stats_path_for,
)


def _fill(strategy: str = "DS01", **extra) -> dict:
    return {
        "event_type": "fill",
        "strategy_id": strategy,
        "symbol": "RB2601",
        "side": 1,
        "trigger_price": 100.0,
        "fill_price": 100.5,
        **extra,
    }


def _close(strategy: str = "DS01", net: float = 10.0, reason: str = "target", **extra) -> dict:
    return {
        "event_type": "close",
        "strategy_id": strategy,
        "symbol": "RB2601",
        "side": 1,
        "entry_price": 100.0,
        "exit_price": 110.0,
        "initial_stop": 90.0,
        "net_pnl": net,
        "exit_reason": reason,
        **extra,
    }


def test_stats_path_for_market() -> None:
    path = stats_path_for("futures", Path("runtime"))
    assert path.name == "FUTURES_ops_stats.json"
    assert path.parent.name == "fengji_ops_stats"


def test_record_aggregates_win_rate_and_r(tmp_path: Path) -> None:
    stats = LiveOpsStats(tmp_path / "s.json", "FUTURES")
    stats.record([_fill(), _close(net=10.0), _close(net=-5.0)])

    data = json.loads((tmp_path / "s.json").read_text(encoding="utf-8"))
    bucket = next(iter(data["buckets"].values()))
    assert bucket["closes"] == 2 and bucket["wins"] == 1
    assert bucket["count"] == 2  # count 以平仓为准，与离线 accepted_trades 同口径
    assert bucket["win_rate"] == pytest.approx(0.5)
    assert bucket["avg_r"] == pytest.approx(1.0)  # (110-100)/|100-90|
    assert bucket["fills"] == 1
    assert data["events_total"] == 3


def test_fill_rate_and_stop_rate(tmp_path: Path) -> None:
    stats = LiveOpsStats(tmp_path / "s.json", "CRYPTO")
    stats.record(
        [
            _fill(),
            _fill(),
            {"event_type": "skip", "strategy_id": "DS01", "skip_reason": "risk"},
            {"event_type": "cancel", "strategy_id": "DS01"},
            _close(reason="stop", net=-8.0),
            _close(reason="target", net=6.0),
        ]
    )
    bucket = next(iter(json.loads((tmp_path / "s.json").read_text(encoding="utf-8"))["buckets"].values()))
    assert bucket["fill_rate"] == pytest.approx(2 / 4)  # fill / (fill + skip + cancel)
    assert bucket["stop_rate"] == pytest.approx(0.5)


def test_slippage_is_adverse_positive_for_both_sides() -> None:
    assert _slippage({"side": 1, "trigger_price": 100.0, "fill_price": 101.0}) == pytest.approx(0.01)
    assert _slippage({"side": -1, "trigger_price": 100.0, "fill_price": 99.0}) == pytest.approx(0.01)
    # 有利成交记负值
    assert _slippage({"side": 1, "trigger_price": 100.0, "fill_price": 99.0}) == pytest.approx(-0.01)
    assert _slippage({"side": 1, "trigger_price": 0, "fill_price": 1.0}) is None


def test_r_multiple_uses_side_and_missing_fields() -> None:
    assert _r_multiple({"side": -1, "entry_price": 100.0, "exit_price": 90.0, "initial_stop": 110.0}) == pytest.approx(1.0)
    assert _r_multiple({"side": 1, "entry_price": 100.0, "exit_price": 100.0, "initial_stop": 100.0}) is None
    assert _r_multiple({"side": 1, "entry_price": 100.0}) is None


def test_buckets_split_by_strategy_and_context(tmp_path: Path) -> None:
    stats = LiveOpsStats(tmp_path / "s.json", "FUTURES")
    stats.record([_close(strategy="DS01"), _close(strategy="DS09")])
    data = json.loads((tmp_path / "s.json").read_text(encoding="utf-8"))
    assert len(data["buckets"]) == 2
    assert any(key.startswith("DS01|") for key in data["buckets"])
    assert any(key.startswith("DS09|") for key in data["buckets"])


def test_close_event_merges_position_fields() -> None:
    event = build_close_event({"net_pnl": 3.0, "exit_price": 110.0}, position={"initial_stop": 90.0, "side": 1, "entry_price": 100.0})
    assert event["initial_stop"] == 90.0 and event["side"] == 1
    assert _r_multiple(event) == pytest.approx(1.0)


def test_totals_and_updated_at(tmp_path: Path) -> None:
    stats = LiveOpsStats(tmp_path / "s.json", "FUTURES")
    stats.record([_close(net=5.0)])
    data = json.loads((tmp_path / "s.json").read_text(encoding="utf-8"))
    assert data["market"] == "FUTURES"
    assert data["totals"]["count"] == 1
    assert data["updated_at"]


def test_incremental_across_rounds(tmp_path: Path) -> None:
    for _ in range(3):
        LiveOpsStats(tmp_path / "s.json", "FUTURES").record([_close(net=5.0)])
    data = json.loads((tmp_path / "s.json").read_text(encoding="utf-8"))
    assert data["totals"]["count"] == 3 and data["events_total"] == 3


def test_corrupted_file_is_rebuilt(tmp_path: Path) -> None:
    path = tmp_path / "s.json"
    path.write_text("{not json", encoding="utf-8")
    stats = LiveOpsStats(path, "FUTURES")
    assert stats.record([_close()]) == 1
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["totals"]["count"] == 1


def test_bypass_never_raises_on_unwritable_path(tmp_path: Path) -> None:
    blocker = tmp_path / "blocker"
    blocker.write_text("x", encoding="utf-8")
    stats = LiveOpsStats(blocker / "nested" / "s.json", "FUTURES")
    assert stats.record([_close()]) == 0  # 旁路：只告警不抛异常，交易主流程不受影响


def test_unknown_event_types_ignored(tmp_path: Path) -> None:
    stats = LiveOpsStats(tmp_path / "s.json", "FUTURES")
    assert stats.record([{"event_type": "heartbeat", "strategy_id": "DS01"}]) == 0


def test_kill_switch_disables_writes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FENGJI_LIVE_OPS_STATS", "0")
    counted = record_round(tmp_path, "FUTURES", fills=[_fill()], closes=[(_close(), None)])
    assert counted == 0
    assert not stats_path_for("FUTURES", tmp_path).exists()


def test_same_scoring_as_offline_bucket_stats() -> None:
    """实时与离线的胜率/评分必须同口径（共用 context_score.score_bucket_row）。"""
    offline_like = score_bucket_row(count=40, wins=24, avg_r=0.8, market="FUTURES")
    # 0.45*0.586(平滑胜率) + 0.35*0.4(R) + 0.2*1.0(置信度) ≈ 0.60 → MEDIUM 档
    assert 0.45 < offline_like["signal_score"] < 0.65
    assert offline_like["signal_tier"] == "MEDIUM"
    assert offline_like["win_rate"] == pytest.approx(0.6)
    # 实时统计走同一函数：给定相同 count/wins/avg_r 结果一致
    stats = LiveOpsStats(Path("runtime") / "unused.json", "FUTURES", active=False)
    merged = {"closes": 40, "wins": 24, "r_sum": 32.0, "r_n": 40}
    from fengji_core.live_ops_stats import _derive

    derived = _derive({**merged, **{"fills": 0, "stops": 0, "skips": 0, "cancels": 0, "net_sum": 0.0, "slip_sum": 0.0, "slip_n": 0}}, "FUTURES")
    assert derived["signal_score"] == pytest.approx(offline_like["signal_score"])
    assert derived["signal_tier"] == offline_like["signal_tier"]
    assert stats.active is False
