from __future__ import annotations

import pandas as pd

from fengji_core.context_snapshot import (
    build_snapshots,
    compute_l2_features,
    compute_r_multiple,
    snapshot_from_trade,
)
from fengji_core.context_stats import aggregate_bucket_stats, build_bucket_key, score_snapshot


def _sample_os_df() -> pd.DataFrame:
    rows = []
    for i in range(30):
        close = 100.0 + i * 0.5
        rows.append(
            {
                "date": pd.Timestamp("2026-01-01") + pd.Timedelta(days=i),
                "open": close - 0.2,
                "high": close + 1.0,
                "low": close - 1.0,
                "close": close,
                "volume": 1000 + i * 10,
                "camp": 1,
                "camp_confirmed": True,
                "pending_turn": None,
                "active_high": 120.0,
                "active_low": 90.0,
                "red_peak_idx": 5,
                "red_peak_price": 110.0,
                "red_ext_idx": 10,
                "red_ext_price": 95.0,
                "blue_peak_idx": None,
                "blue_ext_idx": None,
                "atr": 2.0,
                "hardened_count": 3,
            }
        )
    return pd.DataFrame(rows)


def test_l2_features_basic() -> None:
    df = _sample_os_df()
    feat = compute_l2_features(df, 15)
    assert feat["bar_direction"] == "BULL"
    assert 0.0 <= feat["body_ratio"] <= 1.0
    assert feat["gap_type"] in {"NONE", "UP", "DOWN"}


def test_snapshot_and_r_multiple() -> None:
    df = _sample_os_df()
    trade = {
        "strategy_id": "DS03",
        "entry_idx": 15,
        "exit_idx": 20,
        "entry_price": 107.5,
        "avg_entry_price": 107.5,
        "exit_price": 110.0,
        "initial_stop": 105.0,
        "entry_time": "2026-01-16",
        "exit_time": "2026-01-21",
        "net": 5.0,
        "side": 1,
        "peak_key": "P1",
        "setup_key": "SOLUSDT|DS03|P1|1",
    }
    snap = snapshot_from_trade(trade, df, market="CRYPTO", symbol="SOLUSDT", timeframe="1d")
    assert snap is not None
    assert snap["strategy_id"] == "DS03"
    assert snap["exit_price"] == 110.0
    assert snap["peak_key"] == "P1"
    assert snap["camp"] == 1
    assert compute_r_multiple(trade) == 2.0


def test_bucket_stats_and_scoring() -> None:
    df = _sample_os_df()
    trades = []
    for i in range(40):
        trades.append(
            {
                "strategy_id": "DS03",
                "entry_idx": 10 + (i % 5),
                "exit_idx": 15 + (i % 5),
                "entry_price": 105.0,
                "initial_stop": 103.0,
                "entry_time": f"2026-01-{10 + i:02d}",
                "exit_time": f"2026-01-{12 + i:02d}",
                "net": 2.0 if i % 2 == 0 else -1.0,
                "side": 1,
                "peak_key": "P1",
                "setup_key": f"SOLUSDT|DS03|P1|1|{i}",
            }
        )
    snapshots = build_snapshots(pd.DataFrame(trades), df, market="CRYPTO", symbol="SOLUSDT", timeframe="1d")
    stats = aggregate_bucket_stats(snapshots)
    assert not stats.empty
    assert (stats["count"] >= 1).all()
    key = build_bucket_key(snapshots.iloc[0], "DS03")
    scored = score_snapshot(snapshots.iloc[0], stats)
    assert scored["bucket_key"] == key
    assert scored["signal_tier"] in {"STRONG", "MEDIUM", "WEAK", "INSUFFICIENT_DATA"}
