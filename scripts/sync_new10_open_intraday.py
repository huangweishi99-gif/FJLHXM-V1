#!/usr/bin/env python3
"""Sync 15m CSV for new10 OPEN positions that use intraday stops (e.g. DS09)."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages" / "fengji_core"))

from fengji_core.runtime_stop_updater import TIMEFRAME_BY_STRATEGY  # noqa: E402

NEW10 = {
    "XRPUSDT", "HYPEUSDT", "ATHUSDT", "PEPEUSDT", "ARBUSDT",
    "OPUSDT", "SUIUSDT", "NEARUSDT", "INJUSDT", "WLDUSDT",
}


def open_intraday_symbols(paper: dict) -> list[str]:
    out: list[str] = []
    for sym, st in (paper.get("symbols") or {}).items():
        if sym not in NEW10:
            continue
        op = (st or {}).get("open_position")
        if not op:
            continue
        sid = str(op.get("strategy_id", "")).upper()
        if TIMEFRAME_BY_STRATEGY.get(sid) == "15m":
            out.append(sym)
    return sorted(set(out))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--paper-state", default=str(ROOT / "runtime" / "overseas_paper_state.json"))
    parser.add_argument("--dry-run", action="store_true", help="only print symbols JSON, no sync")
    args = parser.parse_args()
    path = Path(args.paper_state)
    if not path.is_file():
        print(json.dumps({"status": "missing", "path": str(path)}))
        return 1
    paper = json.loads(path.read_text(encoding="utf-8"))
    symbols = open_intraday_symbols(paper)
    if not symbols:
        print(json.dumps({"status": "noop", "symbols": []}))
        return 0
    if args.dry_run:
        print(json.dumps({"status": "dry_run", "symbols": symbols}))
        return 0
    cmd = [
        sys.executable,
        str(ROOT / "scripts" / "sync_missing_crypto_15m.py"),
        "--symbols",
        ",".join(symbols),
        "--timeframes",
        "M15",
        "--force-okx",
    ]
    rc = subprocess.call(cmd, cwd=str(ROOT))
    print(json.dumps({"status": "ok" if rc == 0 else "error", "symbols": symbols, "rc": rc}))
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
