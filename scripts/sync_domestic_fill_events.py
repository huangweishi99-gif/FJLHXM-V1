#!/usr/bin/env python3
"""Pull domestic fill slice via remote file (avoids SSH stdout encoding issues)."""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ssh-host", default="domestic-quant")
    parser.add_argument("--remote-root", default="C:/Users/Administrator/quant_futures")
    parser.add_argument("--since-hours", type=int, default=168)
    parser.add_argument("--out", default="")
    args = parser.parse_args()

    out = (
        Path(args.out)
        if args.out
        else ROOT / "runtime" / "fengji_pending_orders" / f"events_domestic_fills_{args.since_hours}h.jsonl"
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    remote_root = args.remote_root.replace("\\", "/")
    remote_out = f"{remote_root}/runtime/_tmp_domestic_fills_{args.since_hours}h.jsonl"
    extract = f"{remote_root}/scripts/extract_fill_events_jsonl.py"
    py = "C:/Users/Administrator/AppData/Local/Programs/Python/Python310/python.exe"

    scp_extract = subprocess.run(
        [
            "scp",
            "-o",
            "BatchMode=yes",
            str(ROOT / "scripts" / "extract_fill_events_jsonl.py"),
            f"{args.ssh_host}:{extract}",
        ],
        capture_output=True,
        text=True,
    )
    if scp_extract.returncode != 0:
        sys.stderr.write(scp_extract.stderr or "scp extract script failed\n")
        return scp_extract.returncode

    remote_cmd = (
        f"powershell -NoProfile -Command \"Set-Location '{remote_root}'; "
        f"$env:PYTHONPATH='src;packages/fengji_core'; $env:FENGJI_MARKET='futures'; "
        f"& '{py}' scripts/extract_fill_events_jsonl.py "
        f"--events runtime/fengji_pending_orders/events.jsonl "
        f"--since-hours {args.since_hours} --out runtime/_tmp_domestic_fills_{args.since_hours}h.jsonl\""
    )
    run = subprocess.run(["ssh", "-o", "BatchMode=yes", args.ssh_host, remote_cmd], capture_output=True, text=True)
    if run.returncode != 0:
        sys.stderr.write(run.stderr or run.stdout or "remote extract failed\n")
        return run.returncode

    fetch = subprocess.run(
        ["scp", "-o", "BatchMode=yes", f"{args.ssh_host}:{remote_out}", str(out)],
        capture_output=True,
        text=True,
    )
    if fetch.returncode != 0:
        sys.stderr.write(fetch.stderr or "scp fills failed\n")
        return fetch.returncode

    lines = sum(1 for line in out.read_text(encoding="utf-8").splitlines() if line.strip())
    print(f"synced {out} bytes={out.stat().st_size} fills={lines} since_hours={args.since_hours}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
