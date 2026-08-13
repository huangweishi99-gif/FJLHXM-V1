#!/usr/bin/env python3
"""One-shot: probe Tianqin 1d last bars for a few symbols (run on domestic server)."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import data_manager_futures as dm
import pandas as pd

SAMPLES = ("RB", "LC", "PG", "AG", "SA")


def main() -> int:
    print("catchup=", dm.needs_stale_catchup())
    print("market=", dm.is_market_update_time())
    api = dm.connect_api()
    try:
        for short in SAMPLES:
            tq = dm.TQ_SYMBOL_MAP.get(short)
            if not tq:
                continue
            contract, underlying = dm.resolve_data_contract(api, short, tq)
            frame = dm.fetch_frame(api, contract, "1d")
            tail = frame.tail(3)[["date", "close"]].to_string(index=False) if not frame.empty else "EMPTY"
            csv_path = dm.DATA_DIR / "1d" / f"{short}.csv"
            csv_last = "n/a"
            if csv_path.exists():
                df = pd.read_csv(csv_path)
                csv_last = str(df["date"].iloc[-1])
            print(f"--- {short} contract={contract} rows={len(frame)} csv_last={csv_last}")
            print(tail)
    finally:
        api.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
