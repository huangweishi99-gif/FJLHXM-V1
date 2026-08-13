"""Debug DS01/DS09 radar rows for crypto symbols (read-only)."""
from __future__ import annotations

import argparse
import sys
from argparse import Namespace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "packages" / "fengji_core"))

from fengji_total_radar import analyze_symbol  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", default="data")
    parser.add_argument("--os-state-dir", default="runtime/fengji_os_state")
    parser.add_argument("--symbols", default="IOUSDT,BNBUSDT")
    parser.add_argument("--daily-tail", type=int, default=400)
    parser.add_argument("--h1-tail", type=int, default=2400)
    parser.add_argument("--m15-tail", type=int, default=960)
    args = parser.parse_args()

    radar_args = Namespace(
        atr_window=14,
        gap=3,
        daily_tail=args.daily_tail,
        h1_tail=args.h1_tail,
        m15_tail=args.m15_tail,
        os_state_dir=args.os_state_dir,
        extreme_atr_tol=0.80,
    )

    for sym in [s.strip().upper() for s in args.symbols.split(",") if s.strip()]:
        rows = analyze_symbol(Path(args.data_dir), sym, radar_args)
        print(f"=== {sym} total_rows={len(rows)} ===")
        for sid in ("DS01", "DS03", "DS07", "DS09"):
            matched = [r for r in rows if r.strategy_id == sid]
            print(f"  {sid}: {len(matched)}")
            for r in matched:
                print(
                    f"    {r.side} {r.status} trigger={r.trigger_price} dist={r.distance_pct:.4f} "
                    f"os_camp={r.os_camp} reason={str(r.reason)[:100]}"
                )
        blocked = [
            r
            for r in rows
            if "BLOCKED" in r.status.upper()
            or "missing_" in str(r.reason).lower()
            or "BLOCKED" in str(r.reason).upper()
        ]
        if blocked:
            print(f"  blocked={len(blocked)}")
            for r in blocked:
                print(f"    {r.strategy_id} {r.status} {r.reason}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
