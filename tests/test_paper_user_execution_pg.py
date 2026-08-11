from __future__ import annotations

import json

from db.paper_user_execution import (
    parse_open_positions_from_state,
    parse_pending_orders_from_json,
)


def test_parse_open_positions_from_state() -> None:
    data = {
        "symbols": {
            "BTCUSDT": {
                "open_position": {
                    "key": "k1",
                    "symbol": "BTCUSDT",
                    "strategy_id": "DS01",
                    "direction": "long",
                    "entry_price": 65000,
                    "current_stop": 62000,
                }
            }
        }
    }
    rows = parse_open_positions_from_state(data)
    assert len(rows) == 1
    assert rows[0]["symbol"] == "BTCUSDT"
    assert rows[0]["strategy_id"] == "DS01"
    assert rows[0]["entry_price"] == 65000.0


def test_parse_pending_orders_from_json_list() -> None:
    payload = [
        {
            "order_id": "o1",
            "symbol": "ETHUSDT",
            "strategy_id": "DS03",
            "side": "long",
            "trigger_price": 3000,
            "stop_price": 2900,
            "status": "ACTIVE",
        },
        {"order_id": "o2", "symbol": "BTCUSDT", "status": "FILLED"},
    ]
    rows = parse_pending_orders_from_json(payload)
    assert len(rows) == 1
    assert rows[0]["order_id"] == "o1"


def test_build_execution_payloads_json_fallback(tmp_path, monkeypatch) -> None:
    from services import monitor_paper_account
    from services.paper_execution.paths import UserPaperPaths

    user_root = tmp_path / "paper_users" / "u9" / "crypto"
    user_root.mkdir(parents=True)
    (user_root / "paper_state.json").write_text(
        json.dumps(
            {
                "symbols": {
                    "BTCUSDT": {
                        "open_position": {
                            "key": "k1",
                            "strategy_id": "DS01",
                            "direction": "long",
                            "entry_price": 1,
                            "current_stop": 0.9,
                        }
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    (user_root / "pending").mkdir(parents=True, exist_ok=True)
    (user_root / "pending" / "pending_orders.json").write_text(
        json.dumps([{"order_id": "p1", "symbol": "ETHUSDT", "strategy_id": "DS01", "status": "ACTIVE", "trigger_price": 2, "stop_price": 1.8}]),
        encoding="utf-8",
    )

    import services.paper_execution.paths as pep

    monkeypatch.setattr(pep, "PAPER_USERS_ROOT", tmp_path / "paper_users")
    monkeypatch.setattr(
        monitor_paper_account,
        "_user_execution_paths",
        lambda user_id: UserPaperPaths(user_id=user_id, root_dir=tmp_path / "paper_users"),
    )
    monkeypatch.setattr(
        "db.paper_user_execution.list_user_open_positions",
        lambda *_a, **_k: (_ for _ in ()).throw(RuntimeError("no pg")),
        raising=False,
    )
    monkeypatch.setattr(
        "db.paper_user_execution.list_user_pending_orders",
        lambda *_a, **_k: (_ for _ in ()).throw(RuntimeError("no pg")),
        raising=False,
    )

    pos = monitor_paper_account.build_user_execution_positions_payload(user_id="u9")
    pend = monitor_paper_account.build_user_execution_pending_payload(user_id="u9")
    assert pos["count"] == 1
    assert pos["source"] == "json"
    assert pend["count"] == 1
    assert pend["items"][0]["order_id"] == "p1"
