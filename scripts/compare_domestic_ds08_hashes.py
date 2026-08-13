#!/usr/bin/env python3
"""Compare local vs domestic-quant core execution/supervision file hashes."""
from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FILES = [
    "packages/fengji_core/fengji_core/ds08_pending_fill.py",
    "packages/fengji_core/fengji_core/fill_supervision.py",
    "src/fengji_futures_pending_order_monitor.py",
    "src/fengji_pending_order_monitor.py",
    "src/fengji_feishu_notify.py",
    "src/fengji_total_radar.py",
]
DOMESTIC_ROOT = "C:/Users/Administrator/quant_futures"
TEXT_SUFFIXES = {".py", ".ps1", ".bat", ".cmd", ".md", ".txt", ".json", ".yaml", ".yml"}


def normalized_hash_bytes(data: bytes, suffix: str) -> bytes:
    if suffix.lower() in TEXT_SUFFIXES:
        return data.replace(b"\r\n", b"\n")
    return data


def local_hash(rel: str) -> str:
    p = ROOT / rel
    data = normalized_hash_bytes(p.read_bytes(), p.suffix)
    return hashlib.sha256(data).hexdigest()[:16]


def remote_hash_domestic(rel: str) -> str:
    path = f"{DOMESTIC_ROOT}/{rel.replace(chr(92), '/')}"
    code = (
        "import hashlib,pathlib,sys;"
        "p=pathlib.Path(sys.argv[1]);"
        "data=p.read_bytes().replace(bytes.fromhex('0d0a'), bytes.fromhex('0a'));"
        "print(hashlib.sha256(data).hexdigest()[:16])"
    )
    cmd = f"python -c {json.dumps(code)} {json.dumps(path)}"
    proc = subprocess.run(
        ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=25", "domestic-quant", cmd],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=60,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr or proc.stdout)
    return proc.stdout.strip()


def main() -> int:
    rows = []
    mismatches = 0
    for rel in FILES:
        loc = local_hash(rel)
        try:
            rem = remote_hash_domestic(rel)
        except RuntimeError as exc:
            rem = f"error:{exc}"
        match = loc.lower() == rem.lower()
        if not match:
            mismatches += 1
        rows.append({"file": rel, "local": loc, "remote": rem, "match": match})
    out = {"host": "domestic-quant", "mismatches": mismatches, "rows": rows}
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 1 if mismatches else 0


if __name__ == "__main__":
    raise SystemExit(main())
