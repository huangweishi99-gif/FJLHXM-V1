"""Audit domestic paper_state for main-continuous (KQ.m@) era artifacts."""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

CUTOFF = datetime(2026, 6, 3, 0, 0, 0)
STATE = Path("runtime/domestic_paper_state.json")


def parse_dt(s: str) -> datetime | None:
    s = str(s or "").strip()[:19]
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    return None


def main() -> None:
    state = json.loads(STATE.read_text(encoding="utf-8"))
    open_old = []
    open_new = []
    invalid_archived = []
    closed_old = []

    for sym, bucket in (state.get("symbols") or {}).items():
        if not isinstance(bucket, dict):
            continue
        for pos in bucket.get("open_positions") or []:
            if pos.get("closed"):
                continue
            dt = parse_dt(pos.get("entry_time"))
            row = {
                "symbol": pos.get("symbol") or sym,
                "strategy": pos.get("strategy_id"),
                "entry_time": pos.get("entry_time"),
                "order_id": pos.get("order_id"),
            }
            if dt and dt < CUTOFF:
                open_old.append(row)
            else:
                open_new.append(row)
        for pos in bucket.get("audit_invalid_positions") or []:
            invalid_archived.append(
                {
                    "symbol": pos.get("symbol") or sym,
                    "strategy": pos.get("strategy_id"),
                    "entry_time": pos.get("entry_time"),
                    "reason": pos.get("audit_invalid_reason"),
                }
            )
        for tr in bucket.get("closed_trades") or []:
            dt = parse_dt(tr.get("entry_time") or tr.get("open_time"))
            if dt and dt < CUTOFF:
                closed_old.append(
                    {
                        "symbol": tr.get("symbol") or sym,
                        "strategy": tr.get("strategy_id"),
                        "entry_time": tr.get("entry_time"),
                        "exit_time": tr.get("exit_time"),
                    }
                )

    print(json.dumps(
        {
            "cutoff": CUTOFF.isoformat(),
            "open_before_cutoff": len(open_old),
            "open_after_cutoff": len(open_new),
            "audit_invalid_archived": len(invalid_archived),
            "closed_trades_before_cutoff": len(closed_old),
            "open_old_sample": open_old[:20],
            "invalid_sample": invalid_archived[:10],
            "closed_old_sample": closed_old[:10],
        },
        ensure_ascii=False,
        indent=2,
    ))


if __name__ == "__main__":
    main()
