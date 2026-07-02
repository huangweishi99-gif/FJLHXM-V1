#!/usr/bin/env python3
"""Post-deploy smoke — delegates to W17 remote acceptance checklist."""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(description="W17 post-deploy smoke (acceptance wrapper)")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--ssh-tunnel", default="")
    parser.add_argument("--local-port", type=int, default=8040)
    parser.add_argument("--wait-seconds", type=float, default=5.0)
    parser.add_argument("--admin-token", default="")
    parser.add_argument("--no-web", action="store_true")
    args, extra = parser.parse_known_args()

    cmd = [
        sys.executable,
        str(ROOT / "scripts" / "w17_remote_acceptance.py"),
        "--wait-seconds",
        str(args.wait_seconds),
    ]
    if args.ssh_tunnel:
        cmd.extend(["--ssh-tunnel", args.ssh_tunnel, "--local-port", str(args.local_port)])
    elif args.base_url:
        cmd.extend(["--base-url", args.base_url.rstrip("/")])
    if args.admin_token:
        cmd.extend(["--admin-token", args.admin_token])
    if args.no_web:
        cmd.append("--no-web")
    cmd.extend(extra)

    proc = subprocess.run(cmd, cwd=str(ROOT))
    return proc.returncode


if __name__ == "__main__":
    raise SystemExit(main())
