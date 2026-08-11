"""Tests for futures main contract manifest audit."""
from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "verify_futures_main_contract_manifest.py"


def load_module():
    spec = importlib.util.spec_from_file_location("verify_futures_main_contract_manifest", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_audit_manifest_passes_actual_contract():
    mod = load_module()
    payload = {
        "mode": "tq_actual_main_contract",
        "symbols": {
            "AG": {
                "tq_code": "KQ.m@SHFE.ag",
                "underlying_symbol": "SHFE.ag2608",
                "data_contract": "SHFE.ag2608",
                "data_contract_is_actual": True,
                "timeframes": {
                    "1d": {
                        "data_contract": "SHFE.ag2608",
                        "source_symbols": ["SHFE.ag2608"],
                    }
                },
            }
        },
    }
    issues, summary = mod.audit_manifest(payload)
    assert not issues
    assert summary["ok_actual"] == 1


def test_audit_manifest_rejects_main_continuous_in_csv():
    mod = load_module()
    payload = {
        "mode": "tq_actual_main_contract",
        "symbols": {
            "LH": {
                "tq_code": "KQ.m@DCE.lh",
                "underlying_symbol": "DCE.lh2609",
                "data_contract": "DCE.lh2609",
                "data_contract_is_actual": True,
                "timeframes": {
                    "1d": {"source_symbols": ["KQ.m@DCE.lh"]},
                },
            }
        },
    }
    issues, _summary = mod.audit_manifest(payload)
    assert any(i["code"] == "MAIN_CONTINUOUS_IN_CSV" for i in issues)
