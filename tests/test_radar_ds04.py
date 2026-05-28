from __future__ import annotations

import pandas as pd

from fengji_total_radar import add_ds04
from fengji_pending_orders import convert_radar_rows


def ds04_long_frame() -> pd.DataFrame:
    df = pd.DataFrame(
        [
            {"date": "2026-05-19 16:00:00", "open": 1022, "high": 1027, "low": 1007, "close": 1013, "camp": 0},
            {"date": "2026-05-20 16:00:00", "open": 1014, "high": 1040, "low": 1011, "close": 1028, "camp": 0},
            {"date": "2026-05-21 16:00:00", "open": 1029, "high": 1033, "low": 1013, "close": 1020, "camp": 0},
            {"date": "2026-05-24 16:00:00", "open": 1021, "high": 1057, "low": 1015, "close": 1044, "camp": 0},
            {"date": "2026-05-25 16:00:00", "open": 1043, "high": 1046, "low": 1021, "close": 1025, "camp": 0},
        ]
    )
    df["date"] = pd.to_datetime(df["date"])
    return df


def test_ds04_radar_exports_k4_open_actionable_order() -> None:
    rows = []

    add_ds04(rows, "FGUSDT", ds04_long_frame(), current=1025)

    assert len(rows) == 1
    row = rows[0]
    assert row.strategy_id == "DS04"
    assert row.side == "long"
    assert row.status == "PENDING"
    assert row.trigger_price == 1043
    assert row.stop_price == 1011
    assert "reclaim_price=1040" in row.reason


def test_ds04_pending_is_actionable_by_default() -> None:
    rows = []
    add_ds04(rows, "FGUSDT", ds04_long_frame(), current=1025)

    orders = convert_radar_rows(
        [rows[0].__dict__],
        include_strategies={"DS01", "DS03", "DS04", "DS05", "DS07", "DS08"},
        include_triggered=False,
        max_distance_pct=0.08,
        created_at="2026-05-26 10:00:00",
    )

    assert len(orders) == 1
    assert orders[0].strategy_id == "DS04"
    assert orders[0].trigger_price == 1043
