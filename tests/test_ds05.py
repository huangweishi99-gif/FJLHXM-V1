from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from fengji_core.data import load_ohlcv_for_engine
from fengji_core.ds05 import audit_ds05_camp_direction, make_ds05_signal
from fengji_core.os_engine import FengJiOSIdentityEngine


ROOT = Path(__file__).resolve().parents[1]
SAMPLE_CSV = ROOT / "data" / "sample_ohlcv.csv"


@pytest.fixture
def os_df() -> pd.DataFrame:
    if not SAMPLE_CSV.exists():
        pytest.skip(f"missing sample data: {SAMPLE_CSV}")
    raw = load_ohlcv_for_engine(SAMPLE_CSV, atr_window=14)
    return FengJiOSIdentityEngine(gap=3).run(raw).to_frame(raw)


def test_ds05_audit_empty_on_backtest_trades(os_df: pd.DataFrame) -> None:
    """Run DS05 signal scan; any emitted trades must pass camp-direction audit."""
    rows: list[dict] = []
    for i in range(len(os_df)):
        signal = make_ds05_signal(os_df, i)
        if signal is None:
            continue
        rows.append(
            {
                "direction": "long" if signal.side == 1 else "short",
                "camp_k2": signal.camp_k2,
                "camp_k3": signal.camp_k3,
            }
        )
    trades = pd.DataFrame(rows)
    bad = audit_ds05_camp_direction(trades)
    assert bad.empty


def test_ds05_long_requires_red_camp(os_df: pd.DataFrame) -> None:
    for i in range(len(os_df)):
        signal = make_ds05_signal(os_df, i)
        if signal is None or signal.side != 1:
            continue
        assert signal.camp_k2 == 1 and signal.camp_k3 == 1


def test_ds05_short_requires_blue_camp(os_df: pd.DataFrame) -> None:
    for i in range(len(os_df)):
        signal = make_ds05_signal(os_df, i)
        if signal is None or signal.side != -1:
            continue
        assert signal.camp_k2 == -1 and signal.camp_k3 == -1
