#!/usr/bin/env python3
"""Run per-user CRYPTO radar + pending for V1.1 independent paper execution (Phase 1)."""
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
from paper_execution.runner import (  # noqa: E402
    resolve_user_symbols,
    run_user_paper_pending_once,
    run_user_paper_radar_once,
)
from paper_execution.watchlist import execution_allowed_for_plan  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Per-user CRYPTO radar→pending (V1.1 Phase 1)")
    parser.add_argument("--user-id", required=True)
    parser.add_argument("--plan-id", default="standard", help="standard|pro required for execution")
    parser.add_argument("--symbols", default="", help="Override comma list; default PG watchlist")
    parser.add_argument("--local-symbols", default="", help="Extra comma symbols (e.g. localStorage watchlist)")
    parser.add_argument("--root-dir", default="", help="Override runtime/paper_users root (tests)")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--skip-pending", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not execution_allowed_for_plan(args.plan_id):
        print(json.dumps({"ok": False, "error": "plan_not_eligible", "plan_id": args.plan_id}, ensure_ascii=False))
        return 2

    symbols = resolve_user_symbols(
        args.user_id,
        symbols=[s.strip() for s in args.symbols.split(",") if s.strip()] or None,
        local_symbols=[s.strip() for s in args.local_symbols.split(",") if s.strip()] or None,
    )
    root = Path(args.root_dir) if args.root_dir else None
    paths = UserPaperPaths(user_id=args.user_id, root_dir=root) if root else UserPaperPaths(user_id=args.user_id)
    paths.touch_meta(plan_id=args.plan_id, symbols=symbols)

    if not symbols:
        print(json.dumps({"ok": False, "error": "no_symbols", "user_id": args.user_id}, ensure_ascii=False))
        return 1

    radar = run_user_paper_radar_once(paths, symbols, dry_run=args.dry_run)
    pending = None
    if radar.ok and not args.skip_pending:
        pending = run_user_paper_pending_once(paths, dry_run=args.dry_run)

    ok = radar.ok and (pending is None or pending.ok)
    report = {
        "ok": ok,
        "user_id": args.user_id,
        "symbols": symbols,
        "radar_dir": str(paths.radar_dir),
        "pending_dir": str(paths.pending_dir),
        "steps": [
            {"step": radar.step, "ok": radar.ok, "returncode": radar.returncode},
            *(
                [{"step": pending.step, "ok": pending.ok, "returncode": pending.returncode}]
                if pending
                else []
            ),
        ],
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
