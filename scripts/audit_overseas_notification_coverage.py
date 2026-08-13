#!/usr/bin/env python3
"""Audit overseas crypto DS coverage and Feishu notification wording.

This is a read-only operational audit. It checks the static entry-point contract
for overseas DS01-DS09 coverage, samples current runtime files when present, and
smoke-tests the shared Feishu notification wording.
"""
from __future__ import annotations

import argparse
import ast
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]


def prepend_import_path(path: Path) -> None:
    value = str(path)
    while value in sys.path:
        sys.path.remove(value)
    sys.path.insert(0, value)


for extra in (ROOT, ROOT / "packages" / "fengji_core", ROOT / "src"):
    prepend_import_path(extra)

from fengji_core.feishu_trade_notify import format_close_done, format_fill_done, format_pending_expected
from fengji_pending_orders import DEFAULT_INCLUDE_STRATEGIES
from scripts.summarize_pending_effective_status import load_json, load_orders, summarize


EXPECTED_DS = {f"DS{idx:02d}" for idx in range(1, 10)}


@dataclass(frozen=True)
class CheckResult:
    name: str
    ok: bool
    detail: str

    def as_dict(self) -> dict[str, Any]:
        return {"name": self.name, "ok": self.ok, "detail": self.detail}


def _literal_assigned_set(tree: ast.Module, name: str) -> set[str]:
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        if not any(isinstance(target, ast.Name) and target.id == name for target in node.targets):
            continue
        value = ast.literal_eval(node.value)
        if isinstance(value, (list, set, tuple)):
            return {str(item).upper() for item in value}
    return set()


def overseas_direct_open_strategies(path: Path = ROOT / "src" / "overseas_paper_monitor.py") -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    total = _literal_assigned_set(tree, "TOTAL_PATTERN_STRATEGIES")
    pending_managed = _literal_assigned_set(tree, "PENDING_MANAGED_STRATEGIES")
    return total - pending_managed


def check_static_ds_coverage() -> CheckResult:
    pending = {str(item).upper() for item in DEFAULT_INCLUDE_STRATEGIES}
    direct = overseas_direct_open_strategies()
    covered = pending | direct
    missing = sorted(EXPECTED_DS - covered)
    detail = (
        f"pending={sorted(pending)} direct_open={sorted(direct)} "
        f"covered={sorted(covered)} missing={missing}"
    )
    return CheckResult("overseas_ds01_ds09_entry_coverage", not missing, detail)


def check_notification_wording() -> CheckResult:
    pending_long = format_pending_expected(
        {
            "symbol": "BTCUSDT",
            "strategy_id": "DS01",
            "timeframe": "D1",
            "side": "long",
            "trigger_price": 100.0,
            "stop_price": 95.0,
            "current_price": 99.0,
            "distance_pct": 0.01,
            "os_camp": "red",
            "setup": "smoke",
            "valid_until": "2026-07-10 23:59:59",
        },
        symbol_label="BTC(BTCUSDT)",
        now="2026-07-10 10:00:00",
    )
    fill_long = format_fill_done(
        {
            "symbol": "BTCUSDT",
            "strategy_id": "DS01",
            "timeframe": "D1",
            "side": "long",
            "trigger_price": 100.0,
            "stop_price": 95.0,
            "setup": "smoke",
        },
        100.0,
        symbol_label="BTC(BTCUSDT)",
        now="2026-07-10 10:00:00",
    )
    fill_short = format_fill_done(
        {
            "symbol": "ETHUSDT",
            "strategy_id": "DS03",
            "timeframe": "D1",
            "side": "short",
            "trigger_price": 2500.0,
            "stop_price": 2600.0,
            "setup": "smoke",
        },
        2498.0,
        symbol_label="ETH(ETHUSDT)",
        now="2026-07-10 10:00:00",
    )
    close_long = format_close_done(
        {"strategy_id": "DS01", "side": 1, "entry_time": "2026-07-10", "entry_price": 100.0, "initial_stop": 95.0},
        95.0,
        {"net_pnl": -10.0, "unit": "USDT"},
        symbol_label="BTC(BTCUSDT)",
        now="2026-07-10 11:00:00",
    )
    close_short = format_close_done(
        {"strategy_id": "DS03", "side": -1, "entry_time": "2026-07-10", "entry_price": 100.0, "initial_stop": 105.0},
        105.0,
        {"net_pnl": -10.0, "unit": "USDT"},
        symbol_label="ETH(ETHUSDT)",
        now="2026-07-10 11:00:00",
    )
    required = {
        "pending_has_already_ordered": "状态: 已挂单" in pending_long and "消息类型: 已挂单 +" in pending_long,
        "long_fill_has_bought": "状态: 已买入" in fill_long and "消息类型: 已买入 +" in fill_long,
        "short_fill_has_sold": "状态: 已卖出" in fill_short and "消息类型: 已卖出 +" in fill_short,
        "long_close_has_sell_close": "状态: 已卖出平仓" in close_long,
        "short_close_has_buy_close": "状态: 已买入平仓" in close_short,
    }
    failed = [name for name, ok in required.items() if not ok]
    return CheckResult("overseas_feishu_status_wording", not failed, "ok" if not failed else f"failed={failed}")


def strategy_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        strategy = str(row.get("strategy_id") or row.get("strategy") or "").upper()
        if not strategy:
            continue
        counts[strategy] = counts.get(strategy, 0) + 1
    return dict(sorted(counts.items()))


def paper_open_counts(paper_state: dict[str, Any]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for symbol_state in (paper_state.get("symbols") or {}).values():
        if not isinstance(symbol_state, dict):
            continue
        candidates = []
        open_position = symbol_state.get("open_position")
        if isinstance(open_position, dict) and not open_position.get("closed"):
            candidates.append(open_position)
        for position in symbol_state.get("open_positions") or []:
            if isinstance(position, dict) and not position.get("closed"):
                candidates.append(position)
        for position in candidates:
            strategy = str(position.get("strategy_id") or "").upper()
            if strategy:
                counts[strategy] = counts.get(strategy, 0) + 1
    return dict(sorted(counts.items()))


def runtime_snapshot(root: Path, *, orders_file: str, state_file: str, paper_state_file: str, radar_file: str) -> dict[str, Any]:
    orders_path = root / orders_file
    state_path = root / state_file
    paper_path = root / paper_state_file
    radar_path = root / radar_file

    orders = load_orders(orders_path)
    state = load_json(state_path, {})
    paper_state = load_json(paper_path, {})
    radar_payload = load_json(radar_path, [])
    radar_rows = radar_payload if isinstance(radar_payload, list) else []
    summary = summarize(orders, state, paper_state) if orders_path.exists() else {}
    return {
        "available": {
            "orders": orders_path.exists(),
            "state": state_path.exists(),
            "paper_state": paper_path.exists(),
            "radar": radar_path.exists(),
        },
        "radar_strategy_counts": strategy_counts([row for row in radar_rows if isinstance(row, dict)]),
        "pending_strategy_counts": strategy_counts(orders),
        "effective_status_counts": summary.get("effective_status_counts", {}),
        "actionable_orders": summary.get("actionable_orders", 0),
        "review_candidate_orders": summary.get("review_candidate_orders", 0),
        "paper_open_strategy_counts": paper_open_counts(paper_state),
    }


def run_checks() -> list[CheckResult]:
    return [check_static_ds_coverage(), check_notification_wording()]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit overseas DS coverage and Feishu notification wording.")
    parser.add_argument("--root", default=".")
    parser.add_argument("--orders-file", default="runtime/fengji_pending_orders/pending_orders.json")
    parser.add_argument("--state-file", default="runtime/fengji_pending_orders/state.json")
    parser.add_argument("--paper-state-file", default="runtime/fengji_paper/state.json")
    parser.add_argument("--radar-file", default="runtime/fengji_radar/radar.json")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    checks = run_checks()
    failures = [check for check in checks if not check.ok]
    payload = {
        "checks": [check.as_dict() for check in checks],
        "failures": len(failures),
        "runtime": runtime_snapshot(
            Path(args.root),
            orders_file=args.orders_file,
            state_file=args.state_file,
            paper_state_file=args.paper_state_file,
            radar_file=args.radar_file,
        ),
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
