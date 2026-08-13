#!/usr/bin/env python3
"""Batch job: per-user CRYPTO paper execution for standard/pro watchlist users."""
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

from paper_execution.job import run_execution_job  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="V1.1 per-user CRYPTO paper execution batch job")
    parser.add_argument("--user-id", default="", help="Run single user only")
    parser.add_argument("--force", action="store_true", help="Ignore plan polling interval")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--limit-users", type=int, default=50)
    parser.add_argument("--job-state", default="", help="Override job state JSON path")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    state_path = Path(args.job_state) if args.job_state else None
    report = run_execution_job(
        user_id=args.user_id.strip() or None,
        force=args.force,
        dry_run=args.dry_run,
        limit_users=args.limit_users,
        job_state_path=state_path,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
