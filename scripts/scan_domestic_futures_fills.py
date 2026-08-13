#!/usr/bin/env python3
"""Scan domestic futures DS02-DS09 fills in synced events (exclude accepted order_ids)."""
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DS = {f"DS0{i}" for i in range(2, 10)}


def discover_accepted_sources() -> list[Path]:
    """Collect order_id sources from domestic futures audit result dirs."""
    results = ROOT / "results"
    paths: list[Path] = []
    if not results.is_dir():
        return paths
    for audit_dir in sorted(results.glob("domestic_futures*")):
        if not audit_dir.is_dir():
            continue
        for name in ("fill_audit_subset.json", "USER_SIGNOFF.md", "SUMMARY.md"):
            candidate = audit_dir / name
            if candidate.is_file():
                paths.append(candidate)
    return paths


def load_accepted(paths: list[Path]) -> set[str]:
    out: set[str] = set()
    for path in paths:
        if not path.exists():
            continue
        if path.suffix == ".json":
            payload = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(payload, list):
                for row in payload:
                    if isinstance(row, dict) and row.get("order_id"):
                        out.add(str(row["order_id"]))
        else:
            text = path.read_text(encoding="utf-8")
            for line in text.splitlines():
                if "`" in line and "-DS0" in line:
                    for part in line.split("`"):
                        if "-DS0" in part and "-" in part:
                            out.add(part.strip())
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--hours", type=int, default=336)
    parser.add_argument("--events", default="")
    parser.add_argument("--accepted-json", action="append", default=[])
    parser.add_argument("--out", default="")
    parser.add_argument("--sync-events", action="store_true")
    args = parser.parse_args()

    if args.sync_events:
        sync_script = ROOT / "scripts" / "sync_domestic_fill_events.py"
        if sync_script.is_file():
            import subprocess
            import sys

            subprocess.run(
                [sys.executable, str(sync_script), "--since-hours", str(args.hours)],
                cwd=str(ROOT),
                check=False,
            )

    events = (
        Path(args.events)
        if args.events
        else ROOT / "runtime" / "fengji_pending_orders" / f"events_domestic_fills_{args.hours}h.jsonl"
    )
    if not events.exists():
        print(f"missing events: {events}", flush=True)
        return 1

    accepted_paths = [Path(p) for p in args.accepted_json]
    source_paths = accepted_paths or discover_accepted_sources()
    if not source_paths:
        source_paths = [
            ROOT / "results/domestic_futures_r1_audit_20260625/fill_audit_subset.json",
            ROOT / "results/domestic_futures_r2_audit_20260625/USER_SIGNOFF.md",
        ]
    accepted = load_accepted(source_paths)

    by_strategy: dict[str, list[dict]] = defaultdict(list)
    for line in events.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        obj = json.loads(line)
        if str(obj.get("event_type", "")).lower() != "fill":
            continue
        sid = str(obj.get("strategy_id", "")).upper()
        if sid not in DS:
            continue
        oid = str(obj.get("order_id", ""))
        if oid in accepted:
            continue
        by_strategy[sid].append(
            {
                "order_id": oid,
                "symbol": obj.get("symbol"),
                "time": obj.get("time"),
                "side": obj.get("side"),
            }
        )

    payload = {
        "events": str(events),
        "hours": args.hours,
        "accepted_count": len(accepted),
        "accepted_sources": len(source_paths),
        "by_strategy": dict(sorted(by_strategy.items())),
        "ds02_count": len(by_strategy.get("DS02", [])),
        "ds04_count": len(by_strategy.get("DS04", [])),
        "total_new": sum(len(v) for v in by_strategy.values()),
    }
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(text, encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
