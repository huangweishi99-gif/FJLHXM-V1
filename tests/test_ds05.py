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


def test_ds05_long_k2_can_form_new_extreme_far_from_old_red_ext() -> None:
    df = pd.DataFrame(
        [
            {"date": "2026-05-19", "open": 9000, "high": 9100, "low": 8950, "close": 9050, "volume": 1, "atr": 80, "camp": 1, "active_low": 8295, "active_high": 9440},
            {"date": "2026-05-20", "open": 9050, "high": 9120, "low": 8940, "close": 9060, "volume": 1, "atr": 80, "camp": 1, "active_low": 8295, "active_high": 9440},
            {"date": "2026-05-21", "open": 9060, "high": 9095, "low": 8910, "close": 8930, "volume": 1, "atr": 80, "camp": 1, "active_low": 8295, "active_high": 9440},
            {"date": "2026-05-22", "open": 8930, "high": 8955, "low": 8880, "close": 8920, "volume": 1, "atr": 80, "camp": 1, "active_low": 8295, "active_high": 9440},
            {"date": "2026-05-25", "open": 8900, "high": 9080, "low": 8890, "close": 9060, "volume": 1, "atr": 80, "camp": 1, "active_low": 8295, "active_high": 9440},
        ]
    )
    df["date"] = pd.to_datetime(df["date"])

    signal = make_ds05_signal(df, 4)

    assert signal is not None
    assert signal.side == 1
    assert signal.entry_price == 8955
    assert signal.initial_stop == 8880
    assert signal.k2_possible_extreme == 8880


def test_ds05_short_k2_can_form_new_extreme_far_from_old_blue_ext() -> None:
    df = pd.DataFrame(
        [
            {"date": "2026-05-19", "open": 100, "high": 106, "low": 98, "close": 101, "volume": 1, "atr": 2, "camp": -1, "active_low": 85, "active_high": 130},
            {"date": "2026-05-20", "open": 101, "high": 107, "low": 99, "close": 102, "volume": 1, "atr": 2, "camp": -1, "active_low": 85, "active_high": 130},
            {"date": "2026-05-21", "open": 102, "high": 108, "low": 100, "close": 101, "volume": 1, "atr": 2, "camp": -1, "active_low": 85, "active_high": 130},
            {"date": "2026-05-22", "open": 101, "high": 111, "low": 100, "close": 103, "volume": 1, "atr": 2, "camp": -1, "active_low": 85, "active_high": 130},
            {"date": "2026-05-25", "open": 104, "high": 110, "low": 99, "close": 100, "volume": 1, "atr": 2, "camp": -1, "active_low": 85, "active_high": 130},
        ]
    )
    df["date"] = pd.to_datetime(df["date"])

    signal = make_ds05_signal(df, 4)

    assert signal is not None
    assert signal.side == -1
    assert signal.entry_price == 100
    assert signal.initial_stop == 111
    assert signal.k2_possible_extreme == 111
