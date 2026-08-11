from __future__ import annotations

import argparse
import importlib.util
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import ModuleType

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]


def load_paper_module() -> ModuleType:
    manifest = ROOT / "scripts" / "domestic_paper_manifest.txt"
    name = manifest.read_text(encoding="utf-8").splitlines()[0].strip()
    path = ROOT / "remote_domestic_optimize" / name
    spec = importlib.util.spec_from_file_location("domestic_paper_state_lock_test", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_paper_commit_and_pending_update_share_state_lock(tmp_path: Path) -> None:
    paper = load_paper_module()
    state_path = tmp_path / "state_futures_v2.json"
    args = argparse.Namespace(
        entry_lookback_hours=3,
        max_ds01_entries=3,
        max_open_positions_per_symbol=3,
    )

    def commit_paper(index: int) -> None:
        scan = {
            "clean": "URUSDT",
            "display": "UR",
            "bar_key": f"1d:2026-07-16|1h:2026-07-16 {index:02d}:00:00",
            "h1_time": pd.Timestamp("2026-07-16 10:00:00"),
            "accepted": pd.DataFrame(),
        }
        paper.commit_symbol_scan(state_path, "UR", args, f"run-{index}", scan)

    def commit_pending(index: int) -> None:
        def mutator(state: dict) -> None:
            paper.normalize_state(state)
            symbol_state = paper.init_symbol_state(state["symbols"], "URUSDT")
            symbol_state["open_positions"].append(
                {"key": f"pending-{index}", "order_id": f"order-{index}", "side": 1}
            )

        paper.update_state_file(state_path, mutator, default=paper.new_state())

    for index in range(20):
        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [executor.submit(commit_paper, index), executor.submit(commit_pending, index)]
            for future in futures:
                future.result()

    state = json.loads(state_path.read_text(encoding="utf-8"))
    symbol_state = state["symbols"]["URUSDT"]
    order_ids = {position.get("order_id") for position in symbol_state["open_positions"]}

    assert order_ids == {f"order-{index}" for index in range(20)}
    assert symbol_state["initialized"] is True
    assert symbol_state["last_bar_key"].startswith("1d:2026-07-16|1h:")


def test_duplicate_bar_commit_does_not_repeat_effects(tmp_path: Path) -> None:
    paper = load_paper_module()
    state_path = tmp_path / "state_futures_v2.json"
    args = argparse.Namespace(
        entry_lookback_hours=3,
        max_ds01_entries=3,
        max_open_positions_per_symbol=3,
    )
    scan = {
        "clean": "URUSDT",
        "display": "UR",
        "bar_key": "1d:2026-07-16|1h:2026-07-16 10:00:00",
        "h1_time": pd.Timestamp("2026-07-16 10:00:00"),
        "accepted": pd.DataFrame({"trade_key": ["URUSDT|DS01|2026-07-16 10:00:00|1234|1"]}),
    }

    _, first_effects = paper.commit_symbol_scan(state_path, "UR", args, "run-1", scan)
    _, second_effects = paper.commit_symbol_scan(state_path, "UR", args, "run-2", scan)

    assert first_effects == [{"kind": "print", "message": "[UR] 完成基线数据初始化"}]
    assert second_effects == []
