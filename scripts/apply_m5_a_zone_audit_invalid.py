#!/usr/bin/env python3
"""Apply user-approved M5 A-zone disposition: audit_invalid + ack registration."""
from __future__ import annotations

import json
import re
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REVIEW = ROOT / "results" / "fill_supervision_m5_review_2026-06-10.md"
ACK_PATH = ROOT / "runtime" / "fill_supervision_acknowledged.json"
DISPOSITION_PATH = ROOT / "runtime" / "m5_a_zone_disposition.json"
EMPTY_AUDIT = ROOT / "runtime" / "m5_empty_audit.json"

ORDER_ID_RE = re.compile(r"`([A-Z0-9_.-]+-DS03-[A-Z0-9]+-(?:long|short)-[0-9a-f]+)`")

DOMESTIC_PREFIXES = (
    "BRUSDT",
    "EBUSDT",
    "EGUSDT",
    "SHUSDT",
    "ECUSDT",
    "JDUSDT",
    "AGUSDT",
    "AUUSDT",
)

OVERSEAS_ONLY = {
    "ETHUSDT",
    "IOUSDT",
    "TRUMPUSDT",
    "TAOUSDT",
    "AVAXUSDT",
    "DASHUSDT",
}


def extract_a_zone_ids(review_path: Path) -> list[str]:
    text = review_path.read_text(encoding="utf-8")
    in_a = False
    ids: list[str] = []
    for line in text.splitlines():
        if line.startswith("## A."):
            in_a = True
            continue
        if in_a and line.startswith("## B."):
            break
        if in_a:
            for match in ORDER_ID_RE.findall(line):
                ids.append(match)
    return ids


def load_ack(path: Path) -> dict:
    if not path.exists():
        return {"note": "", "source": "", "acknowledged": []}
    return json.loads(path.read_text(encoding="utf-8"))


def profile_for(order_id: str) -> str:
    symbol = order_id.split("-", 1)[0]
    if symbol in OVERSEAS_ONLY:
        return "overseas"
    if any(order_id.startswith(p) for p in DOMESTIC_PREFIXES):
        return "domestic"
    return "unknown"


def main() -> int:
    review = Path(sys.argv[1]) if len(sys.argv) > 1 else REVIEW
    a_ids = extract_a_zone_ids(review)
    if len(a_ids) != 19:
        print(f"expected 19 A-zone order_ids, got {len(a_ids)}", file=sys.stderr)
        return 1

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ack = load_ack(ACK_PATH)
    merged = sorted(set(ack.get("acknowledged") or []) | set(a_ids))
    ack_payload = {
        "note": "M4 DS01 + M5 A区 DS03 audit_invalid 已登记；watchdog 仅对不在此列的新 invalid 告警",
        "source": "results/fill_supervision_m5_review_2026-06-10.md + M4 checklist",
        "m5_a_zone_applied_at": now,
        "m5_a_zone_disposition": "audit_invalid",
        "acknowledged": merged,
    }
    ACK_PATH.parent.mkdir(parents=True, exist_ok=True)
    ACK_PATH.write_text(json.dumps(ack_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    by_profile: dict[str, list[str]] = {"domestic": [], "overseas": [], "unknown": []}
    for oid in a_ids:
        by_profile[profile_for(oid)].append(oid)

    disposition = {
        "applied_at": now,
        "disposition": "audit_invalid",
        "approved_by": "user",
        "order_ids": a_ids,
        "by_profile": by_profile,
        "repair_reason": "M5 A zone DS03 audit_invalid user approved 2026-06-10",
    }
    DISPOSITION_PATH.write_text(json.dumps(disposition, ensure_ascii=False, indent=2), encoding="utf-8")
    EMPTY_AUDIT.write_text(json.dumps({"suspicious": [], "events": []}, indent=2), encoding="utf-8")

    print(f"ack_total={len(merged)} (+{len(a_ids)} A-zone) -> {ACK_PATH}")
    print(f"disposition -> {DISPOSITION_PATH}")
    print(f"domestic_ids={len(by_profile['domestic'])} overseas_ids={len(by_profile['overseas'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
