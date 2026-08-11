from __future__ import annotations

import json
from pathlib import Path

from services import monitor_paper_account


def test_build_user_paper_account_summary_guest() -> None:
    payload = monitor_paper_account.build_user_paper_account_summary(user_id="")
    assert payload["authenticated"] is False
    assert payload["equity"] is None


def test_build_user_paper_account_summary_scoped(tmp_path: Path, monkeypatch) -> None:
    paper_state = tmp_path / "domestic_paper_state.json"
    paper_state.write_text(
        json.dumps(
            {
                "symbols": {
                    "SAUSDT": {
                        "equity": 101234.5,
                        "open_positions": [{"symbol": "SAUSDT", "direction": "long", "entry_price": 1500, "lots": 1, "multiplier": 20}],
                    },
                    "LCUSDT": {"equity": 99000.0, "open_positions": []},
                }
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(monitor_paper_account, "PAPER_ACCOUNTS_DIR", tmp_path / "paper_accounts")
    monkeypatch.setattr(monitor_paper_account, "load_paper_state_path", lambda: paper_state)
    monkeypatch.setattr(
        monitor_paper_account,
        "load_latest_opens",
        lambda: {
            "source": "paper_state",
            "positions": [
                {"symbol": "SAUSDT", "market": "FUTURES", "amount_cny": 30000},
            ],
        },
    )
    monkeypatch.setattr(
        monitor_paper_account,
        "load_overseas_latest_opens",
        lambda: {"source": "paper_state", "positions": []},
    )
    monkeypatch.setattr(monitor_paper_account, "_persist_pg_account", lambda **_: (None, []))

    payload = monitor_paper_account.build_user_paper_account_summary(
        user_id="user-1",
        plan_id="pro",
        local_watchlist_count=2,
        local_watchlist_symbols=["SA", "000021"],
        pg_watchlist=[{"symbol": "SA", "market": "FUTURES", "status": "pending_runtime"}],
    )
    assert payload["authenticated"] is True
    assert payload["user_id"] == "user-1"
    assert payload["equity"] == 101234.5
    assert payload["watchlist"]["pg_runtime_pending"] == 1
    assert payload["open_positions"] == 1
    assert payload["storage_backend"] == "json_fallback"
    assert "V1.1" in payload["disclaimer"]


def test_build_user_paper_account_includes_overseas_scoped_positions(monkeypatch) -> None:
    monkeypatch.setattr(
        monitor_paper_account,
        "load_latest_opens",
        lambda: {
            "source": "paper_state",
            "positions": [{"symbol": "PG", "market": "FUTURES", "amount_cny": 1000}],
        },
    )
    monkeypatch.setattr(
        monitor_paper_account,
        "load_overseas_latest_opens",
        lambda: {
            "source": "paper_state",
            "positions": [{"symbol": "BNBUSDT", "market": "CRYPTO", "amount_cny": 400}],
        },
    )
    monkeypatch.setattr(monitor_paper_account, "_equity_from_paper_state", lambda keys: (None, None, 0))
    monkeypatch.setattr(monitor_paper_account, "_persist_pg_account", lambda **_: (None, []))

    payload = monitor_paper_account.build_user_paper_account_summary(
        user_id="user-2",
        local_watchlist_symbols=["PG", "BNB"],
    )
    assert payload["open_positions"] == 2
    assert payload["shared_reference"]["overseas_source"] == "paper_state"


def test_build_user_paper_account_pg_storage(monkeypatch) -> None:
    monkeypatch.setattr(monitor_paper_account, "_equity_from_paper_state", lambda keys: (100500.0, None, 1))
    monkeypatch.setattr(
        monitor_paper_account,
        "load_latest_opens",
        lambda: {"source": "paper_state", "positions": []},
    )
    monkeypatch.setattr(
        monitor_paper_account,
        "load_overseas_latest_opens",
        lambda: {"source": "empty", "positions": []},
    )
    monkeypatch.setattr(
        monitor_paper_account,
        "_persist_pg_account",
        lambda **_: (
            {"id": "acc-1", "user_id": "user-3", "equity": 100500.0, "cash": 100500.0},
            [{"event_type": "scoped_projection"}],
        ),
    )

    payload = monitor_paper_account.build_user_paper_account_summary(
        user_id="user-3",
        local_watchlist_symbols=["SA"],
    )
    assert payload["storage_backend"] == "pg"
    assert payload["account_mode"] == "per_user_pg_v1_1"
    assert payload["pg_account"]["id"] == "acc-1"
    assert payload["ledger_preview"][0]["event_type"] == "scoped_projection"


def test_build_user_paper_account_execution_mode(tmp_path: Path, monkeypatch) -> None:
    user_root = tmp_path / "paper_users" / "exec-user" / "crypto"
    user_root.mkdir(parents=True)
    paper_state = user_root / "paper_state.json"
    paper_state.write_text(
        json.dumps(
            {
                "equity": 100250.0,
                "symbols": {
                    "BTCUSDT": {
                        "equity": 100250.0,
                        "open_position": {
                            "symbol": "BTCUSDT",
                            "strategy_id": "DS01",
                            "direction": "long",
                            "entry_price": 65000,
                        },
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(monitor_paper_account, "PAPER_ACCOUNTS_DIR", tmp_path / "paper_accounts")
    monkeypatch.setattr(
        monitor_paper_account,
        "load_latest_opens",
        lambda: {"source": "paper_state", "positions": []},
    )
    monkeypatch.setattr(
        monitor_paper_account,
        "load_overseas_latest_opens",
        lambda: {"source": "empty", "positions": []},
    )
    monkeypatch.setattr(monitor_paper_account, "_persist_pg_account", lambda **_: (None, []))

    import services.paper_execution.paths as pep
    from services.paper_execution.paths import UserPaperPaths

    monkeypatch.setattr(pep, "PAPER_USERS_ROOT", tmp_path / "paper_users")
    monkeypatch.setattr(
        monitor_paper_account,
        "_user_execution_paths",
        lambda user_id: UserPaperPaths(user_id=user_id, root_dir=tmp_path / "paper_users"),
    )

    payload = monitor_paper_account.build_user_paper_account_summary(
        user_id="exec-user",
        plan_id="pro",
        paper_mode="execution",
    )
    assert payload["paper_account_view"] == "execution"
    assert "execution" in payload["account_mode"]
    assert payload["open_positions"] == 1
    assert payload["equity"] == 100250.0
    assert payload["positions_preview"][0]["symbol"] == "BTCUSDT"
