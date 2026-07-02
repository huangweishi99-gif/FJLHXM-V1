"""Read-only OS state verification for post-rebuild smoke."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def load_state(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def hardened_tail(state: dict, *, start_prefix: str = "", limit: int = 6) -> list[tuple[str, str, float]]:
    nodes = state.get("hardened_nodes") or []
    out: list[tuple[str, str, float]] = []
    for node in nodes:
        t = str(node.get("bar_time", ""))[:10]
        if start_prefix and t < start_prefix:
            continue
        out.append((t, str(node.get("raw_type", "")), float(node.get("price", 0) or 0)))
    return out[-limit:]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--state-dir", default="runtime/fengji_os_state")
    parser.add_argument("--symbol", required=True, help="e.g. RB, IOUSDT")
    parser.add_argument("--timeframe", default="1d")
    parser.add_argument("--since", default="", help="Optional YYYY-MM prefix filter for hardened tail")
    args = parser.parse_args()

    path = Path(args.state_dir) / f"{args.symbol}_{args.timeframe}.json"
    if not path.exists():
        print(f"MISSING {path}")
        return 1
    state = load_state(path)
    camp = state.get("camp")
    camp_confirmed = state.get("camp_confirmed")
    aligned = camp == camp_confirmed
    print(f"symbol={args.symbol} tf={args.timeframe} camp={camp} camp_confirmed={camp_confirmed} aligned={aligned}")
    print(f"pending_turn={state.get('pending_turn')} processed_len={state.get('processed_len')}")
    tail = hardened_tail(state, start_prefix=args.since)
    for row in tail:
        print(f"  hardened {row[0]} {row[1]} @{row[2]}")
    return 0 if aligned else 2


if __name__ == "__main__":
    sys.exit(main())
