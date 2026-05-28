from __future__ import annotations

import pandas as pd

from fengji_total_radar import add_ds07


def d1_frame() -> pd.DataFrame:
    df = pd.DataFrame(
        [
            {"date": "2026-05-25", "open": 9.0, "high": 10.0, "low": 8.5, "close": 9.8, "camp": 1},
            {"date": "2026-05-26", "open": 9.8, "high": 10.2, "low": 9.4, "close": 10.0, "camp": 1},
        ]
    )
    df["date"] = pd.to_datetime(df["date"])
    return df


def h1_alignment(red_ext_price: float | None, red_ext_idx: int | None) -> pd.DataFrame:
    df = pd.DataFrame(
        [
            {
                "date": "2026-05-26 09:00:00",
                "open": 9.5,
                "high": 9.8,
                "low": 9.3,
                "close": 9.6,
                "camp": -1,
                "hardened_count": 4,
                "blue_ext_price": 10.0,
                "blue_ext_idx": 5,
            },
            {
                "date": "2026-05-26 10:00:00",
                "open": 9.6,
                "high": 9.9,
                "low": 9.4,
                "close": 9.7,
                "camp": -1,
                "hardened_count": 4,
                "red_ext_price": red_ext_price,
                "red_ext_idx": red_ext_idx,
            },
        ]
    )
    df["date"] = pd.to_datetime(df["date"])
    return df


def test_ds07_skips_alignment_without_known_defense_extreme() -> None:
    rows = []

    add_ds07(rows, "BNBUSDT", d1_frame(), h1_alignment(red_ext_price=None, red_ext_idx=None), current=9.7)

    assert rows == []


def test_ds07_alignment_pending_requires_attack_and_defense_key() -> None:
    rows = []

    add_ds07(rows, "BNBUSDT", d1_frame(), h1_alignment(red_ext_price=8.8, red_ext_idx=6), current=9.7)

    assert len(rows) == 1
    assert rows[0].strategy_id == "DS07"
    assert rows[0].status == "PENDING"
    assert rows[0].stop_price == 8.8
    assert rows[0].setup_key == "BNBUSDT|DS07|LONG|ALIGN|attack=5|defense=6|trigger=10"
