from __future__ import annotations

import pandas as pd

from fengji_core.runtime_stop_updater import _normalize_ohlcv


def test_runtime_stop_loader_filters_placeholders_but_keeps_zero_volume_moving_bar(monkeypatch) -> None:
    monkeypatch.setenv("FENGJI_MARKET", "futures")
    frame = pd.DataFrame(
        [
            {
                "datetime": pd.Timestamp("2026-06-01 16:00:00").value,
                "open": 100.0,
                "high": 103.0,
                "low": 99.0,
                "close": 102.0,
                "volume": 10,
            },
            {
                "datetime": pd.Timestamp("2026-06-02 16:00:00").value,
                "open": 102.0,
                "high": 102.0,
                "low": 102.0,
                "close": 102.0,
                "volume": 0,
            },
            {
                "datetime": pd.Timestamp("2026-06-03 16:00:00").value,
                "open": 102.0,
                "high": 104.0,
                "low": 101.0,
                "close": 103.0,
                "volume": 0,
            },
            {
                "datetime": pd.Timestamp("2026-06-04 16:00:00").value,
                "open": 6.5181547e-143,
                "high": 5.040429e180,
                "low": 3.183734e-312,
                "close": 3.189770e-312,
                "volume": 6360567320059846688,
            },
        ]
    )

    out = _normalize_ohlcv(frame)

    assert out["date"].dt.strftime("%Y-%m-%d").tolist() == ["2026-06-01", "2026-06-03"]
    assert out["close"].tolist() == [102.0, 103.0]
