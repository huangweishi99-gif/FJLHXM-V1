from __future__ import annotations

from types import SimpleNamespace

import pandas as pd

from fengji_total_radar import add_ds01, add_ds03


def engine() -> SimpleNamespace:
    return SimpleNamespace(hardened_by_bar=[[], []])


def test_ds01_radar_carries_signal_stick_setup_key() -> None:
    df = pd.DataFrame(
        [
            {"date": "2026-05-25", "open": 9.0, "high": 10.0, "low": 8.8, "close": 9.8, "camp": 1},
            {"date": "2026-05-26", "open": 9.8, "high": 9.9, "low": 9.2, "close": 9.5, "camp": 1},
        ]
    )
    df["date"] = pd.to_datetime(df["date"])
    rows = []

    add_ds01(rows, "RENDERUSDT", df, engine(), current=9.5)

    assert len(rows) == 1
    assert rows[0].setup_key == "RENDERUSDT|DS01|LONG|signal=20260525000000|trigger=10"


def test_ds03_radar_carries_active_attack_setup_key() -> None:
    df = pd.DataFrame(
        [
            {
                "date": "2026-05-25",
                "open": 9.0,
                "high": 9.8,
                "low": 8.8,
                "close": 9.6,
                "camp": 1,
                "active_high": 10.0,
                "active_low": 8.5,
                "red_peak_idx": 23,
            },
            {
                "date": "2026-05-26",
                "open": 9.6,
                "high": 9.9,
                "low": 9.2,
                "close": 9.5,
                "camp": 1,
                "active_high": 10.0,
                "active_low": 8.5,
                "red_peak_idx": 23,
            },
        ]
    )
    df["date"] = pd.to_datetime(df["date"])
    rows = []

    add_ds03(rows, "RENDERUSDT", df, current=9.5)

    assert len(rows) == 1
    # 无 resolve_ds03_attack 时：上一根阵营 + 破 active 极 → watch 挂单键
    assert rows[0].setup_key == "RENDERUSDT|DS03|LONG|watch|trigger=10"


def test_ds03_radar_uses_failed_peak_after_later_extreme() -> None:
    df = pd.DataFrame(
        [
            {
                "date": "2026-05-25",
                "open": 9.0,
                "high": 9.3,
                "low": 8.8,
                "close": 9.1,
                "camp": 1,
                "active_high": 10.0,
                "red_peak_idx": 23,
                "red_ext_idx": 30,
                "last_failed_high_idx": 28,
                "last_failed_high_price": 9.5,
            },
            {
                "date": "2026-05-26",
                "open": 9.1,
                "high": 9.6,
                "low": 9.0,
                "close": 9.4,
                "camp": 1,
                "active_high": 10.0,
                "red_peak_idx": 23,
                "red_ext_idx": 31,
                "last_failed_high_idx": 28,
                "last_failed_high_price": 9.5,
            },
        ]
    )
    for i in range(6):
        df.loc[-i - 1] = df.iloc[0]
    df = df.sort_index().reset_index(drop=True)
    df["date"] = pd.date_range("2026-05-19", periods=len(df), freq="D")
    rows = []

    add_ds03(rows, "IOUSDT", df, current=9.4)

    assert len(rows) == 1
    assert rows[0].trigger_price == 9.5
    assert rows[0].status == "TRIGGERED"
    assert rows[0].setup_key == "IOUSDT|DS03|1|fake_peak|idx=28|px=9.5"
