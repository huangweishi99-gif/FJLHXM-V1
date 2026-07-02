#!/usr/bin/env python3
"""Pull recent overseas fill rows from remote events.jsonl (no full ~700MB scp)."""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Sync overseas fill events slice for local fill_supervision.")
    parser.add_argument("--ssh-host", default="overseas-quant")
    parser.add_argument("--remote-root", default="/home/ubuntu/quant_crypto")
    parser.add_argument("--since-hours", type=int, default=168)
    parser.add_argument(
        "--out",
        help="Local output path (default runtime/fengji_pending_orders/events_overseas_fills_{hours}h.jsonl)",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    out = (
        Path(args.out)
        if args.out
        else ROOT / "runtime" / "fengji_pending_orders" / f"events_overseas_fills_{args.since_hours}h.jsonl"
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(out.suffix + ".tmp")

    remote_py = (
        "import json; from pathlib import Path; "
        "from fengji_core.fill_supervision import parse_events_jsonl; "
        f"rows=parse_events_jsonl(Path('runtime/fengji_pending_orders/events.jsonl'), since_hours={args.since_hours}); "
        "[print(json.dumps(r, ensure_ascii=False)) for r in rows]"
    )
    remote_cmd = (
        f"cd {args.remote_root} && export PYTHONPATH=src:packages/fengji_core && "
        f".venv/bin/python -c {remote_py!r}"
    )
    proc = subprocess.run(
        ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=15", args.ssh_host, remote_cmd],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if proc.returncode != 0:
        sys.stderr.write(proc.stderr or proc.stdout or "ssh extract failed\n")
        return proc.returncode
    payload = proc.stdout
    if not payload.strip():
        sys.stderr.write("remote fill extract returned empty output\n")
        return 1
    tmp.write_text(payload, encoding="utf-8")
    tmp.replace(out)
    lines = sum(1 for line in payload.splitlines() if line.strip())
    print(f"synced {out} bytes={out.stat().st_size} fills={lines} since_hours={args.since_hours}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
