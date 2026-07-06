from __future__ import annotations

import pandas as pd

from fengji_total_radar import add_ds05


def base_rows() -> list[dict]:
    return [
        {"date": "2026-05-22", "open": 10.0, "high": 11.0, "low": 9.8, "close": 10.5, "volume": 1, "atr": 1.0, "camp": 1, "active_low": 9.7, "active_high": 12.0},
        {"date": "2026-05-23", "open": 10.5, "high": 11.2, "low": 9.9, "close": 10.7, "volume": 1, "atr": 1.0, "camp": 1, "active_low": 9.7, "active_high": 12.0},
        {"date": "2026-05-24", "open": 10.7, "high": 11.4, "low": 9.9, "close": 11.0, "volume": 1, "atr": 1.0, "camp": 1, "active_low": 9.7, "active_high": 12.0},
        {"date": "2026-05-25", "open": 10.9, "high": 11.1, "low": 9.6, "close": 10.2, "volume": 1, "atr": 1.0, "camp": 1, "active_low": 9.7, "active_high": 12.0},
        {"date": "2026-05-26", "open": 10.3, "high": 11.0, "low": 9.7, "close": 10.8, "volume": 1, "atr": 1.0, "camp": 1, "active_low": 9.7, "active_high": 12.0},
    ]


def test_ds05_radar_waits_until_k3_breaks_k2_high() -> None:
    df = pd.DataFrame(base_rows())
    df["date"] = pd.to_datetime(df["date"])
    rows = []

    add_ds05(rows, "RENDERUSDT", df, current=10.8, extreme_atr_tol=0.8)

    assert rows == []


def test_ds05_radar_waits_until_k3_breaks_k2_low_for_short() -> None:
    df = pd.DataFrame(
        [
            {"date": "2026-05-22", "open": 10.0, "high": 10.4, "low": 9.4, "close": 9.8, "volume": 1, "atr": 1.0, "camp": -1, "active_low": 8.5, "active_high": 13.0},
            {"date": "2026-05-23", "open": 9.8, "high": 10.5, "low": 9.5, "close": 9.9, "volume": 1, "atr": 1.0, "camp": -1, "active_low": 8.5, "active_high": 13.0},
            {"date": "2026-05-24", "open": 9.9, "high": 10.6, "low": 9.6, "close": 9.7, "volume": 1, "atr": 1.0, "camp": -1, "active_low": 8.5, "active_high": 13.0},
            {"date": "2026-05-25", "open": 9.8, "high": 11.1, "low": 9.6, "close": 10.4, "volume": 1, "atr": 1.0, "camp": -1, "active_low": 8.5, "active_high": 13.0},
            {"date": "2026-05-26", "open": 10.3, "high": 11.0, "low": 9.7, "close": 9.9, "volume": 1, "atr": 1.0, "camp": -1, "active_low": 8.5, "active_high": 13.0},
        ]
    )
    df["date"] = pd.to_datetime(df["date"])
    rows = []

    add_ds05(rows, "SIUSDT", df, current=9.9, extreme_atr_tol=0.8)

    assert rows == []


def test_ds05_radar_triggered_after_k3_breaks_k2_high() -> None:
    data = base_rows()
    data[-1]["high"] = 11.2
    df = pd.DataFrame(data)
    df["date"] = pd.to_datetime(df["date"])
    rows = []

    add_ds05(rows, "RENDERUSDT", df, current=11.15, extreme_atr_tol=0.8)

    assert len(rows) == 1
    assert rows[0].status == "TRIGGERED"


def test_ds05_radar_does_not_require_k2_near_old_red_ext() -> None:
    data = base_rows()
    data[-1]["high"] = 11.2
    for row in data:
        row["active_low"] = 5.0
    df = pd.DataFrame(data)
    df["date"] = pd.to_datetime(df["date"])
    rows = []

    add_ds05(rows, "RENDERUSDT", df, current=11.15, extreme_atr_tol=0.8)

    assert len(rows) == 1
    assert rows[0].status == "TRIGGERED"
    assert "k2_possible_extreme" in rows[0].reason
