#!/usr/bin/env python3
"""Audit paper execution money defaults and ledger fields."""
from __future__ import annotations

import ast
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CRYPTO_MONITOR = ROOT / "src" / "fengji_pending_order_monitor.py"
FUTURES_MONITOR = ROOT / "src" / "fengji_futures_pending_order_monitor.py"

CRYPTO_DEFAULTS = {
    "--initial-cash": 1000.0,
    "--margin-per-trade": 200.0,
    "--leverage": 2.0,
    "--fee-rate": 0.0005,
    "--slippage-rate": 0.0003,
}
FUTURES_DEFAULTS = {
    "--lots": 1,
    "--fee-rate": 0.0001,
    "--slippage-rate": 0.0002,
}

CRYPTO_OPEN_FIELDS = {
    "source",
    "trade_key",
    "order_id",
    "symbol",
    "strategy_id",
    "side",
    "direction",
    "entry_time",
    "entry_price",
    "initial_stop",
    "current_stop",
    "units",
    "entries",
    "legs",
    "margin",
    "leverage",
    "notional",
    "virtual_initial_cash",
}
CRYPTO_CLOSE_FIELDS = {
    "closed_at",
    "source",
    "symbol",
    "strategy_id",
    "direction",
    "side",
    "entry_time",
    "exit_time",
    "entry_price",
    "exit_price",
    "initial_stop",
    "exit_reason",
    "entries",
    "margin",
    "leverage",
    "notional",
    "gross_pnl",
    "costs",
    "net_pnl",
    "return_on_symbol_cash",
    "equity_after",
    "order_id",
}
FUTURES_OPEN_FIELDS = {
    "key",
    "source",
    "order_id",
    "setup_key",
    "symbol",
    "strategy_id",
    "side",
    "direction",
    "entry_time",
    "entry_price",
    "trigger_price",
    "initial_stop",
    "current_stop",
    "stop_price",
    "lots",
    "multiplier",
    "created_at",
    "entry_bar",
    "risk_rule",
    "timeframe",
    "setup",
}
FUTURES_TRADE_FIELDS = {
    "event_time",
    "symbol",
    "strategy_id",
    "side",
    "action",
    "lots",
    "entry_time",
    "entry_price",
    "exit_time",
    "exit_price",
    "net_pnl",
    "equity",
    "reason",
    "trade_key",
    "run_id",
}
FUTURES_CLOSE_EXTRA_FIELDS = {"gross_pnl", "costs"}


@dataclass(frozen=True)
class CheckResult:
    name: str
    ok: bool
    detail: str

    def as_dict(self) -> dict[str, Any]:
        return {"name": self.name, "ok": self.ok, "detail": self.detail}


def parse_tree(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def literal_default(node: ast.AST) -> Any:
    try:
        return ast.literal_eval(node)
    except Exception:
        return None


def argparse_defaults(path: Path) -> dict[str, Any]:
    defaults: dict[str, Any] = {}
    for node in ast.walk(parse_tree(path)):
        if not isinstance(node, ast.Call):
            continue
        if not isinstance(node.func, ast.Attribute) or node.func.attr != "add_argument":
            continue
        if not node.args or not isinstance(node.args[0], ast.Constant) or not isinstance(node.args[0].value, str):
            continue
        option = str(node.args[0].value)
        for keyword in node.keywords:
            if keyword.arg == "default":
                defaults[option] = literal_default(keyword.value)
                break
    return defaults


def function_nodes(path: Path, function_name: str) -> list[ast.AST]:
    tree = parse_tree(path)
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == function_name:
            return list(ast.walk(node))
    raise ValueError(f"function not found: {path}:{function_name}")


def string_dict_keys(path: Path, function_name: str) -> set[str]:
    keys: set[str] = set()
    for node in function_nodes(path, function_name):
        if not isinstance(node, ast.Dict):
            continue
        for key in node.keys:
            if isinstance(key, ast.Constant) and isinstance(key.value, str):
                keys.add(key.value)
    return keys


def subset_check(name: str, expected: set[str], actual: set[str]) -> CheckResult:
    missing = sorted(expected - actual)
    return CheckResult(name, not missing, "missing=" + ",".join(missing) if missing else "ok")


def defaults_check(name: str, expected: dict[str, Any], actual: dict[str, Any]) -> CheckResult:
    mismatches = []
    for key, value in expected.items():
        if actual.get(key) != value:
            mismatches.append(f"{key}:{actual.get(key)!r}!={value!r}")
    return CheckResult(name, not mismatches, ";".join(mismatches) if mismatches else "ok")


def run_checks() -> list[CheckResult]:
    crypto_defaults = argparse_defaults(CRYPTO_MONITOR)
    futures_defaults = argparse_defaults(FUTURES_MONITOR)
    crypto_open = string_dict_keys(CRYPTO_MONITOR, "update_paper_state_on_fill")
    crypto_close = string_dict_keys(CRYPTO_MONITOR, "close_position_on_stop")
    futures_open = string_dict_keys(FUTURES_MONITOR, "update_paper_state_on_fill")
    futures_open_trade = string_dict_keys(FUTURES_MONITOR, "append_open_trade")
    futures_close = string_dict_keys(FUTURES_MONITOR, "close_position_on_stop")
    return [
        defaults_check("crypto_money_defaults", CRYPTO_DEFAULTS, crypto_defaults),
        defaults_check("futures_money_defaults", FUTURES_DEFAULTS, futures_defaults),
        subset_check("crypto_open_position_fields", CRYPTO_OPEN_FIELDS, crypto_open),
        subset_check("crypto_close_record_fields", CRYPTO_CLOSE_FIELDS, crypto_close),
        subset_check("futures_open_position_fields", FUTURES_OPEN_FIELDS, futures_open),
        subset_check("futures_open_trade_fields", FUTURES_TRADE_FIELDS, futures_open_trade),
        subset_check(
            "futures_close_trade_fields",
            FUTURES_TRADE_FIELDS | FUTURES_CLOSE_EXTRA_FIELDS,
            futures_close,
        ),
    ]


def main() -> int:
    checks = run_checks()
    failures = [check for check in checks if not check.ok]
    payload = {
        "checks": [check.as_dict() for check in checks],
        "failures": len(failures),
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
