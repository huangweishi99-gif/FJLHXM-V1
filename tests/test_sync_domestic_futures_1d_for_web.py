from __future__ import annotations

import importlib.util
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "sync_domestic_futures_1d_for_web.py"


def load_script_module():
    spec = importlib.util.spec_from_file_location("sync_domestic_futures_1d_for_web", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_normalize_tq_daily_dates_to_shanghai_trading_date(tmp_path):
    module = load_script_module()
    src = tmp_path / "AO.csv"
    dst = tmp_path / "out" / "氧化铝.csv"

    rows = []
    for i in range(205):
        trading_day = pd.Timestamp("2025-01-01") + pd.Timedelta(days=i)
        tq_utc = trading_day - pd.Timedelta(hours=8)
        rows.append(
            {
                "datetime": 1_700_000_000_000_000_000 + i,
                "symbol": "SHFE.ao2609",
                "duration": 86400,
                "id": i,
                "open": 100 + i,
                "high": 105 + i,
                "low": 95 + i,
                "close": 102 + i,
                "volume": 1000 + i,
                "open_oi": 2000 + i,
                "close_oi": 2100 + i,
                "date": tq_utc.strftime("%Y-%m-%d %H:%M:%S"),
            }
        )
    rows.append(
        {
            "datetime": 1_780_329_600_000_000_000,
            "symbol": "SHFE.ao2609",
            "duration": 86400,
            "id": 999,
            "open": 2890.0,
            "high": 2891.0,
            "low": 2824.0,
            "close": 2851.0,
            "volume": 372220,
            "open_oi": 311559,
            "close_oi": 308963,
            "date": "2026-06-01 16:00:00",
        }
    )

    pd.DataFrame(rows).to_csv(src, index=False)
    count, _start, end = module.normalize_daily_csv(src, dst)

    out = pd.read_csv(dst)
    assert count == 206
    assert end == "2026-06-02"
    assert out.iloc[-1]["date"] == "2026-06-02"
    assert out.iloc[-1]["hold"] == 308963


def test_normalize_rejects_main_continuous_source(tmp_path):
    module = load_script_module()
    src = tmp_path / "LH.csv"
    dst = tmp_path / "out" / "生猪.csv"

    rows = []
    for i in range(25):
        trading_day = pd.Timestamp("2026-05-01") + pd.Timedelta(days=i)
        tq_utc = trading_day - pd.Timedelta(hours=8)
        rows.append(
            {
                "datetime": 1_780_000_000_000_000_000 + i,
                "symbol": "KQ.m@DCE.lh",
                "duration": 86400,
                "id": i,
                "open": 100 + i,
                "high": 105 + i,
                "low": 95 + i,
                "close": 102 + i,
                "volume": 1000 + i,
                "open_oi": 2000 + i,
                "close_oi": 2100 + i,
                "date": tq_utc.strftime("%Y-%m-%d %H:%M:%S"),
            }
        )

    pd.DataFrame(rows).to_csv(src, index=False)
    try:
        module.normalize_daily_csv(src, dst)
    except ValueError as exc:
        assert "main-continuous data" in str(exc)
    else:
        raise AssertionError("KQ.m@ main-continuous source should be rejected")
