#!/usr/bin/env python3
"""Register additional invalid fill order_ids into fill_supervision_acknowledged.json."""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ACK = ROOT / "runtime" / "fill_supervision_acknowledged.json"
DEFAULT_DISPOSITION = ROOT / "runtime" / "n04_rebuild_disposition.json"


def load_ack(path: Path) -> dict:
    if not path.exists():
        return {"note": "", "source": "", "acknowledged": []}
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description="Merge order_ids into fill supervision ack file.")
    parser.add_argument("--ack-file", default=str(DEFAULT_ACK))
    parser.add_argument("--disposition-file", default=str(DEFAULT_DISPOSITION))
    parser.add_argument("--order-id", action="append", default=[], help="Repeatable order_id to acknowledge.")
    parser.add_argument("--disposition", default="audit_invalid", choices=["audit_invalid", "equity_review"])
    parser.add_argument("--reason", default="", help="Human-readable reason for this registration batch.")
    parser.add_argument("--approved-by", default="user")
    args = parser.parse_args()

    order_ids = [str(x).strip() for x in args.order_id if str(x).strip()]
    if not order_ids:
        print("no --order-id provided", file=sys.stderr)
        return 1

    ack_path = Path(args.ack_file)
    ack = load_ack(ack_path)
    before = set(ack.get("acknowledged") or [])
    merged = sorted(before | set(order_ids))
    added = sorted(set(order_ids) - before)
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    ack.update(
        {
            "note": ack.get("note") or "fill supervision invalid 已登记；watchdog 仅对不在此列的新 invalid 告警",
            "source": ack.get("source") or "",
            "n04_rebuild_ack_applied_at": now,
            "n04_rebuild_ack_reason": args.reason or "N04 OS rebuild post-audit invalid registration",
            "acknowledged": merged,
        }
    )
    ack_path.parent.mkdir(parents=True, exist_ok=True)
    ack_path.write_text(json.dumps(ack, ensure_ascii=False, indent=2), encoding="utf-8")

    disposition_path = Path(args.disposition_file)
    disposition = {}
    if disposition_path.exists():
        disposition = json.loads(disposition_path.read_text(encoding="utf-8"))
    rows = list(disposition.get("rows") or [])
    for oid in added:
        rows.append(
            {
                "order_id": oid,
                "disposition": args.disposition,
                "reason": args.reason,
                "registered_at": now,
                "approved_by": args.approved_by,
            }
        )
    disposition_payload = {
        "applied_at": now,
        "approved_by": args.approved_by,
        "source": "scripts/register_fill_supervision_ack.py",
        "rows": rows,
        "audit_invalid": sorted({r["order_id"] for r in rows if r.get("disposition") == "audit_invalid"}),
        "equity_review": sorted({r["order_id"] for r in rows if r.get("disposition") == "equity_review"}),
    }
    disposition_path.write_text(json.dumps(disposition_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"ack_total={len(merged)} (+{len(added)} new) -> {ack_path}")
    print(f"disposition -> {disposition_path}")
    for oid in added:
        print(f"  + {oid} ({args.disposition})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
