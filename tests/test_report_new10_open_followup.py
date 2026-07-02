from __future__ import annotations

import json
from pathlib import Path

from scripts.report_new10_open_followup import build_report, monitor_stop_bar


def test_build_report_uses_completed_bar_for_ds01(tmp_path: Path) -> None:
    paper = {
        "symbols": {
            "SUIUSDT": {
                "open_position": {
                    "strategy_id": "DS01",
                    "side": -1,
                    "direction": "short",
                    "entry_time": "2026-06-28 14:13:12",
                    "entry_price": 0.6783,
                    "current_stop": 0.6877,
                    "order_id": "sui",
                }
            }
        }
    }
    data = tmp_path / "data"
    (data / "1d").mkdir(parents=True)
    (data / "1d" / "SUIUSDT.csv").write_text(
        "datetime,open,high,low,close,volume\n"
        "2026-06-29,0.68,0.685,0.67,0.682,1\n"
        "2026-06-30,0.70,0.7034,0.69,0.6957,1\n",
        encoding="utf-8",
    )
    report = build_report(paper, data)
    bar = report["positions"][0]["stop_bar"]
    assert bar is not None
    assert bar["date"].startswith("2026-06-29")
    assert report["positions"][0]["stop_check"]["breached_on_bar"] is False


def test_pre_entry_bar_not_effective_breach(tmp_path: Path) -> None:
    paper = {
        "symbols": {
            "HYPEUSDT": {
                "open_position": {
                    "strategy_id": "DS05",
                    "side": 1,
                    "direction": "long",
                    "entry_time": "2026-06-30 11:35:53",
                    "entry_price": 65.815,
                    "current_stop": 60.61,
                    "order_id": "hype",
                }
            }
        }
    }
    data = tmp_path / "data"
    (data / "1d").mkdir(parents=True)
    (data / "1d" / "HYPEUSDT.csv").write_text(
        "datetime,open,high,low,close,volume\n"
        "2026-06-28,63.141,65.0,60.61,64.905,1\n"
        "2026-06-29,64.926,67.829,64.259,65.902,1\n",
        encoding="utf-8",
    )
    report = build_report(paper, data)
    pos = report["positions"][0]
    assert pos["after_entry"] is False
    assert pos["stop_check"]["breached_on_bar"] is True
    assert pos["stop_check"]["breached_effective"] is False


def test_missing_bar_adds_note(tmp_path: Path) -> None:
    paper = {
        "symbols": {
            "OPUSDT": {
                "open_position": {
                    "strategy_id": "DS09",
                    "side": -1,
                    "direction": "short",
                    "entry_time": "2026-06-30 12:17:38",
                    "entry_price": 0.0984,
                    "current_stop": 0.0991,
                    "order_id": "op",
                }
            }
        }
    }
    data = tmp_path / "data"
    data.mkdir()
    report = build_report(paper, data)
    pos = report["positions"][0]
    assert pos["stop_bar"] is None
    assert "15m" in pos.get("stop_eval_note", "")


def test_post_entry_bar_for_ds09(tmp_path: Path) -> None:
    paper = {
        "symbols": {
            "OPUSDT": {
                "open_position": {
                    "strategy_id": "DS09",
                    "side": -1,
                    "direction": "short",
                    "entry_time": "2026-06-30 12:00:00",
                    "entry_price": 0.0984,
                    "current_stop": 0.0991,
                    "order_id": "op",
                }
            }
        }
    }
    data = tmp_path / "data"
    (data / "15m").mkdir(parents=True)
    (data / "15m" / "OPUSDT.csv").write_text(
        "datetime,open,high,low,close,volume\n"
        "2026-06-30 11:45:00,0.098,0.0985,0.0979,0.0982,1\n"
        "2026-06-30 12:15:00,0.0984,0.0992,0.0983,0.0989,1\n",
        encoding="utf-8",
    )
    report = build_report(paper, data)
    pos = report["positions"][0]
    assert pos.get("post_entry_bar") is not None
    assert pos["post_entry_stop_check"]["breached_on_bar"] is True


def test_monitor_stop_bar_kind(tmp_path: Path) -> None:
    data = tmp_path / "data"
    (data / "1d").mkdir(parents=True)
    (data / "1d" / "XRPUSDT.csv").write_text(
        "datetime,open,high,low,close,volume\n2026-06-30,1,1.05,0.99,1.02,1\n",
        encoding="utf-8",
    )
    pos = {"strategy_id": "DS01", "side": -1, "current_stop": 1.1}
    bar = monitor_stop_bar(data, "XRPUSDT", pos)
    assert bar is not None
    assert bar["bar_kind"] == "completed"
