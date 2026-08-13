#!/usr/bin/env python3
"""从 M4 invalid 人工确认清单提取 order_id，生成 fill_supervision 已确认登记文件。"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CHECKLIST = ROOT / "results" / "fill_supervision_invalid_checklist_2026-06-09.md"
DEFAULT_OUT = ROOT / "runtime" / "fill_supervision_acknowledged.json"

ORDER_ID_RE = re.compile(r"`([A-Z0-9_.-]+-DS\d+-[A-Z0-9]+-(?:long|short)-[0-9a-f]+)`")


def main() -> int:
    checklist = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_CHECKLIST
    out = Path(sys.argv[2]) if len(sys.argv) > 2 else DEFAULT_OUT
    ids = sorted(set(ORDER_ID_RE.findall(checklist.read_text(encoding="utf-8"))))
    payload = {
        "note": "M4 invalid 人工确认清单登记；watchdog 仅对不在此列的新 invalid 告警",
        "source": str(checklist.relative_to(ROOT)) if checklist.is_relative_to(ROOT) else str(checklist),
        "acknowledged": ids,
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"acknowledged={len(ids)} -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
