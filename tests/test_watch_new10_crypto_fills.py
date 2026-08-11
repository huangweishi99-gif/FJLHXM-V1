from __future__ import annotations

import json
from pathlib import Path


def test_watch_detects_order_id_change() -> None:
    paper = {
        "symbols": {
            "OPUSDT": {
                "open_position": {
                    "order_id": "OP-new-id",
                    "strategy_id": "DS01",
                    "entry_time": "2026-06-20 22:02:49",
                }
            }
        }
    }
    seen = {"OPUSDT": "OP-old-id"}
    current = {
        "OPUSDT": {
            "order_id": "OP-new-id",
            "strategy_id": "DS01",
            "entry_time": "2026-06-20 22:02:49",
        }
    }
    new_syms = [
        sym
        for sym, pos in current.items()
        if sym not in seen or str(seen.get(sym) or "") != str(pos.get("order_id") or "")
    ]
    assert new_syms == ["OPUSDT"]
