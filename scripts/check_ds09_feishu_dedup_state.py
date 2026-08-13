#!/usr/bin/env python3
"""Check DS09 pending Feishu dedup state (semantic keys vs legacy order_id spam)."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def load_pending_orders(path: Path) -> list[dict]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(raw, list):
        return raw
    return list(raw.get("orders", []))


def check_state(state: dict, orders: list[dict], *, symbol: str = "TRUMPUSDT") -> dict:
    symbol = symbol.upper()
    active = [
        o
        for o in orders
        if str(o.get("symbol", "")).upper() == symbol
        and str(o.get("strategy_id", "")).upper() == "DS09"
        and str(o.get("status", "")).upper() in {"ACTIVE", "READY_TRIGGERED"}
    ]
    legacy_ids = [
        x
        for x in state.get("notified_pending_order_ids", [])
        if symbol in str(x) and "DS09" in str(x)
    ]
    semantic = [
        k
        for k in state.get("notified_pending_semantic_keys", [])
        if symbol in str(k) and "DS09" in str(k)
    ]
    issues: list[str] = []
    if len(legacy_ids) >= 2 and not semantic:
        issues.append("legacy_order_id_spam_without_semantic_key")
    if active and semantic:
        issues.append("ok_active_with_semantic")
    if not active and semantic:
        issues.append("ok_inactive_semantic_retained")
    if not active and not semantic and len(legacy_ids) >= 2:
        issues.append("needs_semantic_bootstrap")
    return {
        "symbol": symbol,
        "trump_active_ds09": len(active),
        "legacy_notified_order_ids": len(legacy_ids),
        "semantic_keys": semantic,
        "semantic_keys_total": len(state.get("notified_pending_semantic_keys", [])),
        "status": "ok" if not issues or issues[0].startswith("ok_") else "warn",
        "issues": issues,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--state-file", default="runtime/fengji_pending_orders/state.json")
    parser.add_argument("--orders-file", default="runtime/fengji_pending_orders/pending_orders.json")
    parser.add_argument("--symbol", default="TRUMPUSDT")
    parser.add_argument("--fail-on-warn", action="store_true")
    args = parser.parse_args()
    root = args.root.resolve()
    state_path = (root / args.state_file).resolve()
    orders_path = (root / args.orders_file).resolve()
    if not state_path.is_file():
        print(json.dumps({"error": f"missing state: {state_path}"}, ensure_ascii=False))
        return 2
    if not orders_path.is_file():
        print(json.dumps({"error": f"missing orders: {orders_path}"}, ensure_ascii=False))
        return 2
    result = check_state(
        json.loads(state_path.read_text(encoding="utf-8")),
        load_pending_orders(orders_path),
        symbol=args.symbol,
    )
    print(json.dumps(result, ensure_ascii=False))
    if args.fail_on_warn and result.get("status") != "ok":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
