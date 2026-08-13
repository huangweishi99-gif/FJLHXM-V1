#!/usr/bin/env python3
"""Summarize actionable pending orders after applying execution state.

Radar and pending-order snapshots can continue to show a setup after the
execution monitor has already filled or cancelled the order. This utility keeps
that distinction explicit by adding an effective_status column.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


ACTIONABLE_RAW_STATUSES = {"ACTIVE", "READY_TRIGGERED"}
FILL_REVIEW_STATUSES = {"filled", "filled_open"}


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return default


def normalize_symbol(symbol: str) -> str:
    return str(symbol or "").strip().upper()


def setup_key(order: dict[str, Any]) -> str:
    return str(order.get("setup_key") or order.get("semantic_key") or "").strip()


def load_orders(path: Path) -> list[dict[str, Any]]:
    payload = load_json(path, [])
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        for key in ("orders", "pending_orders", "active_orders"):
            value = payload.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
            if isinstance(value, dict):
                return [item for item in value.values() if isinstance(item, dict)]
    return []


def active_paper_positions(paper_state: dict[str, Any]) -> tuple[set[str], set[str], dict[str, int]]:
    order_ids: set[str] = set()
    setup_keys: set[str] = set()
    symbol_counts: dict[str, int] = {}
    for symbol, symbol_state in (paper_state.get("symbols") or {}).items():
        if not isinstance(symbol_state, dict):
            continue
        clean = normalize_symbol(symbol)
        for position in symbol_state.get("open_positions") or []:
            if not isinstance(position, dict) or position.get("closed"):
                continue
            symbol_counts[clean] = symbol_counts.get(clean, 0) + 1
            order_id = str(position.get("order_id") or "").strip()
            if order_id:
                order_ids.add(order_id)
            key = str(position.get("setup_key") or "").strip()
            if key:
                setup_keys.add(key)
    return order_ids, setup_keys, symbol_counts


def classify_order(
    order: dict[str, Any],
    *,
    filled_ids: set[str],
    cancelled_ids: set[str],
    filled_setup_keys: set[str],
    cancelled_setup_keys: set[str],
    open_order_ids: set[str],
    open_setup_keys: set[str],
) -> tuple[str, bool, str]:
    order_id = str(order.get("order_id") or "").strip()
    key = setup_key(order)
    raw_status = str(order.get("status") or "").strip().upper()

    if order_id in open_order_ids or (key and key in open_setup_keys):
        return "filled_open", False, "paper_state has an active open position"
    if order_id in cancelled_ids or (key and key in cancelled_setup_keys):
        return "cancelled", False, "execution state cancelled this order"
    if order_id in filled_ids or (key and key in filled_setup_keys):
        return "filled", False, "execution state already filled this order"
    if raw_status in ACTIONABLE_RAW_STATUSES:
        return raw_status.lower(), True, "actionable"
    if raw_status:
        return raw_status.lower(), False, "raw status is not actionable"
    return "unknown", False, "missing raw status"


def summarize(
    orders: list[dict[str, Any]],
    state: dict[str, Any],
    paper_state: dict[str, Any],
    *,
    symbol_filter: str = "",
) -> dict[str, Any]:
    filled_ids = {str(item) for item in state.get("filled_order_ids", [])}
    cancelled_ids = {str(item) for item in state.get("cancelled_order_ids", [])}
    filled_setup_keys = {str(item) for item in state.get("filled_setup_keys", [])}
    cancelled_setup_keys = {str(item) for item in state.get("cancelled_setup_keys", [])}
    open_order_ids, open_setup_keys, open_position_counts = active_paper_positions(paper_state)

    clean_filter = normalize_symbol(symbol_filter)
    rows: list[dict[str, Any]] = []
    for order in orders:
        symbol = normalize_symbol(str(order.get("symbol") or ""))
        if clean_filter and symbol != clean_filter:
            continue
        effective_status, actionable, note = classify_order(
            order,
            filled_ids=filled_ids,
            cancelled_ids=cancelled_ids,
            filled_setup_keys=filled_setup_keys,
            cancelled_setup_keys=cancelled_setup_keys,
            open_order_ids=open_order_ids,
            open_setup_keys=open_setup_keys,
        )
        rows.append(
            {
                "symbol": symbol,
                "strategy_id": str(order.get("strategy_id") or "").upper(),
                "timeframe": order.get("timeframe", ""),
                "side": str(order.get("side") or "").lower(),
                "raw_status": str(order.get("status") or "").upper(),
                "effective_status": effective_status,
                "actionable": actionable,
                "trigger_price": order.get("trigger_price"),
                "stop_price": order.get("stop_price"),
                "current_price": order.get("current_price"),
                "latest_time": order.get("latest_time", ""),
                "created_at": order.get("created_at", ""),
                "valid_until": order.get("valid_until", ""),
                "order_id": order.get("order_id", ""),
                "setup_key": setup_key(order),
                "note": note,
            }
        )

    counts: dict[str, int] = {}
    for row in rows:
        status = str(row["effective_status"])
        counts[status] = counts.get(status, 0) + 1
    return {
        "total_orders": len(rows),
        "actionable_orders": sum(1 for row in rows if row["actionable"]),
        "review_candidate_orders": sum(1 for row in rows if row["effective_status"] in FILL_REVIEW_STATUSES),
        "effective_status_counts": counts,
        "open_position_counts": open_position_counts,
        "rows": rows,
    }


def render_table(rows: list[dict[str, Any]]) -> str:
    columns = [
        ("symbol", 10),
        ("strategy_id", 10),
        ("side", 6),
        ("raw_status", 16),
        ("effective_status", 18),
        ("actionable", 10),
        ("trigger_price", 13),
        ("current_price", 13),
        ("order_id", 28),
    ]
    header = " ".join(name.ljust(width) for name, width in columns)
    lines = [header, "-" * len(header)]
    for row in rows:
        parts = []
        for name, width in columns:
            value = row.get(name, "")
            text = str(value)
            if len(text) > width:
                text = text[: max(0, width - 1)] + "~"
            parts.append(text.ljust(width))
        lines.append(" ".join(parts))
    return "\n".join(lines)


def default_event_files(state_file: str) -> list[str]:
    return [str(Path(state_file).parent / "events.jsonl")]


def build_sandbox_review_command(args: argparse.Namespace) -> list[str]:
    script = Path(__file__).resolve().with_name("generate_fill_sandbox_review.py")
    event_files = list(args.event_file or default_event_files(args.state_file))
    command = [
        sys.executable,
        str(script),
        "--orders-file",
        str(args.orders_file),
        "--state-file",
        str(args.state_file),
        "--paper-state-file",
        str(args.paper_state_file),
        "--data-dir",
        str(args.data_dir),
        "--os-state-dir",
        str(args.os_state_dir),
        "--out-dir",
        str(args.review_out_dir),
        "--limit",
        str(args.review_limit),
        "--event-tail-lines",
        str(args.event_tail_lines),
    ]
    for event_file in event_files:
        command.extend(["--event-file", str(event_file)])
    if args.symbol:
        command.extend(["--symbol", str(args.symbol)])
    if args.sandbox_review_execute:
        command.extend(["--execute", "--timeout", str(args.review_timeout)])
    return command


def run_sandbox_review(args: argparse.Namespace) -> int:
    command = build_sandbox_review_command(args)
    result = subprocess.run(command, text=True, capture_output=True)
    if result.stdout.strip():
        print(result.stdout.strip())
    if result.stderr.strip():
        print(result.stderr.strip(), file=sys.stderr)
    return result.returncode


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Summarize effective pending-order status.")
    parser.add_argument("--orders-file", default="runtime/fengji_pending_orders/pending_orders.json")
    parser.add_argument("--state-file", default="runtime/fengji_pending_orders/futures_pending_state.json")
    parser.add_argument("--paper-state-file", default="runtime/fengji_futures/state_futures_v2.json")
    parser.add_argument("--symbol", default="")
    parser.add_argument("--json", action="store_true", help="print JSON instead of a compact table")
    parser.add_argument("--actionable-only", action="store_true")
    parser.add_argument("--include-shadow", action="store_true", help="include filled/cancelled shadow rows in text output")
    parser.add_argument("--sandbox-review", action="store_true", help="also build the post-fill sandbox review pack when filled rows exist")
    parser.add_argument("--sandbox-review-execute", action="store_true", help="with --sandbox-review, run supported plotters instead of only writing the review manifest")
    parser.add_argument("--event-file", action="append", default=[], help="pending monitor events JSONL for sandbox review; repeatable")
    parser.add_argument("--data-dir", default="data")
    parser.add_argument("--os-state-dir", default="runtime/fengji_os_state")
    parser.add_argument("--review-out-dir", default="runtime/fill_sandbox_review")
    parser.add_argument("--review-limit", type=int, default=20)
    parser.add_argument("--event-tail-lines", type=int, default=20000)
    parser.add_argument("--review-timeout", type=int, default=120)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    payload = summarize(
        load_orders(Path(args.orders_file)),
        load_json(Path(args.state_file), {}),
        load_json(Path(args.paper_state_file), {}),
        symbol_filter=args.symbol,
    )
    rows = payload["rows"]
    if args.actionable_only:
        rows = [row for row in rows if row["actionable"]]
    if not args.include_shadow and not args.actionable_only:
        rows = [row for row in rows if row["actionable"] or row["effective_status"] not in {"filled", "filled_open", "cancelled"}]

    if args.json:
        print(json.dumps({**payload, "rows": rows}, ensure_ascii=False, indent=2))
    else:
        print(
            "effective pending summary: "
            f"total={payload['total_orders']} actionable={payload['actionable_orders']} "
            f"review_candidates={payload['review_candidate_orders']} "
            f"counts={payload['effective_status_counts']}"
        )
        if rows:
            print(render_table(rows))
        else:
            print("no rows")
    if args.sandbox_review:
        if int(payload["review_candidate_orders"]) <= 0:
            print("sandbox review: no filled or filled_open candidates")
        else:
            return run_sandbox_review(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
