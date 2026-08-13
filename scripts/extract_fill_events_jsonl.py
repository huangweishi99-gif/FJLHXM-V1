#!/usr/bin/env python3
"""Stream fill rows from events.jsonl (optionally filtered by age). Used for overseas SSH sync."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PKG = ROOT / "packages" / "fengji_core"
if str(PKG) not in sys.path:
    sys.path.insert(0, str(PKG))

from fengji_core.fill_supervision import parse_events_jsonl  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Extract fill events from events.jsonl to stdout.")
    parser.add_argument(
        "--events",
        default=str(ROOT / "runtime/fengji_pending_orders/events.jsonl"),
        help="Source events.jsonl",
    )
    parser.add_argument(
        "--since-hours",
        type=float,
        default=168.0,
        help="Only emit fills within N hours (0=all)",
    )
    parser.add_argument(
        "--out",
        help="Optional output path; default stdout",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    since = None if args.since_hours <= 0 else args.since_hours
    fills = parse_events_jsonl(Path(args.events), since_hours=since)
    lines = []
    import json

    for row in fills:
        lines.append(json.dumps(row, ensure_ascii=False) + "\n")
    payload = "".join(lines)
    if args.out:
        Path(args.out).write_text(payload, encoding="utf-8")
    else:
        sys.stdout.write(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
