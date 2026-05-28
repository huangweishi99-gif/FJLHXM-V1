from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from fengji_core.data import load_ohlcv_for_engine
from fengji_core.os_engine import BLUE, NEUTRAL, RED, FengJiOSIdentityEngine, IdentityNode, RawNode, build_identity_line, role


ROOT = Path(__file__).resolve().parents[1]
SAMPLE_CSV = ROOT / "data" / "sample_ohlcv.csv"


@pytest.fixture
def sample_df() -> pd.DataFrame:
    if not SAMPLE_CSV.exists():
        pytest.skip(f"missing sample data: {SAMPLE_CSV}")
    return load_ohlcv_for_engine(SAMPLE_CSV, atr_window=14)


def test_os_engine_runs_on_sample(sample_df: pd.DataFrame) -> None:
    engine = FengJiOSIdentityEngine(gap=3).run(sample_df)
    frame = engine.to_frame(sample_df)
    assert len(engine.raw_nodes) > 0
    assert len(engine.hardened_nodes) > 0
    assert "camp" in frame.columns
    assert set(frame["camp"].dropna().unique()).issubset({RED, BLUE, NEUTRAL})


def test_hardened_nodes_alternate(sample_df: pd.DataFrame) -> None:
    engine = FengJiOSIdentityEngine(gap=3).run(sample_df)
    types = [node.raw_type for node in engine.hardened_nodes]
    for idx in range(1, len(types)):
        assert types[idx] != types[idx - 1]


def test_hardened_gap_at_least_three(sample_df: pd.DataFrame) -> None:
    engine = FengJiOSIdentityEngine(gap=3).run(sample_df)
    for idx in range(1, len(engine.hardened_nodes)):
        prev = engine.hardened_nodes[idx - 1]
        curr = engine.hardened_nodes[idx]
        assert curr.point_idx - prev.point_idx >= 3


def test_identity_line_roles_alternate(sample_df: pd.DataFrame) -> None:
    engine = FengJiOSIdentityEngine(gap=3).run(sample_df)
    line = build_identity_line(engine.identity_nodes)
    roles = [role(node.identity) for node in line if role(node.identity) != "FAILED"]
    for idx in range(1, len(roles)):
        assert roles[idx] != roles[idx - 1]


def test_gap_rejected_raw_node_does_not_update_identity() -> None:
    df = pd.DataFrame(
        {
            "date": pd.date_range("2026-01-01", periods=16, freq="D"),
            "open": [12.0] * 16,
            "high": [20.0] * 16,
            "low": [11.0] * 16,
            "close": [12.0] * 16,
        }
    )
    engine = FengJiOSIdentityEngine(gap=3)
    engine.camp = RED
    engine.hardened_nodes = [RawNode(point_idx=10, confirm_idx=13, price=20.0, raw_type="HIGH")]
    engine.red_peak = IdentityNode(10, 13, 20.0, "HIGH", "RED_PEAK", RED)
    engine.red_ext = IdentityNode(7, 10, 10.0, "LOW", "RED_EXT", RED)

    rejected_low = RawNode(point_idx=12, confirm_idx=15, price=15.0, raw_type="LOW")
    engine.detect_raw_33_node = lambda _df, _i: rejected_low  # type: ignore[method-assign]

    engine.process_bar(df, 15)

    assert engine.hardened_nodes == [RawNode(point_idx=10, confirm_idx=13, price=20.0, raw_type="HIGH")]
    assert engine.red_ext == IdentityNode(7, 10, 10.0, "LOW", "RED_EXT", RED)
    assert all(node.point_idx != 12 for node in engine.identity_nodes)


def test_incremental_state_matches_full_run(sample_df: pd.DataFrame) -> None:
    split = max(10, len(sample_df) // 2)
    prefix = sample_df.iloc[:split].reset_index(drop=True)

    full_engine = FengJiOSIdentityEngine(gap=3).run(sample_df)
    prefix_engine = FengJiOSIdentityEngine(gap=3).run(prefix)
    state = json.loads(json.dumps(prefix_engine.to_state(), default=str))
    incremental_engine = FengJiOSIdentityEngine(gap=3).run_from_state(sample_df, state)

    incremental_turns = incremental_engine.export_turns().copy()
    full_turns = full_engine.export_turns().copy()
    if "date" in incremental_turns:
        normalize_date = lambda series: pd.to_datetime(series, errors="coerce").dt.strftime("%Y-%m-%d %H:%M:%S")
        incremental_turns["date"] = normalize_date(incremental_turns["date"])
        full_turns["date"] = normalize_date(full_turns["date"])

    assert incremental_engine.raw_nodes == full_engine.raw_nodes
    assert incremental_engine.identity_nodes == full_engine.identity_nodes
    assert incremental_turns.fillna("__NA__").to_dict("records") == full_turns.fillna("__NA__").to_dict("records")
    assert incremental_engine.hardened_nodes == full_engine.hardened_nodes
    assert incremental_engine.camp == full_engine.camp
