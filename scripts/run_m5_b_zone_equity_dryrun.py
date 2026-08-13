#!/usr/bin/env python3
"""Dry-run equity rollback estimates for M5 B-zone equity_review order_ids."""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DISPOSITION = ROOT / "runtime" / "m5_b_zone_disposition.json"
OUT = ROOT / "results" / "m5_b_zone_equity_dryrun_2026-06-10.json"

DOMESTIC_IDS = {
    "ECUSDT-DS01-D1-long-2dfeae944abdef49",
    "ECUSDT-DS01-D1-long-f48041169975e929",
    "LHUSDT-DS01-D1-short-58b2638967b67a32",
    "LHUSDT-DS01-D1-long-50754f2091ac9227",
}
OVERSEAS_IDS = {"BNBUSDT-DS01-D1-long-ebfd3882424f3fc6"}


def dry_run_local(order_id: str, state_path: Path) -> dict:
    if not state_path.exists():
        return {"order_id": order_id, "status": "missing_state", "path": str(state_path)}
    script = ROOT / "scripts" / "apply_equity_rollback.py"
    proc = subprocess.run(
        [sys.executable, str(script), "--state", str(state_path), "--order-id", order_id, "--dry-run"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return {
        "order_id": order_id,
        "exit_code": proc.returncode,
        "stdout": proc.stdout.strip(),
        "stderr": proc.stderr.strip(),
    }


def main() -> int:
    if not DISPOSITION.exists():
        print(f"missing {DISPOSITION}", file=sys.stderr)
        return 1
    disp = json.loads(DISPOSITION.read_text(encoding="utf-8"))
    equity_ids = list(disp.get("equity_review") or [])
    rows = []
    for oid in equity_ids:
        if oid in DOMESTIC_IDS:
            rows.append(dry_run_local(oid, ROOT / "runtime" / "state_futures_v2.json"))
        elif oid in OVERSEAS_IDS:
            rows.append({"order_id": oid, "status": "remote_only", "note": "run on overseas server"})
        else:
            rows.append({"order_id": oid, "status": "unknown_profile"})
    payload = {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "equity_review_ids": equity_ids,
        "rows": rows,
        "note": "dry-run only; no equity applied",
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"equity_dryrun -> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
