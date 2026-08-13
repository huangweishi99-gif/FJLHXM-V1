#!/usr/bin/env python3
"""Apply user-approved M5 B-zone disposition (33 DS01 audit_invalid + equity_review tags)."""
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DRAFT = ROOT / "runtime" / "m5_b_zone_disposition_draft.json"
OUT = ROOT / "runtime" / "m5_b_zone_disposition.json"
ACK_PATH = ROOT / "runtime" / "fill_supervision_acknowledged.json"

def main() -> int:
    if not DRAFT.exists():
        print(f"missing {DRAFT}", file=sys.stderr)
        return 1
    draft = json.loads(DRAFT.read_text(encoding="utf-8"))
    audit_ids = list(draft.get("audit_invalid") or [])
    equity_ids = list(draft.get("equity_review") or [])
    all_ids = sorted(set(audit_ids) | set(equity_ids))
    if len(all_ids) != 33:
        print(f"expected 33 B-zone order_ids, got {len(all_ids)}", file=sys.stderr)
        return 1

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    by_profile: dict[str, list[str]] = {"domestic": [], "overseas": [], "unknown": []}
    for row in draft.get("rows") or []:
        oid = str(row.get("order_id") or "")
        prof = str(row.get("profile") or "unknown")
        if oid and prof in by_profile:
            by_profile[prof].append(oid)
    for key in by_profile:
        by_profile[key] = sorted(set(by_profile[key]))

    disposition = {
        "applied_at": now,
        "status": "approved",
        "approved_by": "user",
        "disposition": "audit_invalid",
        "audit_invalid_count": len(audit_ids),
        "equity_review_count": len(equity_ids),
        "order_ids": all_ids,
        "audit_invalid": audit_ids,
        "equity_review": equity_ids,
        "by_profile": by_profile,
        "repair_reason": "M5 B zone DS01 audit_invalid user approved 2026-06-10",
        "equity_note": "equity_review 5笔仅 dry-run 估算，不回滚权益",
    }
    OUT.write_text(json.dumps(disposition, ensure_ascii=False, indent=2), encoding="utf-8")

    ack = json.loads(ACK_PATH.read_text(encoding="utf-8")) if ACK_PATH.exists() else {}
    merged = sorted(set(ack.get("acknowledged") or []) | set(all_ids))
    ack.update(
        {
            "m5_b_zone_applied_at": now,
            "m5_b_zone_disposition": "audit_invalid",
            "m5_b_zone_equity_review": equity_ids,
            "acknowledged": merged,
        }
    )
    ACK_PATH.write_text(json.dumps(ack, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"disposition -> {OUT}")
    print(f"ack_total={len(merged)} domestic={len(by_profile['domestic'])} overseas={len(by_profile['overseas'])}")
    print(f"audit_invalid={len(audit_ids)} equity_review={len(equity_ids)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
