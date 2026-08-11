from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "repair_corrupt_futures_csv.py"


def load_module():
    spec = importlib.util.spec_from_file_location("repair_corrupt_futures_csv", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["repair_corrupt_futures_csv"] = module
    spec.loader.exec_module(module)
    return module


def write_bad_pp(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        [
            {
                "datetime": pd.Timestamp("2026-05-29 01:00:00").value,
                "symbol": "DCE.pp2609",
                "open": 6.5181547e-143,
                "high": 5.040429e180,
                "low": 3.183734e-312,
                "close": 3.189770e-312,
                "volume": 6360567320059846688,
            },
            {
                "datetime": pd.Timestamp("2026-06-03 10:15:00").value,
                "symbol": "DCE.pp2609",
                "open": 8700.0,
                "high": 8720.0,
                "low": 8690.0,
                "close": 8710.0,
                "volume": 100,
            },
        ]
    ).to_csv(path, index=False)


def test_discover_dirty_files_collapses_usdt_alias(tmp_path: Path) -> None:
    module = load_module()
    data_dir = tmp_path / "data"
    write_bad_pp(data_dir / "15m" / "PP.csv")
    write_bad_pp(data_dir / "15m" / "PPUSDT.csv")

    dirty = module.discover_dirty_files(data_dir)

    assert len(dirty) == 2
    assert module.unique_symbols(dirty) == ["PP"]
    assert sum(item.dropped for item in dirty) == 2


def test_clean_dirty_files_backs_up_and_removes_corrupt_rows(tmp_path: Path) -> None:
    module = load_module()
    data_dir = tmp_path / "data"
    path = data_dir / "15m" / "PP.csv"
    write_bad_pp(path)
    dirty = module.discover_dirty_files(data_dir)

    records = module.clean_dirty_files(dirty, data_dir, tmp_path / "backup")
    remaining = module.discover_dirty_files(data_dir)
    cleaned = pd.read_csv(path)

    assert len(records) == 1
    assert remaining == []
    assert len(cleaned) == 1
    assert (tmp_path / "backup" / "15m" / "PP.csv").exists()
