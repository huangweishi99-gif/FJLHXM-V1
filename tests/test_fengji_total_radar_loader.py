from __future__ import annotations

from pathlib import Path
from argparse import Namespace

import pandas as pd

from fengji_total_radar import load_ohlcv, resolve_market, resolve_symbols


def test_futures_loader_drops_flat_zero_volume_placeholders_only(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("FENGJI_MARKET", "futures")
    path = tmp_path / "FG.csv"
    pd.DataFrame(
        [
            {"date": "2026-06-01 16:00:00", "open": 1000, "high": 1010, "low": 990, "close": 1005, "volume": 100},
            {"date": "2026-06-02 16:00:00", "open": 1005, "high": 1005, "low": 1005, "close": 1005, "volume": 0},
            {"date": "2026-06-03 16:00:00", "open": 1005, "high": 1015, "low": 995, "close": 1008, "volume": 0},
            {"date": "2026-06-04 15:00:00", "open": 6.5181547e-143, "high": 5.040429e180, "low": 3.183734e-312, "close": 3.189770e-312, "volume": 6360567320059846688},
            {"date": "2026-06-04 16:00:00", "open": 1008, "high": 1020, "low": 1000, "close": 1018, "volume": 120},
        ]
    ).to_csv(path, index=False)

    frame = load_ohlcv(path)

    assert frame["date"].dt.strftime("%Y-%m-%d").tolist() == ["2026-06-01", "2026-06-03", "2026-06-04"]


def test_total_radar_resolve_market_infers_futures_without_environment() -> None:
    args = Namespace(market="auto", symbols="SA,FG,LC", data_dir="data")

    assert resolve_market(args, {}) == "futures"


def test_total_radar_discovers_futures_symbols_when_empty(tmp_path: Path) -> None:
    one_day = tmp_path / "1d"
    one_day.mkdir()
    for name in ["PP.csv", "PPUSDT.csv", "EC.csv", "SI.csv"]:
        (one_day / name).write_text("date,open,high,low,close,volume\n", encoding="utf-8")

    args = Namespace(symbols="")

    assert resolve_symbols(args, "futures", tmp_path) == ["ECUSDT", "PPUSDT", "SIUSDT"]


def test_total_radar_uses_crypto_defaults_when_symbols_empty(tmp_path: Path) -> None:
    args = Namespace(symbols="")

    symbols = resolve_symbols(args, "crypto", tmp_path)

    assert "BTCUSDT" in symbols
    assert "IOUSDT" in symbols
