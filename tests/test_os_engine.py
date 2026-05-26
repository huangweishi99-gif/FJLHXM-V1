from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from fengji_core.data import load_ohlcv_for_engine
from fengji_core.os_engine import BLUE, NEUTRAL, RED, FengJiOSIdentityEngine, build_identity_line, role


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
