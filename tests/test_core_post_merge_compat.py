from __future__ import annotations

import pandas as pd

from fengji_core.constants import STRATEGY_DISPLAY_NAMES
from fengji_core.ds07 import make_ds07_signal


def test_strategy_display_names_covers_all_ds() -> None:
    for sid in ("DS01", "DS02", "DS03", "DS04", "DS05", "DS06", "DS07", "DS08", "DS09"):
        assert sid in STRATEGY_DISPLAY_NAMES
        assert STRATEGY_DISPLAY_NAMES[sid]


def test_make_ds07_signal_accepts_optional_df_kwarg() -> None:
    row = pd.Series({"d1_camp": 0, "camp": 0, "open": 1.0, "high": 1.0, "low": 1.0})
    prev = pd.Series({"camp": 0, "open": 1.0, "high": 1.0, "low": 1.0})
    df = pd.DataFrame([prev, row])
    assert make_ds07_signal(row, 1, set(), prev_row=prev, df=df) is None
