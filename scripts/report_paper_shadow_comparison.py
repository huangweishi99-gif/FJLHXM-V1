"""Print V1.1 Phase 4 shadow comparison reports for eligible users."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services"))
sys.path.insert(0, str(ROOT / "packages" / "fengji_core"))


def main() -> int:
    parser = argparse.ArgumentParser(description="List or refresh paper shadow comparison reports")
    parser.add_argument("--user-id", default="", help="Refresh one user then print report")
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--json", action="store_true", help="Print JSON only")
    args = parser.parse_args()

    from paper_execution.mode import paper_mode_summary, resolve_fengji_paper_mode
    from paper_execution.shadow import list_shadow_reports, load_user_shadow_report, record_user_shadow_comparison

    if args.user_id:
        report = record_user_shadow_comparison(user_id=args.user_id.strip())
        if args.json:
            print(json.dumps(report, ensure_ascii=False, indent=2))
        else:
            delta = report.get("delta") or {}
            print(f"user={args.user_id} equity_gap={delta.get('equity_gap')} open_gap={delta.get('open_count_gap')}")
        return 0 if report.get("ok") else 1

    rows = list_shadow_reports(limit=args.limit)
    payload = {
        "fengji_paper_mode": resolve_fengji_paper_mode(),
        "paper_mode_config": paper_mode_summary(),
        "count": len(rows),
        "items": rows,
    }
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0

    print(f"FENGJI_PAPER_MODE={payload['fengji_paper_mode']}")
    for row in rows:
        print(
            f"{row.get('user_id')} gap={row.get('equity_gap')} "
            f"open_gap={row.get('open_count_gap')} fills={row.get('fill_count')} "
            f"stops={row.get('stop_count')} bad={row.get('bad_audits')}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
