"""Unit tests for FUTURES 5m data pump config (no live TqApi)."""
from __future__ import annotations

import importlib
import sys

import pandas as pd
import pytest


def load_data_manager(monkeypatch: pytest.MonkeyPatch, tmp_path):
    monkeypatch.setenv("FUTURES_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("FUTURES_LOG_DIR", str(tmp_path / "logs"))
    sys.modules.pop("data_manager_futures", None)
    return importlib.import_module("data_manager_futures")


def test_5m_timeframe_registered(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    dm = load_data_manager(monkeypatch, tmp_path)
    assert dm.TIMEFRAMES["5m"] == 300
    assert dm.DATA_LENGTHS["5m"] >= 2000
    assert (tmp_path / "data" / "5m").is_dir()


def test_length_candidates_include_5m_fallbacks(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    dm = load_data_manager(monkeypatch, tmp_path)
    monkeypatch.setenv("FUTURES_5M_LENGTH", "6000")
    dm.DATA_LENGTHS["5m"] = 6000
    candidates = dm._length_candidates("5m", 6000)
    assert 6000 in candidates
    assert 3000 in candidates
    assert all(c >= 2000 for c in candidates)


def test_fetch_symbol_writes_5m_csv(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    dm = load_data_manager(monkeypatch, tmp_path)
    seen_seconds: list[int] = []
    data_contract = "SHFE.rb2609"

    class DummyApi:
        def get_quote(self, tq_code: str):
            return type("Quote", (), {"underlying_symbol": data_contract, "instrument_id": tq_code})()

        def wait_update(self, deadline=None):
            return False

        def get_kline_serial(self, tq_code, seconds, data_length):
            seen_seconds.append(seconds)
            assert tq_code == data_contract
            base = pd.Timestamp("2026-06-01 09:00:00")
            if seconds == 86400:
                delta = pd.Timedelta(days=1)
            elif seconds == 3600:
                delta = pd.Timedelta(hours=1)
            elif seconds == 900:
                delta = pd.Timedelta(minutes=15)
            else:
                delta = pd.Timedelta(minutes=5)
            rows = 3200
            return pd.DataFrame(
                {
                    "datetime": [(base + delta * i).value for i in range(rows)],
                    "symbol": [tq_code] * rows,
                    "open": [100.0 + (i % 3) for i in range(rows)],
                    "high": [101.0 + (i % 3) for i in range(rows)],
                    "low": [99.0 + (i % 3) for i in range(rows)],
                    "close": [100.5 + (i % 3) for i in range(rows)],
                }
            )

    assert dm.fetch_symbol(DummyApi(), "RB", "KQ.m@SHFE.rb") is True
    assert 300 in seen_seconds
    assert (tmp_path / "data" / "5m" / "RB.csv").is_file()
    frame = pd.read_csv(tmp_path / "data" / "5m" / "RB.csv")
    assert len(frame) >= 3000
