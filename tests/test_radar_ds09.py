from __future__ import annotations

import pandas as pd

from fengji_core.ds09 import BLUE, RED, assign_session_date, build_prev_day_boundary_map
from fengji_total_radar import add_ds09, replay_ds09_session


def d1_frame() -> pd.DataFrame:
    # 2026-05-27 多头授权：昨日(05-26)红阵营 + 阴线，边界=昨日高点
    return pd.DataFrame(
        {
            "date": pd.to_datetime(["2026-05-25", "2026-05-26", "2026-05-27"]),
            "open": [12.0, 11.0, 8.0],
            "high": [12.8, 12.5, 13.0],
            "low": [8.8, 10.0, 7.5],
            "close": [9.5, 10.0, 8.2],
            "camp": [RED, RED, RED],
        }
    )


def m15_long_bars(include_second_attack: bool) -> pd.DataFrame:
    rows = []
    base = pd.Timestamp("2026-05-27 00:00:00")
    rows.append({"date": base, "open": 8.0, "high": 13.0, "low": 7.9, "close": 12.5, "camp": RED})
    rows.append(
        {
            "date": base + pd.Timedelta(minutes=15),
            "open": 12.5,
            "high": 12.6,
            "low": 12.0,
            "close": 12.2,
            "camp": RED,
            "red_peak_price": 12.6,
            "red_peak_idx": 1,
        }
    )
    rows.append(
        {
            "date": base + pd.Timedelta(minutes=30),
            "open": 12.2,
            "high": 12.3,
            "low": 11.5,
            "close": 11.8,
            "camp": RED,
            "red_peak_price": 12.6,
            "red_peak_idx": 1,
            "red_ext_price": 11.5,
            "red_ext_idx": 2,
        }
    )
    if include_second_attack:
        rows.append(
            {
                "date": base + pd.Timedelta(minutes=45),
                "open": 11.8,
                "high": 12.7,
                "low": 11.7,
                "close": 12.6,
                "camp": RED,
                "red_peak_price": 12.6,
                "red_peak_idx": 1,
                "red_ext_price": 11.5,
                "red_ext_idx": 2,
            }
        )
    df = pd.DataFrame(rows)
    df["session_date"] = pd.to_datetime("2026-05-27")
    return df


def test_ds09_radar_pending_after_defense_before_second_attack() -> None:
    d1 = d1_frame()
    m15 = m15_long_bars(include_second_attack=False)
    rows: list = []
    add_ds09(rows, "ETHUSDT", d1, m15, current=12.0)
    assert len(rows) == 1
    assert rows[0].strategy_id == "DS09"
    assert rows[0].side == "long"
    assert rows[0].status == "PENDING"
    assert rows[0].trigger_price == 12.6
    assert rows[0].stop_price == 11.5
    assert "DS09|LONG|2026-05-27" in rows[0].setup_key


def test_ds09_radar_triggered_on_second_attack_bar() -> None:
    d1 = d1_frame()
    m15 = m15_long_bars(include_second_attack=True)
    boundary_map = build_prev_day_boundary_map(d1)
    _, _, signal = replay_ds09_session(m15, boundary_map, "ETHUSDT")
    assert signal is not None
    rows: list = []
    add_ds09(rows, "ETHUSDT", d1, m15, current=12.6)
    assert len(rows) == 1
    assert rows[0].status == "TRIGGERED"
    assert rows[0].setup_key == signal.key


def test_assign_session_date_crypto_calendar_day() -> None:
    d1 = d1_frame()
    m15 = m15_long_bars(include_second_attack=False).drop(columns=["session_date"])
    out = assign_session_date(m15, d1, futures=False)
    assert out["session_date"].nunique() == 1
    assert pd.Timestamp(out["session_date"].iloc[0]) == pd.Timestamp("2026-05-27")
