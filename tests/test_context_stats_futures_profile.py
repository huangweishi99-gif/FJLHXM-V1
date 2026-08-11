from __future__ import annotations

import pandas as pd

from fengji_core.context_stats import (
    aggregate_bucket_stats,
    build_bucket_key,
    bucket_profile_for_market,
)


def _futures_row(**overrides) -> dict:
    base = {
        "strategy_id": "DS01",
        "market": "FUTURES",
        "trade_id": "t1",
        "net_pnl": 10.0,
        "r_multiple": 1.0,
        "camp": 1,
        "camp_confirmed": 1,
        "dist_active_high_atr": 0.3,
        "bar_direction": "BULL",
        "position_in_range_20": 0.8,
        "market_regime_vol": "HIGH",
    }
    base.update(overrides)
    return base


def test_futures_v2_bucket_profile_differs_from_v1() -> None:
    row = _futures_row()
    v1_key = build_bucket_key(row, "DS01", "A_STOCK")
    fut_key = build_bucket_key(row, "DS01", "FUTURES")
    assert "camp_confirmed=" in fut_key
    assert "|camp=" not in fut_key.replace("camp_confirmed", "")
    assert "position_in_range_20=" not in fut_key
    assert "market_regime_vol=" not in fut_key
    assert "dist_active_high_atr=NEAR_MID" in fut_key
    assert v1_key != fut_key


def test_crypto_still_uses_v1_profile() -> None:
    row = _futures_row(market="CRYPTO")
    key = build_bucket_key(row, "DS01", "CRYPTO")
    assert "position_in_range_20=" in key
    assert bucket_profile_for_market("CRYPTO").name == "v1"


def test_futures_aggregate_has_fewer_buckets_than_v1_counterfactual() -> None:
    rows = []
    camps = [1, -1]
    dirs = ["BULL", "BEAR"]
    atrs = [0.2, 1.0, 2.0]
    for i, camp in enumerate(camps):
        for d in dirs:
            for atr in atrs:
                rows.append(
                    _futures_row(
                        trade_id=f"t{i}-{d}-{atr}",
                        camp=camp,
                        camp_confirmed=camp,
                        bar_direction=d,
                        dist_active_high_atr=atr,
                        position_in_range_20=0.2 if i == 0 else 0.8,
                        market_regime_vol="HIGH" if i == 0 else "LOW",
                        net_pnl=1.0 if i == 0 else -1.0,
                    )
                )
    df = pd.DataFrame(rows)
    stats = aggregate_bucket_stats(df)
    assert len(stats) < len(rows)
    assert bucket_profile_for_market("FUTURES").name == "futures_v2"
