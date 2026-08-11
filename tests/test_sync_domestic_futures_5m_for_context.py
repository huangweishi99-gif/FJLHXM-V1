from __future__ import annotations

import importlib.util
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "sync_domestic_futures_5m_for_context.py"


def load_module():
    spec = importlib.util.spec_from_file_location("sync_domestic_futures_5m_for_context", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_normalize_5m_csv(tmp_path):
    module = load_module()
    src = tmp_path / "M_5m.csv"
    dst = tmp_path / "out" / "豆粕.csv"
    rows = []
    start = pd.Timestamp("2025-01-02 09:00:00")
    for i in range(200):
        ts = start + pd.Timedelta(minutes=5 * i)
        price = 3000 + (i % 17)
        rows.append(
            {
                "datetime": ts.value,
                "symbol": "DCE.m2609",
                "date": ts.strftime("%Y-%m-%d %H:%M:%S"),
                "open": price,
                "high": price + 5,
                "low": price - 5,
                "close": price + 1,
                "volume": 100 + i,
                "close_oi": 1000 + i,
            }
        )
    pd.DataFrame(rows).to_csv(src, index=False)
    count, start_s, end_s = module.normalize_intraday_csv(src, dst, min_rows=120)
    out = pd.read_csv(dst)
    assert count == 200
    assert start_s.startswith("2025-01-02")
    assert end_s.startswith("2025-01-")
    assert out.iloc[-1]["close"] == rows[-1]["close"]


def test_rejects_main_continuous_5m(tmp_path):
    module = load_module()
    src = tmp_path / "bad.csv"
    dst = tmp_path / "out" / "豆粕.csv"
    pd.DataFrame(
        [
            {
                "symbol": "KQ.m@DCE.m",
                "date": "2025-01-02 09:00:00",
                "open": 1,
                "high": 2,
                "low": 1,
                "close": 2,
                "volume": 1,
            }
        ]
        * 150
    ).to_csv(src, index=False)
    try:
        module.normalize_intraday_csv(src, dst)
    except ValueError as exc:
        assert "main-continuous" in str(exc)
    else:
        raise AssertionError("expected main-continuous rejection")
