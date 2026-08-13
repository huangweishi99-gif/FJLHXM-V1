#!/usr/bin/env python3
"""Run one per-user CRYPTO pending monitor cycle (V1.1 independent paper, Phase 1)."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for rel in ("services", "packages/fengji_core", "src"):
    p = str(ROOT / rel)
    if p not in sys.path:
        sys.path.insert(0, p)

from paper_execution.paths import UserPaperPaths  # noqa: E402
from paper_execution.runner import load_user_open_positions, run_user_paper_monitor_once  # noqa: E402
from paper_execution.watchlist import execution_allowed_for_plan  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Per-user CRYPTO monitor --once (V1.1 Phase 1)")
    parser.add_argument("--user-id", required=True)
    parser.add_argument("--plan-id", default="standard")
    parser.add_argument("--root-dir", default="")
    parser.add_argument("--price-file", default="", help="Optional price snapshot for tests")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not execution_allowed_for_plan(args.plan_id):
        print(json.dumps({"ok": False, "error": "plan_not_eligible", "plan_id": args.plan_id}, ensure_ascii=False))
        return 2

    root = Path(args.root_dir) if args.root_dir else None
    paths = UserPaperPaths(user_id=args.user_id, root_dir=root) if root else UserPaperPaths(user_id=args.user_id)
    result = run_user_paper_monitor_once(
        paths,
        price_file=args.price_file,
        dry_run=args.dry_run,
    )
    positions = load_user_open_positions(paths) if result.ok and not args.dry_run else []
    report = {
        "ok": result.ok,
        "user_id": args.user_id,
        "paper_state": str(paths.paper_state_json),
        "open_positions": len(positions),
        "step": result.step,
        "returncode": result.returncode,
        "stderr_tail": result.stderr_tail,
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
