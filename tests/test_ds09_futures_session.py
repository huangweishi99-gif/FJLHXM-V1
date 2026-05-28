from __future__ import annotations

import pandas as pd

from fengji_core.ds09 import RED, assign_cn_futures_session_date, assign_session_date, build_prev_day_boundary_map


def test_cn_futures_night_bar_maps_to_next_calendar_session() -> None:
    """21:00 夜盘 K 线应归属下一交易日 session（与 D1 对齐）。"""
    d1 = pd.DataFrame(
        {
            "date": pd.to_datetime(["2026-05-26", "2026-05-27", "2026-05-28"]),
            "open": [10.0, 11.0, 12.0],
            "high": [11.0, 12.0, 13.0],
            "low": [9.0, 10.0, 11.0],
            "close": [10.5, 11.5, 12.5],
            "camp": [RED, RED, RED],
        }
    )
    m15 = pd.DataFrame(
        {
            "date": pd.to_datetime(["2026-05-26 21:15:00", "2026-05-27 09:15:00"]),
            "open": [11.0, 12.0],
            "high": [11.5, 12.5],
            "low": [10.8, 11.8],
            "close": [11.2, 12.2],
        }
    )
    out = assign_cn_futures_session_date(m15, d1)
    assert len(out) == 2
    assert pd.Timestamp(out.iloc[0]["session_date"]).normalize() == pd.Timestamp("2026-05-27")
    assert pd.Timestamp(out.iloc[1]["session_date"]).normalize() == pd.Timestamp("2026-05-27")
    assert pd.to_datetime(m15.iloc[0]["date"]).hour >= 21


def test_assign_session_date_futures_flag() -> None:
    d1 = pd.DataFrame(
        {
            "date": pd.to_datetime(["2026-05-27"]),
            "open": [11.0],
            "high": [12.0],
            "low": [10.0],
            "close": [11.5],
            "camp": [RED],
        }
    )
    m15 = pd.DataFrame(
        {
            "date": pd.to_datetime(["2026-05-26 22:00:00"]),
            "open": [11.0],
            "high": [12.0],
            "low": [10.5],
            "close": [11.8],
        }
    )
    out = assign_session_date(m15, d1, futures=True)
    assert pd.Timestamp(out["session_date"].iloc[0]).normalize() == pd.Timestamp("2026-05-27")
