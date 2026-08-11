from __future__ import annotations

import json
from pathlib import Path

from scripts.check_ds09_feishu_dedup_state import check_state


def test_check_state_ok_when_semantic_present_despite_legacy_ids() -> None:
    state = {
        "notified_pending_order_ids": [
            "TRUMPUSDT-DS09-M15-long-aaaaaaaaaaaaaaaa",
            "TRUMPUSDT-DS09-M15-long-bbbbbbbbbbbbbbbb",
        ],
        "notified_pending_semantic_keys": [
            "pending_semantic|TRUMPUSDT|DS09|M15|long|1.686|1.64",
        ],
    }
    result = check_state(state, [], symbol="TRUMPUSDT")
    assert result["status"] == "ok"
    assert result["legacy_notified_order_ids"] == 2


def test_check_state_warn_when_legacy_spam_without_semantic(tmp_path: Path) -> None:
    state = {
        "notified_pending_order_ids": [
            "TRUMPUSDT-DS09-M15-long-aaaaaaaaaaaaaaaa",
            "TRUMPUSDT-DS09-M15-long-bbbbbbbbbbbbbbbb",
        ],
        "notified_pending_semantic_keys": [],
    }
    result = check_state(state, [], symbol="TRUMPUSDT")
    assert result["status"] == "warn"
    assert "legacy_order_id_spam_without_semantic_key" in result["issues"]
