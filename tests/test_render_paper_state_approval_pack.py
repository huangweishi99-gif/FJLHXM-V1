from __future__ import annotations

import json
from pathlib import Path

from scripts.render_paper_state_approval_pack import build_pack, render_markdown


def test_build_pack_pp_skip_rollback(tmp_path: Path) -> None:
    state = {
        "symbols": {
            "PPUSDT": {
                "equity": 99937.279,
                "open_positions": [],
                "audit_invalid_closes": [
                    {
                        "order_id": "PPUSDT-DS01-D1-long-44b9d7cd48133592",
                        "new_equity": 99937.279,
                        "fake_net_pnl": -88146.44,
                    }
                ],
            },
            "PGUSDT": {
                "open_positions": [
                    {"symbol": "PGUSDT", "strategy_id": "DS01", "direction": "short", "entry_time": "2026-06-15"},
                    {"symbol": "PGUSDT", "strategy_id": "DS03", "direction": "short", "entry_time": "2026-06-12"},
                ],
                "audit_invalid_positions": [],
            },
        }
    }
    state_path = tmp_path / "state.json"
    state_path.write_text(json.dumps(state), encoding="utf-8")
    pack = build_pack(state_path=state_path, manifest_path=tmp_path / "missing.json")
    assert pack["pp_equity"]["recommendation"] == "SKIP_ROLLBACK"
    assert pack["summary"]["open_positions"] == 2
    md = render_markdown(pack)
    assert "SKIP_ROLLBACK" in md
    assert "PGUSDT" in md
