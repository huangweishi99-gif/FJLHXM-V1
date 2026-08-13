"""Read-only overseas crypto radar/paper snapshot for IOUSDT + BNBUSDT review."""
from __future__ import annotations

import json
import sys
from pathlib import Path


def main() -> int:
    root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".")
    radar_path = root / "runtime/fengji_radar/radar.json"
    paper_path = root / "runtime/fengji_paper/state.json"
    radar = json.loads(radar_path.read_text(encoding="utf-8"))
    paper = json.loads(paper_path.read_text(encoding="utf-8"))

    for sym in ("IOUSDT", "BNBUSDT"):
        rows = [r for r in radar if r.get("symbol") == sym]
        print(f"=== {sym} radar rows={len(rows)} ===")
        for r in sorted(rows, key=lambda x: (str(x.get("strategy_id", "")), str(x.get("status", "")))):
            reason = str(r.get("reason") or "")[:90]
            print(
                f"  {r.get('strategy_id'):5} {str(r.get('side')):5} {str(r.get('status')):22} "
                f"trigger={r.get('trigger_price')} dist={r.get('distance_pct')} os_camp={r.get('os_camp')} "
                f"reason={reason}"
            )
        blocked = [
            r
            for r in rows
            if "BLOCKED" in str(r.get("status", "")).upper()
            or "BLOCKED" in str(r.get("reason", "")).upper()
            or "missing_" in str(r.get("reason", "")).lower()
        ]
        print(f"  blocked_or_incomplete={len(blocked)}")
        for r in blocked:
            print(f"    -> {r.get('strategy_id')} {r.get('status')} {r.get('reason')}")

        st = (paper.get("symbols") or {}).get(sym) or {}
        op = st.get("open_position")
        if op:
            print(f"  paper open: {op.get('strategy_id')} side={op.get('side')} entry={op.get('entry_time')}")
        else:
            print("  paper open: None")

        m15 = root / f"data/15m/{sym}.csv"
        print(f"  m15_csv exists={m15.exists()}")

    pending_path = root / "runtime/fengji_pending_orders/pending_orders.json"
    if pending_path.exists():
        pending = json.loads(pending_path.read_text(encoding="utf-8"))
        for sym in ("IOUSDT", "BNBUSDT"):
            prows = [r for r in pending if isinstance(r, dict) and r.get("symbol") == sym]
            print(f"=== {sym} pending={len(prows)} ===")
            for r in prows:
                print(f"  {r.get('strategy_id')} {r.get('status')} trigger={r.get('trigger_price')}")

    for sym in ("IOUSDT", "BNBUSDT"):
        for tf in ("1d", "1h", "15m"):
            sp = root / "runtime/fengji_os_state" / f"{sym}_{tf}.json"
            if not sp.exists():
                continue
            st = json.loads(sp.read_text(encoding="utf-8"))
            print(
                f"=== {sym} os_{tf} camp={st.get('camp')} camp_confirmed={st.get('camp_confirmed')} "
                f"pending_turn={st.get('pending_turn')} aligned={st.get('camp') == st.get('camp_confirmed')} ==="
            )

    ai = paper.get("audit_invalid_closes") or []
    hits = [x for x in ai if isinstance(x, dict) and sym_in(x, ("IOUSDT", "BNBUSDT"))]
    print(f"=== audit_invalid_closes IO/BNB count={len(hits)} ===")
    for x in hits[:5]:
        print(f"  {x.get('order_id', x)}")

    return 0


def sym_in(row: dict, symbols: tuple[str, ...]) -> bool:
    blob = json.dumps(row, ensure_ascii=False)
    return any(s in blob for s in symbols)


if __name__ == "__main__":
    raise SystemExit(main())
