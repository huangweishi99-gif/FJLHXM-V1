from __future__ import annotations

import json
from pathlib import Path

import pytest

from fengji_core.futures_main_contract import (
    detect_order_contract_switch,
    load_manifest,
    lookup_data_contract,
    short_code_from_symbol,
    stamp_entry_data_contract,
)


def test_short_code_from_symbol():
    assert short_code_from_symbol("LHUSDT") == "LH"
    assert short_code_from_symbol("LH") == "LH"
    assert short_code_from_symbol("000063") == "000063"


def test_lookup_and_stamp(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    manifest = {
        "mode": "tq_actual_main_contract",
        "symbols": {
            "LH": {
                "tq_code": "KQ.m@DCE.lh",
                "data_contract": "DCE.lh2609",
                "underlying_symbol": "DCE.lh2609",
            }
        },
    }
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    monkeypatch.setenv("FUTURES_MAIN_CONTRACT_MANIFEST", str(path))

    assert lookup_data_contract("LH", manifest) == "DCE.lh2609"
    assert lookup_data_contract("LHUSDT", manifest) == "DCE.lh2609"

    pos: dict = {"key": "k1"}
    stamp_entry_data_contract(pos, "LHUSDT", root=tmp_path)
    assert pos["entry_data_contract"] == "DCE.lh2609"


def test_contract_switch_audit(monkeypatch, tmp_path):
    import importlib
    import sys

    monkeypatch.setenv("FUTURES_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("FUTURES_LOG_DIR", str(tmp_path / "logs"))
    monkeypatch.setenv("FUTURES_MAIN_CONTRACT_MANIFEST", str(tmp_path / "logs" / "manifest.json"))
    sys.modules.pop("data_manager_futures", None)
    dm = importlib.import_module("data_manager_futures")

    dm.write_main_contract_identity("LH", "KQ.m@DCE.lh", "DCE.lh2609", "DCE.lh2609")
    dm.write_main_contract_identity("LH", "KQ.m@DCE.lh", "DCE.lh2611", "DCE.lh2611")

    manifest = json.loads(dm.MAIN_CONTRACT_MANIFEST.read_text(encoding="utf-8"))
    entry = manifest["symbols"]["LH"]
    assert entry["data_contract"] == "DCE.lh2611"
    assert entry["previous_data_contract"] == "DCE.lh2609"
    assert entry.get("contract_switched_at")


def test_detect_legacy_order_created_before_contract_switch() -> None:
    manifest = {
        "symbols": {
            "JD": {
                "data_contract": "DCE.jd2609",
                "previous_data_contract": "DCE.jd2608",
                "contract_switched_at": "2026-07-15 13:02:29",
            }
        }
    }
    order = {
        "symbol": "JDUSDT",
        "created_at": "2026-07-15 13:01:04",
        "time": "2026-07-15 13:02:40",
    }

    result = detect_order_contract_switch(order, manifest)

    assert result is not None
    assert result["order_contract"] == "DCE.jd2608"
    assert result["current_contract"] == "DCE.jd2609"
    assert result["detection"] == "legacy_order_created_before_switch"


def test_detect_explicit_order_contract_mismatch() -> None:
    manifest = {"symbols": {"JD": {"data_contract": "DCE.jd2609"}}}
    order = {"symbol": "JDUSDT", "data_contract": "DCE.jd2608"}

    result = detect_order_contract_switch(order, manifest)

    assert result is not None
    assert result["detection"] == "explicit_order_contract"
