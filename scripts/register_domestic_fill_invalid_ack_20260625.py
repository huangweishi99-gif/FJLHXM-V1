#!/usr/bin/env python3
"""Register EG DS03 watch stale fill (2026-06-24) — stop domestic watchdog fill_supervision spam."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NEW_IDS = [
    "EGUSDT-DS03-D1-short-849aac94a668bd36",
]
REASON = (
    "2026-06-24 EG DS03 watch trigger=4152 vs attack entry_ref=4333; "
    "intraday/stale watch execution audit_invalid; ds03_watch_trigger_stale fix deployed"
)


def main() -> int:
    reg = ROOT / "scripts" / "register_fill_supervision_ack.py"
    cmd = [sys.executable, str(reg), "--reason", REASON, "--approved-by", "cursor_domestic_watchdog_fix"]
    for oid in NEW_IDS:
        cmd.extend(["--order-id", oid])
    subprocess.run(cmd, check=True, cwd=str(ROOT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
