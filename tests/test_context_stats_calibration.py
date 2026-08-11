from __future__ import annotations

import json

import pandas as pd

from fengji_core.context_stats import (
    aggregate_bucket_stats,
    classify_tier,
    infer_crypto_period_from_hint,
    load_market_calibrations,
    market_calibration,
    resolve_data_csv,
)


def test_market_calibration_active_and_inactive_fallback(tmp_path, monkeypatch) -> None:
    cfg = {
        "markets": {
            "A_STOCK": {
                "activate": True,
                "tier_medium": 0.34,
                "tier_strong": 0.51,
                "min_bucket_samples": 30,
                "w_wr": 0.45,
                "w_r": 0.35,
                "w_conf": 0.20,
            },
            "CRYPTO": {
                "activate": False,
                "tier_medium": 0.10,
                "tier_strong": 0.20,
                "min_bucket_samples": 30,
                "w_wr": 0.45,
                "w_r": 0.35,
                "w_conf": 0.20,
            },
        },
        "default": {
            "tier_medium": 0.45,
            "tier_strong": 0.65,
            "min_bucket_samples": 30,
            "w_wr": 0.45,
            "w_r": 0.35,
            "w_conf": 0.20,
        },
    }
    path = tmp_path / "context_market_calibration.json"
    path.write_text(json.dumps(cfg), encoding="utf-8")
    monkeypatch.setenv("FENGJI_CONTEXT_CALIBRATION", str(path))
    load_market_calibrations.cache_clear()
    try:
        assert market_calibration("A_STOCK")["tier_strong"] == 0.51
        assert classify_tier(0.52, 30, market="A_STOCK") == "STRONG"
        assert classify_tier(0.52, 30, market="CRYPTO") == "MEDIUM"
        assert classify_tier(0.30, 29, market="A_STOCK") == "INSUFFICIENT_DATA"
    finally:
        load_market_calibrations.cache_clear()


def test_aggregate_bucket_stats_uses_market_specific_thresholds(tmp_path, monkeypatch) -> None:
    cfg = {
        "markets": {
            "A_STOCK": {
                "activate": True,
                "tier_medium": 0.30,
                "tier_strong": 0.50,
                "min_bucket_samples": 30,
                "w_wr": 0.45,
                "w_r": 0.35,
                "w_conf": 0.20,
            }
        },
        "default": {
            "tier_medium": 0.45,
            "tier_strong": 0.65,
            "min_bucket_samples": 30,
            "w_wr": 0.45,
            "w_r": 0.35,
            "w_conf": 0.20,
        },
    }
    path = tmp_path / "context_market_calibration.json"
    path.write_text(json.dumps(cfg), encoding="utf-8")
    monkeypatch.setenv("FENGJI_CONTEXT_CALIBRATION", str(path))
    load_market_calibrations.cache_clear()
    try:
        rows = []
        for i in range(30):
            rows.append(
                {
                    "trade_id": f"t{i}",
                    "strategy_id": "DS01",
                    "market": "A_STOCK",
                    "symbol": "000001",
                    "net_pnl": 1.0 if i < 20 else -1.0,
                    "r_multiple": 1.0 if i < 20 else -1.0,
                    "camp": 1,
                    "camp_confirmed": 1,
                    "dist_active_high_atr": 1.0,
                    "bar_direction": "BULL",
                    "position_in_range_20": 0.5,
                    "market_regime_vol": "NORMAL",
                }
            )
        stats = aggregate_bucket_stats(pd.DataFrame(rows))
        assert stats.iloc[0]["signal_tier"] in {"MEDIUM", "STRONG"}
    finally:
        load_market_calibrations.cache_clear()


def test_crypto_period_aware_resolve_uses_exact_okx_window(tmp_path) -> None:
    okx_dir = tmp_path / "crypto_okx"
    okx_dir.mkdir()
    expected = okx_dir / "AVAX-USDT_15m_180d.csv"
    expected.write_text("date,open,high,low,close,volume\n", encoding="utf-8")

    assert infer_crypto_period_from_hint("results/fengji_total_pattern_default_180d_m15/AVAX-USDT") == "180d"
    assert infer_crypto_period_from_hint("results/fengji_total_ds01_ds08_okx16_5y/AVAX-USDT") == "1825d"
    assert infer_crypto_period_from_hint("results/unified_crypto_forward30_filtered_m15/XRP-USDT") == "180d"
    resolved = resolve_data_csv(
        tmp_path,
        "AVAXUSDT",
        "15m",
        "CRYPTO",
        source_hint="results/fengji_total_pattern_default_180d_m15/AVAX-USDT",
    )
    assert resolved == expected


def test_futures_resolve_does_not_append_usdt(tmp_path) -> None:
    futures_dir = tmp_path / "1d"
    futures_dir.mkdir()
    expected = futures_dir / "PVC.csv"
    expected.write_text("date,open,high,low,close,volume\n", encoding="utf-8")

    resolved = resolve_data_csv(tmp_path, "PVC", "1d", "FUTURES")
    assert resolved == expected
