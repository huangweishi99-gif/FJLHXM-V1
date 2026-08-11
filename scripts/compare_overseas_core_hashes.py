#!/usr/bin/env python3
"""Compare local vs overseas core file SHA256 (no secrets)."""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FILES = [
    "src/fengji_pending_order_monitor.py",
    "src/fengji_feishu_notify.py",
    "src/fengji_total_radar.py",
    "src/overseas_paper_monitor.py",
    "packages/fengji_core/fengji_core/ds03_pending_fill.py",
    "packages/fengji_core/fengji_core/stop_bar_monitor.py",
    "packages/fengji_core/fengji_core/ds08_pending_fill.py",
    "packages/fengji_core/fengji_core/os_engine.py",
    "packages/fengji_core/fengji_core/fill_supervision.py",
    "packages/fengji_core/fengji_core/feishu_trade_notify.py",
    "data_manager.py",
    "services/crypto_ingest.py",
    "scripts/sync_missing_crypto_15m.py",
    "scripts/check_okx_csv_freshness.py",
    "scripts/check_ds09_feishu_dedup_state.py",
    "scripts/watchdog_overseas.sh",
    "scripts/audit_new10_crypto_fills.py",
]


def local_hash_bytes(rel: str) -> bytes:
    p = ROOT / rel
    data = p.read_bytes()
    if p.suffix == ".sh":
        return data.replace(b"\r\n", b"\n")
    return data


def local_hash(rel: str) -> str:
    return hashlib.sha256(local_hash_bytes(rel)).hexdigest()


def remote_hashes(host: str, remote_root: str, rels: list[str]) -> dict[str, str]:
    """Fetch remote SHA256 for all paths in one SSH round-trip."""
    lines_script: list[str] = []
    for rel in rels:
        path = f"{remote_root}/{rel}".replace("\\", "/")
        lines_script.append(f"sha256sum '{path}' 2>/dev/null || echo 'MISSING  {rel}'")
    cmd = " ; ".join(lines_script)
    proc = subprocess.run(
        ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=20", host, cmd],
        capture_output=True,
        text=True,
        timeout=120,
    )
    out: dict[str, str] = {}
    for line in (proc.stdout or "").splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith("MISSING"):
            parts = line.split()
            if len(parts) >= 2:
                out[parts[-1]] = "MISSING"
            continue
        parts = line.split()
        if len(parts) >= 2:
            # sha256sum prints: HASH  /path/to/file
            out[parts[-1]] = parts[0]
    for rel in rels:
        path = f"{remote_root}/{rel}".replace("\\", "/")
        if path not in out and rel not in out:
            out[rel] = "MISSING"
    return out


def remote_hash(host: str, remote_root: str, rel: str) -> tuple[int, str]:
    path = f"{remote_root}/{rel}".replace("\\", "/")
    proc = subprocess.run(
        ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=20", host, f"sha256sum {path} 2>/dev/null || echo MISSING"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    line = (proc.stdout or "").strip().splitlines()[0] if proc.stdout else ""
    if "MISSING" in line or not line:
        return proc.returncode, "MISSING"
    return proc.returncode, line.split()[0]


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare local vs overseas core file hashes.")
    parser.add_argument("--host", default="overseas-quant")
    parser.add_argument("--remote-root", default="/home/ubuntu/quant_crypto")
    parser.add_argument("--out", default="", help="optional JSON output path")
    args = parser.parse_args()

    rows = []
    mismatches = 0
    remote = remote_hashes(args.host, args.remote_root, FILES)
    for rel in FILES:
        lh = local_hash(rel)
        path = f"{args.remote_root}/{rel}".replace("\\", "/")
        rh = remote.get(path, remote.get(rel, "MISSING"))
        ok = rh != "MISSING" and lh.lower() == rh.lower()
        if not ok:
            mismatches += 1
        rows.append({"file": rel, "local": lh[:16], "remote": rh[:16] if rh != "MISSING" else rh, "match": ok})
    payload = {"host": args.host, "mismatches": mismatches, "rows": rows}
    text = json.dumps(payload, indent=2)
    print(text)
    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text, encoding="utf-8")
    return 0 if mismatches == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
