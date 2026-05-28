from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from fengji_core.constants import DEFAULT_STRATEGIES_CSV, FENGJI_TOTAL_PATTERN_STRATEGIES
from fengji_core.ds09 import BLUE, RED, audit_ds09_structure, build_prev_day_boundary_map


ROOT = Path(__file__).resolve().parents[1]


def test_total_pattern_includes_ds09() -> None:
    assert "DS09" in FENGJI_TOTAL_PATTERN_STRATEGIES
    assert FENGJI_TOTAL_PATTERN_STRATEGIES[-1] == "DS09"
    assert "DS09" in DEFAULT_STRATEGIES_CSV.split(",")


def test_ds09_audit_empty_on_empty_trades() -> None:
    assert audit_ds09_structure(pd.DataFrame()).empty


def test_ds09_boundary_requires_d1_os_camp() -> None:
    d1 = pd.DataFrame(
        {
            "date": pd.to_datetime(["2026-01-01", "2026-01-02"]),
            "open": [10.0, 11.0],
            "high": [12.0, 12.5],
            "low": [9.5, 10.0],
            "close": [11.0, 10.5],
        }
    )
    with pytest.raises(ValueError, match="D1 FengJi OS camp"):
        build_prev_day_boundary_map(d1)


def test_ds09_boundary_uses_prev_completed_d1_camp() -> None:
    d1 = pd.DataFrame(
        {
            "date": pd.to_datetime(["2026-01-01", "2026-01-02", "2026-01-03", "2026-01-04"]),
            "open": [10.0, 12.0, 9.0, 8.0],
            "high": [11.0, 12.8, 9.5, 8.5],
            "low": [9.0, 8.8, 7.7, 7.5],
            "close": [10.5, 9.5, 9.4, 8.2],
            "camp": [RED, RED, BLUE, RED],
        }
    )
    boundary_map = build_prev_day_boundary_map(d1)

    jan3 = boundary_map[pd.Timestamp("2026-01-03")]
    assert jan3["mode"] == "LONG"
    assert jan3["d1_camp"] == RED
    assert jan3["boundary"] == pytest.approx(12.8)

    jan4 = boundary_map[pd.Timestamp("2026-01-04")]
    assert jan4["mode"] == "SHORT"
    assert jan4["d1_camp"] == BLUE
    assert jan4["boundary"] == pytest.approx(7.7)


def test_unified_smoke_outputs_if_present() -> None:
    smoke_dir = ROOT / "results" / "ds09_inclusion_smoke" / "ETH"
    bad_path = smoke_dir / "strategy_bad_trades.csv"
    if not bad_path.exists():
        pytest.skip("run unified smoke first to populate results/ds09_inclusion_smoke/ETH")
    bad = pd.read_csv(bad_path)
    assert len(bad) == 0
