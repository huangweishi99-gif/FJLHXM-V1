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


def test_ds05_radar_pending_before_k3_breaks_k2_high() -> None:
    df = pd.DataFrame(base_rows())
    df["date"] = pd.to_datetime(df["date"])
    rows = []

    add_ds05(rows, "RENDERUSDT", df, current=10.8, extreme_atr_tol=0.8)

    assert len(rows) == 1
    assert rows[0].strategy_id == "DS05"
    assert rows[0].side == "long"
    assert rows[0].status == "PENDING"
    assert rows[0].trigger_price == 11.1
    assert rows[0].stop_price == 9.6
    assert rows[0].setup_key == "RENDERUSDT|DS05|LONG|k2=20260525000000|k3=20260526000000|trigger=11.1"


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
