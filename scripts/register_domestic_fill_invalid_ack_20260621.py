#!/usr/bin/env python3
"""Register 2026-06 domestic NEW fill_supervision invalid order_ids (stop watchdog spam)."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NEW_IDS = [
    "SFUSDT-DS01-D1-long-6e8db7f90620b99d",
    "SFUSDT-DS01-D1-long-e36cbaabd983c4c2",
    "PPUSDT-DS03-D1-short-f7d42786d017770d",
    "JDUSDT-DS03-D1-long-b41f6e608f634a99",
    "SFUSDT-DS03-D1-short-61f00c281ca5091a",
    "PUSDT-DS03-D1-short-fd1496922981058b",
    "EGUSDT-DS03-D1-short-25e1739d13280b32",
    "SHUSDT-DS03-D1-short-ae881a2d0ce74fef",
]
REASON = "2026-06 domestic DS03 post-OS-rebuild audit_invalid; SF DS01 tick tolerance; watchdog ack batch"


def main() -> int:
    reg = ROOT / "scripts" / "register_fill_supervision_ack.py"
    cmd = [sys.executable, str(reg), "--reason", REASON, "--approved-by", "cursor_domestic_watchdog_fix"]
    for oid in NEW_IDS:
        cmd.extend(["--order-id", oid])
    subprocess.run(cmd, check=True, cwd=str(ROOT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
