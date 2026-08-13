#!/usr/bin/env python3
"""Watch new-10 crypto open positions; emit sandbox on new fill (local or overseas paths)."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NEW10 = {
    "XRPUSDT", "HYPEUSDT", "ATHUSDT", "PEPEUSDT", "ARBUSDT",
    "OPUSDT", "SUIUSDT", "NEARUSDT", "INJUSDT", "WLDUSDT",
}
DEFAULT_STATE = ROOT / "runtime" / "new10_fill_watch_state.json"
AUDIT = ROOT / "scripts" / "audit_new10_crypto_fills.py"


def load_positions(paper_state_path: Path) -> dict[str, dict]:
    ps = json.loads(paper_state_path.read_text(encoding="utf-8"))
    out: dict[str, dict] = {}
    for sym, st in (ps.get("symbols") or {}).items():
        if sym not in NEW10:
            continue
        op = (st or {}).get("open_position")
        if op:
            out[sym] = {
                "order_id": op.get("order_id"),
                "strategy_id": op.get("strategy_id"),
                "entry_time": op.get("entry_time"),
            }
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--paper-state", default=str(ROOT / "runtime" / "overseas_paper_state.json"))
    parser.add_argument("--state-file", default=str(DEFAULT_STATE))
    parser.add_argument("--out-dir", default=str(ROOT / "results" / "new10_fill_watch"))
    parser.add_argument("--emit-sandbox", action="store_true")
    args = parser.parse_args()

    paper = Path(args.paper_state)
    if not paper.exists():
        print(f"missing paper state: {paper}", file=sys.stderr)
        return 1

    current = load_positions(paper)
    state_path = Path(args.state_file)
    prev = json.loads(state_path.read_text(encoding="utf-8")) if state_path.exists() else {"seen": {}}
    seen: dict = dict(prev.get("seen") or {})
    prev_open = set(prev.get("open_symbols") or list(seen.keys()))
    new_syms: list[str] = []
    closed_syms: list[str] = []
    events = list(prev.get("events") or [])

    for sym, pos in current.items():
        oid = str(pos.get("order_id") or "")
        if not oid:
            continue
        if sym not in seen or str(seen.get(sym) or "") != oid:
            new_syms.append(sym)
            events.append({"time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "type": "open", "symbol": sym, **pos})
            seen[sym] = oid

    for sym in sorted(prev_open - set(current.keys())):
        closed_syms.append(sym)
        events.append(
            {
                "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "type": "close",
                "symbol": sym,
                "last_order_id": seen.get(sym),
            }
        )

    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(
        json.dumps(
            {"seen": seen, "open_symbols": sorted(current.keys()), "events": events[-100:]},
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print(
        json.dumps(
            {
                "open": len(current),
                "new": new_syms,
                "closed": closed_syms,
                "symbols": sorted(current),
            },
            ensure_ascii=False,
            indent=2,
        )
    )

    if args.emit_sandbox and new_syms and AUDIT.exists():
        stamp = datetime.now().strftime("%Y%m%d_%H%M")
        out = Path(args.out_dir) / f"fill_{stamp}"
        cmd = [
            sys.executable,
            str(AUDIT),
            "--paper-state",
            str(paper),
            "--out-dir",
            str(out),
            "--only-symbols",
            ",".join(new_syms),
            "--no-audit",
        ]
        subprocess.run(cmd, cwd=str(ROOT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
