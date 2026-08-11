"""Tests for WEB-CUSTOM-002 market ingest helpers."""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
SERVICES = str(ROOT / "services")
if SERVICES not in sys.path:
    sys.path.insert(0, SERVICES)

from market_ingest import ingest_custom_market_d1, ingest_futures_d1  # noqa: E402


def test_ingest_custom_market_d1_dispatches_a_stock() -> None:
    meta = {"market": "A_STOCK", "symbol": "000021", "path": "x.csv"}
    with patch("market_ingest.ingest_a_stock_d1", return_value=meta) as ingest:
        assert ingest_custom_market_d1("A_STOCK", "21", years=3) == meta
    ingest.assert_called_once_with("21", years=3)


def test_ingest_custom_market_d1_rejects_unknown_market() -> None:
    with pytest.raises(ValueError, match="unsupported custom ingest market"):
        ingest_custom_market_d1("FOREX", "EURUSD")


def test_ingest_futures_d1_rejects_unmapped_symbol(monkeypatch) -> None:
    fake_dm = MagicMock()
    fake_dm.TQ_SYMBOL_MAP = {"PVC": "KQ.m@DCE.V"}
    monkeypatch.setitem(sys.modules, "data_manager_futures", fake_dm)
    with pytest.raises(ValueError, match="not in domestic TQ map"):
        ingest_futures_d1("NOTAFUT")


def test_ingest_futures_d1_copies_csv_to_web_path(tmp_path: Path, monkeypatch) -> None:
    short = "PVC"
    source_dir = tmp_path / "futures_src" / "1d"
    source_dir.mkdir(parents=True)
    source_csv = source_dir / "PVC.csv"
    frame = pd.DataFrame(
        {
            "datetime": [f"2026-06-{i:02d}" for i in range(1, 40)],
            "open": [1.0] * 39,
            "high": [1.1] * 39,
            "low": [0.9] * 39,
            "close": [1.0] * 39,
            "volume": [100] * 39,
        }
    )
    frame.to_csv(source_csv, index=False)

    fake_dm = MagicMock()
    fake_dm.TQ_SYMBOL_MAP = {"PVC": "KQ.m@DCE.V"}
    fake_dm.DATA_DIR = tmp_path / "futures_src"
    fake_dm.MAIN_CONTRACT_MANIFEST = tmp_path / "manifest.json"
    fake_dm.connect_api.return_value = MagicMock()
    fake_dm.fetch_symbol.return_value = True
    monkeypatch.setitem(sys.modules, "data_manager_futures", fake_dm)

    web_dir = tmp_path / "web" / "futures" / "1d"
    monkeypatch.setattr("market_ingest.DATA_FUTURES_1D", web_dir)

    meta = ingest_futures_d1("PVC")
    assert meta["symbol"] == "PVC"
    assert meta["rows"] >= 30
    assert (web_dir / "PVC.csv").exists()
    fake_dm.fetch_symbol.assert_called_once()
