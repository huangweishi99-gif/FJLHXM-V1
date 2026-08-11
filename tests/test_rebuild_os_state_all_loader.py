from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "rebuild_os_state_all.py"


def load_module():
    spec = importlib.util.spec_from_file_location("rebuild_os_state_all", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["rebuild_os_state_all"] = module
    spec.loader.exec_module(module)
    return module


def test_rebuild_loader_keeps_zero_volume_price_move_but_drops_placeholders(tmp_path: Path) -> None:
    module = load_module()
    path = tmp_path / "LC.csv"
    pd.DataFrame(
        [
            {"date": "2026-06-01 16:00:00", "open": 170000, "high": 171000, "low": 169000, "close": 170500, "volume": 10},
            {"date": "2026-06-02 16:00:00", "open": 170500, "high": 170500, "low": 170500, "close": 170500, "volume": 0},
            {"date": "2026-06-03 16:00:00", "open": 170500, "high": 172000, "low": 170000, "close": 171500, "volume": 0},
            {"date": "2026-06-04 16:00:00", "open": 6.5181547e-143, "high": 5.040429e180, "low": 3.183734e-312, "close": 3.189770e-312, "volume": 6360567320059846688},
            {"date": "2117-11-11 06:26:59", "open": 8715, "high": 9165, "low": 9135, "close": 8750, "volume": 100},
        ]
    ).to_csv(path, index=False)

    frame = module.load_ohlcv(path, market="futures")

    assert frame["date"].dt.strftime("%Y-%m-%d").tolist() == ["2026-06-01", "2026-06-03"]
    assert frame["close"].tolist() == [170500, 171500]


def test_rebuild_source_dedupe_prefers_futures_short_code_csv(tmp_path: Path) -> None:
    module = load_module()
    data_dir = tmp_path / "data" / "1d"
    data_dir.mkdir(parents=True)
    rows = "date,open,high,low,close,volume\n2026-06-01,1,2,1,2,1\n"
    (data_dir / "EG.csv").write_text(rows, encoding="utf-8")
    (data_dir / "EGUSDT.csv").write_text(rows, encoding="utf-8")

    spec = module.parse_input_spec(f"{data_dir},market=futures,timeframe=1d")
    chosen = {}
    for source in module.discover_sources(spec):
        key = (source.market, module.state_symbol(source.symbol, source.market), source.timeframe)
        current = chosen.get(key)
        if current is None or module.source_preference_key(source) < module.source_preference_key(current):
            chosen[key] = source

    assert chosen[("futures", "EG", "1d")].path.name == "EG.csv"
