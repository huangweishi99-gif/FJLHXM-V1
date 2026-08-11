from __future__ import annotations

from pathlib import Path

import pandas as pd

from fengji_core.stop_bar_monitor import filter_valid_price_rows, read_latest_bar, stop_crossed


def test_filter_valid_price_rows_keeps_crypto_pepe(tmp_path: Path) -> None:
    frame = pd.DataFrame(
        {
            "date": ["2026-06-29", "2026-06-30"],
            "open": [2.35e-06, 2.35e-06],
            "high": [2.42e-06, 2.37e-06],
            "low": [2.31e-06, 2.32e-06],
            "close": [2.36e-06, 2.35e-06],
            "volume": [1.0, 1.0],
        }
    )
    out = filter_valid_price_rows(frame)
    assert len(out) == 2


def test_read_latest_bar_completed_ds01(tmp_path: Path) -> None:
    data = tmp_path / "data"
    (data / "1d").mkdir(parents=True)
    (data / "1d" / "SUIUSDT.csv").write_text(
        "datetime,open,high,low,close,volume\n"
        "2026-06-29,0.68,0.685,0.67,0.682,1\n"
        "2026-06-30,0.70,0.7034,0.69,0.6957,1\n",
        encoding="utf-8",
    )
    bar = read_latest_bar(data, "SUIUSDT", ["1d"], completed_only=True)
    assert bar is not None
    assert bar["date"].startswith("2026-06-29")


def test_stop_crossed_short_string_side() -> None:
    pos = {"side": "short", "current_stop": 1.05}
    bar = {"high": 1.06, "low": 1.0, "open": 1.02, "close": 1.03}
    assert stop_crossed(pos, bar) is True
