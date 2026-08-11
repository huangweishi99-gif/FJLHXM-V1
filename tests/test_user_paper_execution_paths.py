from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

from services.paper_execution.paths import UserPaperPaths, safe_user_id
from services.paper_execution.runner import resolve_user_symbols, run_user_paper_pipeline
from services.paper_execution.watchlist import (
    execution_allowed_for_plan,
    load_user_crypto_symbols,
    normalize_crypto_symbol,
)


def test_safe_user_id_sanitizes() -> None:
    assert safe_user_id("user@example.com") == "user_example.com"
    assert safe_user_id("  ") == "anonymous"


def test_user_paper_paths_layout(tmp_path: Path) -> None:
    paths = UserPaperPaths(user_id="u1", root_dir=tmp_path / "paper_users")
    paths.ensure_dirs()
    assert paths.paper_state_json.parent == paths.base_dir
    assert paths.radar_json.parent == paths.radar_dir
    assert paths.is_outside_shared_runtime(paths.paper_state_json)
    assert not paths.is_outside_shared_runtime(tmp_path / "other" / "state.json")


def test_normalize_crypto_symbol() -> None:
    assert normalize_crypto_symbol("btc") == "BTCUSDT"
    assert normalize_crypto_symbol("ETH-USDT") == "ETHUSDT"


def test_load_user_crypto_symbols_from_rows() -> None:
    rows = [
        {"market": "CRYPTO", "symbol": "BTCUSDT", "status": "pending_runtime"},
        {"market": "FUTURES", "symbol": "RB", "status": "pending_runtime"},
        {"market": "CRYPTO", "symbol": "ETH", "status": "cancelled"},
    ]
    symbols = load_user_crypto_symbols("u1", watchlist_rows=rows, include_pg=False)
    assert "BTCUSDT" in symbols
    assert "RB" not in symbols
    assert "ETHUSDT" not in symbols


def test_execution_plan_gate() -> None:
    assert execution_allowed_for_plan("standard") is True
    assert execution_allowed_for_plan("pro") is True
    assert execution_allowed_for_plan("free") is False


def test_resolve_user_symbols_override() -> None:
    assert resolve_user_symbols("u1", symbols=["sol"]) == ["SOLUSDT"]


def test_user_fill_does_not_touch_shared_paper_state(tmp_path: Path) -> None:
    from fengji_pending_orders import convert_radar_rows, write_orders
    from fengji_pending_order_monitor import process_once

    shared_paper = tmp_path / "shared" / "fengji_paper" / "state.json"
    shared_paper.parent.mkdir(parents=True)
    shared_paper.write_text(json.dumps({"symbols": {}, "equity": 1000.0}), encoding="utf-8")

    user_root = tmp_path / "paper_users"
    paths = UserPaperPaths(user_id="test-user", root_dir=user_root)
    paths.ensure_dirs()

    orders = convert_radar_rows(
        [
            {
                "symbol": "RENDERUSDT",
                "strategy_id": "DS01",
                "timeframe": "D1",
                "side": "long",
                "status": "PENDING",
                "setup": "test",
                "current_price": 9.5,
                "trigger_price": 10.0,
                "stop_price": 8.0,
                "os_camp": "red",
                "latest_time": "2026-06-01",
                "distance_pct": 0.05,
                "priority": 1,
                "setup_key": "RENDERUSDT|DS01|test",
                "reason": "test",
            }
        ],
        include_strategies={"DS01"},
        include_triggered=False,
        max_distance_pct=0.08,
        created_at="2099-01-01 00:00:00",
    )
    write_orders(orders, paths.pending_dir)
    price_file = tmp_path / "prices.json"
    price_file.write_text(json.dumps({"RENDERUSDT": 10.01}), encoding="utf-8")

    args = argparse.Namespace(
        orders_file=str(paths.pending_orders_json),
        out_dir=str(paths.pending_dir),
        state_file=str(paths.monitor_state_json),
        paper_state_file=str(paths.paper_state_json),
        feishu_webhook="",
        price_file=str(price_file),
        max_ds01_entries=3,
        initial_cash=1000.0,
        margin_per_trade=200.0,
        leverage=2.0,
        fee_rate=0.0005,
        slippage_rate=0.0003,
        no_paper_state_update=False,
        data_dir="data",
        os_state_dir="runtime/fengji_os_state",
        notify_claims_dir=str(tmp_path / "claims"),
        timeout=8.0,
    )
    state = {"version": 1, "filled_order_ids": [], "cancelled_order_ids": [], "fills": []}
    summary = process_once(args, state)

    assert summary["filled"] == 1
    user_state = json.loads(paths.paper_state_json.read_text(encoding="utf-8"))
    shared_before = json.loads(shared_paper.read_text(encoding="utf-8"))
    assert user_state["symbols"]["RENDERUSDT"]["open_position"]["strategy_id"] == "DS01"
    assert shared_before == {"symbols": {}, "equity": 1000.0}


def test_pipeline_dry_run_free_plan_blocked() -> None:
    out = run_user_paper_pipeline(user_id="u1", plan_id="free", symbols=["BTCUSDT"], dry_run=True)
    assert out["ok"] is False
    assert out["error"] == "plan_not_eligible"


def test_pipeline_dry_run_standard(tmp_path: Path) -> None:
    out = run_user_paper_pipeline(
        user_id="u1",
        plan_id="standard",
        symbols=["BTCUSDT"],
        root_dir=tmp_path / "paper_users",
        dry_run=True,
    )
    assert out["ok"] is True
    assert out["symbols"] == ["BTCUSDT"]


def test_run_step_reports_timeout(monkeypatch) -> None:
    from services.paper_execution import runner

    def fake_run(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd=kwargs.get("args") or args[0], timeout=7)

    monkeypatch.setattr(runner.subprocess, "run", fake_run)

    result = runner._run_step(["python", "src/fake_step.py"], timeout_seconds=7)

    assert result.ok is False
    assert result.returncode == 124
    assert result.detail == {"error": "timeout", "timeout_seconds": 7}
