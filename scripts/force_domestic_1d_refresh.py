#!/usr/bin/env python3
"""One-shot: reconnect Tianqin and rewrite all domestic 1d/1h/15m CSV (run on domestic server)."""
from __future__ import annotations

import sys
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import data_manager_futures as dm


def main() -> int:
    print(f"catchup={dm.needs_stale_catchup()} market={dm.is_market_update_time()}", flush=True)
    api = None
    try:
        api = dm.connect_api()
        ok, fail = dm.fetch_all_data(api)
        print(f"fetch done success={ok} fail={fail}", flush=True)
        return 0 if ok > 0 and fail == 0 else 1
    except Exception as exc:
        print(f"ERROR: {exc}", flush=True)
        traceback.print_exc()
        return 2
    finally:
        if api is not None:
            try:
                api.close()
            except Exception:
                pass


if __name__ == "__main__":
    raise SystemExit(main())
