from __future__ import annotations

import json
from pathlib import Path


def test_resolve_fengji_paper_mode_defaults_shadow(monkeypatch) -> None:
    monkeypatch.delenv("FENGJI_PAPER_MODE", raising=False)
    from paper_execution.mode import PAPER_MODE_SHADOW, resolve_fengji_paper_mode

    assert resolve_fengji_paper_mode() == PAPER_MODE_SHADOW


def test_resolve_default_paper_account_mode_cutover(monkeypatch) -> None:
    monkeypatch.setenv("FENGJI_PAPER_MODE", "per_user_execution")
    monkeypatch.delenv("FENGJI_PAPER_ACCOUNT_MODE", raising=False)
    from paper_execution.mode import resolve_default_paper_account_mode

    assert resolve_default_paper_account_mode() == "execution"


def test_resolve_default_paper_account_mode_shadow_stays_scoped(monkeypatch) -> None:
    monkeypatch.setenv("FENGJI_PAPER_MODE", "shadow")
    monkeypatch.delenv("FENGJI_PAPER_ACCOUNT_MODE", raising=False)
    from paper_execution.mode import resolve_default_paper_account_mode

    assert resolve_default_paper_account_mode() == "scoped"


def test_compare_shadow_snapshots() -> None:
    from paper_execution.shadow import compare_shadow_snapshots

    delta = compare_shadow_snapshots(
        {"equity": 100000, "open_positions": 1, "symbols": ["BTCUSDT"]},
        {
            "equity": 100250,
            "open_positions": 2,
            "symbols": ["BTCUSDT", "ETHUSDT"],
            "pending_orders": 1,
            "fill_count_proxy": 2,
            "stop_count_proxy": 1,
            "bad_audits": 0,
        },
    )
    assert delta["equity_gap"] == 250.0
    assert delta["open_count_gap"] == 1
    assert delta["execution_only_symbols"] == ["ETHUSDT"]
    assert delta["fill_count"] == 2


def test_record_user_shadow_comparison_writes_file(tmp_path: Path, monkeypatch) -> None:
    import paper_execution.paths as pep

    user_root = tmp_path / "paper_users" / "u-shadow" / "crypto"
    user_root.mkdir(parents=True)
    (user_root / "paper_state.json").write_text(
        json.dumps(
            {
                "equity": 100300,
                "symbols": {
                    "BTCUSDT": {
                        "equity": 100300,
                        "open_position": {"symbol": "BTCUSDT", "strategy_id": "DS01", "direction": "long"},
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(pep, "PAPER_USERS_ROOT", tmp_path / "paper_users")
    monkeypatch.setattr("paper_execution.shadow.SHADOW_REPORTS_DIR", tmp_path / "_shadow")
    monkeypatch.setattr(
        "paper_execution.shadow.collect_scoped_snapshot",
        lambda **_: {
            "user_id": "u-shadow",
            "equity": 100000,
            "open_positions": 0,
            "symbols": [],
            "positions_preview": [],
        },
    )

    from paper_execution.shadow import load_user_shadow_report, record_user_shadow_comparison

    report = record_user_shadow_comparison(
        user_id="u-shadow",
        plan_id="pro",
        persist_ledger=False,
    )
    assert report["ok"] is True
    assert report["delta"]["equity_gap"] == 300.0
    assert report["execution"]["open_positions"] == 1
    saved = load_user_shadow_report("u-shadow")
    assert saved is not None
    assert saved["user_id"] == "u-shadow"


def test_build_user_paper_account_includes_shadow_comparison(tmp_path: Path, monkeypatch) -> None:
    import services.monitor_paper_account as mpa

    shadow_dir = tmp_path / "_shadow"
    shadow_dir.mkdir()
    (shadow_dir / "user1.json").write_text(
        json.dumps(
            {
                "user_id": "user1",
                "generated_at": "2026-06-16T00:00:00+00:00",
                "scoped": {"open_positions": 0},
                "execution": {"open_positions": 1},
                "delta": {"equity_gap": 120.0, "open_count_gap": 1, "fill_count": 1, "stop_count": 0, "bad_audits": 0},
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("FENGJI_PAPER_MODE", "shadow")
    monkeypatch.setattr(mpa, "PAPER_ACCOUNTS_DIR", tmp_path / "paper_accounts")
    monkeypatch.setattr(mpa, "_equity_from_paper_state", lambda keys: (100000.0, None, 0))
    monkeypatch.setattr(mpa, "load_latest_opens", lambda: {"source": "x", "positions": []})
    monkeypatch.setattr(mpa, "load_overseas_latest_opens", lambda: {"source": "x", "positions": []})
    monkeypatch.setattr(mpa, "_persist_pg_account", lambda **_: (None, []))
    monkeypatch.setattr("paper_execution.shadow.SHADOW_REPORTS_DIR", shadow_dir)

    payload = mpa.build_user_paper_account_summary(user_id="user1", plan_id="pro")
    assert payload["paper_mode_global"] == "shadow"
    assert payload["shadow_comparison"]["delta"]["equity_gap"] == 120.0
