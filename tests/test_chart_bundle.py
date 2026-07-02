from __future__ import annotations

import os
from pathlib import Path

import pytest

from chart_bundle import ChartBundleRequest, _hardened_segments, build_chart_bundle


def _require_chart_futures_golden() -> None:
    if not os.environ.get("FENGJI_CHART_FUTURES_GOLDEN"):
        pytest.skip("futures chart golden tests require FENGJI_CHART_FUTURES_GOLDEN=1 and synced os_state")


def _require_os_state(root: Path, symbol: str, timeframe: str = "1d") -> Path:
    state_dir = root / "runtime" / "fengji_os_state"
    path = state_dir / f"{symbol}_{timeframe}.json"
    if not path.is_file():
        pytest.skip(f"os state fixture missing: {path.name}")
    return state_dir


def test_chart_bundle_ds03_sol() -> None:
    root = Path(__file__).resolve().parents[1]
    csv = root / "data" / "overseas_1d" / "SOLUSDT.csv"
    if not csv.exists():
        csv = root / "data" / "overseas_1d" / "SOLUSDT_server.csv"
    if not csv.exists():
        return
    bundle = build_chart_bundle(ChartBundleRequest(csv_path=csv, strategy_id="DS03", years=3))
    assert bundle["strategy_id"] == "DS03"
    assert len(bundle["bars"]) > 100
    assert bundle["metrics"]["trades"] > 0
    assert bundle["metrics"]["bad_audits"] == 0
    assert any(m["kind"] == "entry" for m in bundle["markers"])
    assert len(bundle["trades"]) == bundle["metrics"]["trades"]
    assert bundle["trades"][0]["trade_no"] >= 1
    assert bundle["trades"][0]["trade_source"] == "live_backtest"
    assert "equity_curve" in bundle
    assert isinstance(bundle["equity_curve"], list)


def test_chart_bundle_total_sol() -> None:
    root = Path(__file__).resolve().parents[1]
    csv = root / "data" / "overseas_1d" / "SOLUSDT.csv"
    if not csv.exists():
        csv = root / "data" / "overseas_1d" / "SOLUSDT_server.csv"
    if not csv.exists():
        return
    bundle = build_chart_bundle(ChartBundleRequest(csv_path=csv, strategy_id="TOTAL", years=3))
    assert bundle["strategy_id"] == "TOTAL"
    assert len(bundle["bars"]) > 100
    assert bundle["metrics"]["trades"] >= 0
    assert "bad_audits" in bundle["metrics"]


def test_chart_bundle_prefers_stateful_os_overlay(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[1]
    csv = root / "data" / "overseas_1d" / "SOLUSDT.csv"
    if not csv.exists():
        csv = root / "data" / "overseas_1d" / "SOLUSDT_server.csv"
    if not csv.exists():
        pytest.skip("SOLUSDT fixture not available")

    state_dir = tmp_path / "fengji_os_state"
    bundle = build_chart_bundle(
        ChartBundleRequest(
            csv_path=csv,
            strategy_id="DS03",
            years=2,
            os_state_dir=state_dir,
            os_symbol="SOLUSDT",
            os_timeframe="1d",
            os_tail_rows=1095,
        )
    )

    state = bundle.get("os_state") or {}
    assert state["used_os_state"] is True
    assert state["state_symbol"] == "SOLUSDT"
    assert Path(state["state_file"]).exists()
    assert len(bundle["bars"]) > 100
    assert len(bundle["hardened_segments"]) > 0


def test_hardened_segments_trail_reaches_latest_bar(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[1]
    csv = root / "data" / "1d" / "IOUSDT.csv"
    if not csv.exists():
        pytest.skip("IOUSDT fixture not available")

    state_dir = tmp_path / "fengji_os_state"
    bundle = build_chart_bundle(
        ChartBundleRequest(
            csv_path=csv,
            strategy_id="DS03",
            years=2,
            os_state_dir=state_dir,
            os_symbol="IOUSDT",
            os_timeframe="1d",
            os_tail_rows=1095,
        )
    )
    bars = bundle["bars"]
    segs = bundle["hardened_segments"]
    assert bars
    assert segs
    last_bar_t = bars[-1]["t"]
    last_seg = segs[-1]
    assert last_seg["t1"] == last_bar_t
    dashed = [s for s in segs if s.get("style") == "dashed" or s.get("kind") == "provisional"]
    assert dashed, "expected provisional dashed segment before latest hardened point"
    assert dashed[-1]["t1"] == last_bar_t


def test_ni_solid_includes_identity_empty_may_low() -> None:
    """沪镍：5/26 谷点已物理硬化但尚无红/蓝身份，实线须连过该点，橡皮筋从该点出发。"""
    _require_chart_futures_golden()
    root = Path(__file__).resolve().parents[1]
    csv = root / "data" / "futures" / "1d" / "沪镍.csv"
    if not csv.exists():
        pytest.skip("沪镍 fixture not available")

    state_dir = _require_os_state(root, "NI")
    bundle = build_chart_bundle(
        ChartBundleRequest(
            csv_path=csv,
            strategy_id="DS03",
            years=2,
            futures_mode=True,
            os_state_dir=state_dir,
            os_symbol="NI",
            os_timeframe="1d",
            os_tail_rows=1095,
        )
    )
    segs = bundle["hardened_segments"]
    assert segs
    solid = [s for s in segs if s.get("style", "solid") == "solid" and s.get("kind") != "provisional"]
    assert any(s["t1"] == "2026-05-26" and s["p1"] == 140650.0 for s in solid), "实线应连到 5/26 谷点"
    trail = segs[-1]
    dashed = [s for s in segs if s.get("kind") == "provisional" or s.get("style") == "dashed"]
    assert dashed
    assert dashed[0]["t0"] == "2026-05-26" and dashed[0]["p0"] == 140650.0, "橡皮筋锚点必须是最后固化谷点"
    assert trail["t1"] == bundle["bars"][-1]["t"]


def test_ag_provisional_trail_zigzag_through_rebound() -> None:
    """沪银：5/28 谷后反弹，橡皮筋须经区间高点再落至最新 K，不能斜线抄近路。"""
    _require_chart_futures_golden()
    root = Path(__file__).resolve().parents[1]
    csv = root / "data" / "futures" / "1d" / "沪银.csv"
    if not csv.exists():
        pytest.skip("沪银 fixture not available")
    state_dir = _require_os_state(root, "AG")
    bundle = build_chart_bundle(
        ChartBundleRequest(
            csv_path=csv,
            strategy_id="DS03",
            years=2,
            futures_mode=True,
            os_state_dir=state_dir,
            os_symbol="AG",
            os_timeframe="1d",
        )
    )
    dashed = [s for s in bundle["hardened_segments"] if s.get("kind") == "provisional"]
    assert len(dashed) >= 2, "AG 反弹后橡皮筋应有多段 zigzag"
    assert dashed[0]["t0"] == "2026-05-28" and dashed[0]["p0"] == 17455.0
    assert dashed[0]["t1"] == "2026-05-29" and dashed[0]["p1"] == 18588.0
    assert dashed[-1]["t1"] == bundle["bars"][-1]["t"]


def test_sc_solid_bridges_failed_low_between_highs() -> None:
    """原油：5/8 FAILED 谷点不参与实线锚点，但 4/30 峰→5/20 峰须经区间谷点桥接，不能 HIGH 直连。"""
    _require_chart_futures_golden()
    root = Path(__file__).resolve().parents[1]
    csv = root / "data" / "futures" / "1d" / "原油.csv"
    if not csv.exists():
        pytest.skip("原油 fixture not available")

    state_dir = _require_os_state(root, "SC")
    bundle = build_chart_bundle(
        ChartBundleRequest(
            csv_path=csv,
            strategy_id="DS03",
            years=2,
            futures_mode=True,
            os_state_dir=state_dir,
            os_symbol="SC",
            os_timeframe="1d",
            os_tail_rows=1095,
        )
    )
    solid = [
        s
        for s in bundle["hardened_segments"]
        if s.get("style", "solid") == "solid" and s.get("kind") != "provisional"
    ]
    assert not any(
        s["type"] == "HIGH" and s["t0"] == "2026-04-30" and s["t1"] == "2026-05-20"
        for s in solid
    ), "4/30 峰不能直接连 5/20 峰"
    assert any(s["t0"] == "2026-04-30" and s["t1"] == "2026-05-08" and s["p1"] == 609.1 for s in solid)
    trail = bundle["hardened_segments"][-1]
    assert trail.get("kind") == "provisional"
    assert trail["t1"] == bundle["bars"][-1]["t"]
