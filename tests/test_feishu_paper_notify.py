from __future__ import annotations

import pandas as pd

from fengji_feishu_paper_notify import (
    notify_paper_close,
    notify_paper_open,
    validate_paper_open_row,
)


def test_validate_paper_open_row_rejects_bad_stop() -> None:
    row = pd.Series(
        {
            "symbol": "BTCUSDT",
            "strategy_id": "DS04",
            "side": 1,
            "entry_price": 100.0,
            "initial_stop": 101.0,
        }
    )
    check = validate_paper_open_row(row)
    assert check.ok is False


def test_validate_paper_open_row_accepts_good_geometry() -> None:
    row = pd.Series(
        {
            "symbol": "BTCUSDT",
            "strategy_id": "DS04",
            "side": 1,
            "entry_price": 100.0,
            "initial_stop": 95.0,
        }
    )
    assert validate_paper_open_row(row).ok is True
