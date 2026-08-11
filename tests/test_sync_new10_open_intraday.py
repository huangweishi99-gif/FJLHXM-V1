"""Tests for sync_new10_open_intraday.py symbol detection."""
from __future__ import annotations

from scripts.sync_new10_open_intraday import open_intraday_symbols


def test_open_intraday_symbols_ds09_only() -> None:
    paper = {
        "symbols": {
            "HYPEUSDT": {"open_position": {"strategy_id": "DS05"}},
            "OPUSDT": {"open_position": {"strategy_id": "DS09"}},
            "XRPUSDT": {"open_position": {"strategy_id": "DS01"}},
        }
    }
    assert open_intraday_symbols(paper) == ["OPUSDT"]


def test_open_intraday_symbols_empty() -> None:
    assert open_intraday_symbols({"symbols": {}}) == []
