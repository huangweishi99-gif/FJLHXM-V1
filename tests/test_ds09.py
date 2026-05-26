from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from fengji_core.constants import DEFAULT_STRATEGIES_CSV, FENGJI_TOTAL_PATTERN_STRATEGIES
from fengji_core.ds09 import audit_ds09_structure


ROOT = Path(__file__).resolve().parents[1]


def test_total_pattern_includes_ds09() -> None:
    assert "DS09" in FENGJI_TOTAL_PATTERN_STRATEGIES
    assert FENGJI_TOTAL_PATTERN_STRATEGIES[-1] == "DS09"
    assert "DS09" in DEFAULT_STRATEGIES_CSV.split(",")


def test_ds09_audit_empty_on_empty_trades() -> None:
    assert audit_ds09_structure(pd.DataFrame()).empty


def test_unified_smoke_outputs_if_present() -> None:
    smoke_dir = ROOT / "results" / "ds09_inclusion_smoke" / "ETH"
    bad_path = smoke_dir / "strategy_bad_trades.csv"
    if not bad_path.exists():
        pytest.skip("run unified smoke first to populate results/ds09_inclusion_smoke/ETH")
    bad = pd.read_csv(bad_path)
    assert len(bad) == 0
