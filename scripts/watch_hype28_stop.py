#!/usr/bin/env python3
"""Watch HYPE #28 DS05 long stop vs monitor-aligned D1 bar."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "packages" / "fengji_core"))

from fengji_core.stop_bar_monitor import (  # noqa: E402
    read_latest_bar,
    stop_bar_after_entry,
    stop_crossed,
    stop_timeframe_for_position,
)

ORDER_ID = "HYPEUSDT-DS05-D1-long-d69873cc01ec9234"
SYMBOL = "HYPEUSDT"


def load_open_position(paper_path: Path) -> dict | None:
    paper = json.loads(paper_path.read_text(encoding="utf-8"))
    st = (paper.get("symbols") or {}).get(SYMBOL) or {}
    op = st.get("open_position")
    if not op or str(op.get("order_id", "")) != ORDER_ID:
        return None
    return op


def pending_eval_bar(data_dir: Path, position: dict) -> dict | None:
    import pandas as pd
    from fengji_core.os_state_store import find_data_file
    from fengji_core.stop_bar_monitor import filter_valid_price_rows

    tf = stop_timeframe_for_position(position)
    path = find_data_file(data_dir, SYMBOL, tf)
    if not path.is_file():
        return None
    entry_time = pd.to_datetime(position.get("entry_time"), errors="coerce")
    frame = pd.read_csv(path)
    frame.columns = [str(c).strip().lower() for c in frame.columns]
    if "date" not in frame.columns:
        frame["date"] = frame.iloc[:, 0]
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
    frame = filter_valid_price_rows(frame)
    if frame.empty:
        return None
    row = frame.iloc[-1]
    bar_time = pd.to_datetime(row["date"], errors="coerce")
    if pd.isna(entry_time) or pd.isna(bar_time) or bar_time.normalize() <= entry_time.normalize():
        return None
    return {
        "date": str(bar_time.strftime("%Y-%m-%d %H:%M:%S")),
        "high": float(row["high"]),
        "low": float(row["low"]),
        "close": float(row["close"]),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--paper-state", default=str(ROOT / "runtime" / "overseas_paper_state.json"))
    parser.add_argument("--data-dir", default=str(ROOT / "data"))
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    paper_path = Path(args.paper_state)
    if not paper_path.is_file():
        print(f"missing paper state: {paper_path}", file=sys.stderr)
        return 1

    position = load_open_position(paper_path)
    if position is None:
        payload = {"status": "CLOSED_OR_MISSING", "order_id": ORDER_ID}
        if args.json:
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        else:
            print("HYPE #28: not open (closed or order_id changed)")
        return 0

    data_dir = Path(args.data_dir)
    bar = read_latest_bar(data_dir, SYMBOL, ["1d"], completed_only=True)
    stop = float(position.get("current_stop") or position.get("initial_stop") or 0)
    monitor_effective = bool(bar and stop_bar_after_entry(position, bar) and stop_crossed(position, bar))
    pending = pending_eval_bar(data_dir, position)
    pending_effective = bool(pending and stop_crossed(position, pending))

    if monitor_effective:
        phase = "STOP_TRIGGERED_MONITOR"
        code = 3
    elif pending_effective:
        phase = "STOP_PENDING_MONITOR_BAR"
        code = 2
    else:
        phase = "OPEN_OK"
        code = 0

    payload = {
        "status": phase,
        "order_id": ORDER_ID,
        "entry_time": position.get("entry_time"),
        "entry_price": position.get("entry_price"),
        "current_stop": stop,
        "monitor_bar": bar,
        "monitor_effective_stop": monitor_effective,
        "pending_eval_bar": pending,
        "pending_eval_breach": pending_effective,
    }
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(f"HYPE #28: {phase} stop={stop}")
        if bar:
            print(f"  monitor bar: {bar.get('date')} low={bar.get('low')}")
        if pending:
            print(f"  pending eval: {pending.get('date')} low={pending.get('low')}")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
