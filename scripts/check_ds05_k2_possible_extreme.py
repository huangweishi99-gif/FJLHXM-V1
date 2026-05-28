from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from fengji_total_radar import add_ds05  # noqa: E402
from quant.ds05 import make_ds05_signal  # noqa: E402


def main() -> None:
    long_df = pd.DataFrame(
        [
            {"date": "2026-05-19", "open": 9000, "high": 9100, "low": 8950, "close": 9050, "volume": 1, "atr": 80, "camp": 1, "active_low": 8295, "active_high": 9440},
            {"date": "2026-05-20", "open": 9050, "high": 9120, "low": 8940, "close": 9060, "volume": 1, "atr": 80, "camp": 1, "active_low": 8295, "active_high": 9440},
            {"date": "2026-05-21", "open": 9060, "high": 9095, "low": 8910, "close": 8930, "volume": 1, "atr": 80, "camp": 1, "active_low": 8295, "active_high": 9440},
            {"date": "2026-05-22", "open": 8930, "high": 8955, "low": 8880, "close": 8920, "volume": 1, "atr": 80, "camp": 1, "active_low": 8295, "active_high": 9440},
            {"date": "2026-05-25", "open": 8900, "high": 9080, "low": 8890, "close": 9060, "volume": 1, "atr": 80, "camp": 1, "active_low": 8295, "active_high": 9440},
        ]
    )
    long_df["date"] = pd.to_datetime(long_df["date"])
    long_signal = make_ds05_signal(long_df, 4)
    assert long_signal is not None
    assert long_signal.side == 1
    assert long_signal.k2_possible_extreme == 8880
    assert long_signal.entry_price == 8955
    assert long_signal.initial_stop == 8880

    short_df = pd.DataFrame(
        [
            {"date": "2026-05-19", "open": 100, "high": 106, "low": 98, "close": 101, "volume": 1, "atr": 2, "camp": -1, "active_low": 85, "active_high": 130},
            {"date": "2026-05-20", "open": 101, "high": 107, "low": 99, "close": 102, "volume": 1, "atr": 2, "camp": -1, "active_low": 85, "active_high": 130},
            {"date": "2026-05-21", "open": 102, "high": 108, "low": 100, "close": 101, "volume": 1, "atr": 2, "camp": -1, "active_low": 85, "active_high": 130},
            {"date": "2026-05-22", "open": 101, "high": 111, "low": 100, "close": 103, "volume": 1, "atr": 2, "camp": -1, "active_low": 85, "active_high": 130},
            {"date": "2026-05-25", "open": 104, "high": 110, "low": 99, "close": 100, "volume": 1, "atr": 2, "camp": -1, "active_low": 85, "active_high": 130},
        ]
    )
    short_df["date"] = pd.to_datetime(short_df["date"])
    short_signal = make_ds05_signal(short_df, 4)
    assert short_signal is not None
    assert short_signal.side == -1
    assert short_signal.k2_possible_extreme == 111
    assert short_signal.entry_price == 100
    assert short_signal.initial_stop == 111

    rows = []
    add_ds05(rows, "TEST", long_df, current=9060, extreme_atr_tol=0.8)
    assert len(rows) == 1
    assert "k2_possible_extreme" in rows[0].reason

    print("OK_DS05_K2_POSSIBLE_EXTREME")
    print("LONG", long_signal)
    print("SHORT", short_signal)
    print("RADAR_REASON", rows[0].reason)


if __name__ == "__main__":
    main()
