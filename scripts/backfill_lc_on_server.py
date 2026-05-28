"""在国内服务器执行：加长抓取 LC K 线（供 DS09）。"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

from data_manager_futures import TQ_SYMBOL_MAP, connect_api, fetch_symbol, log_line, DATA_LENGTHS


def main() -> None:
    log_line(f"LC backfill DATA_LENGTHS={DATA_LENGTHS}")
    api = connect_api()
    try:
        deadline = time.time() + 45
        while api.wait_update(deadline=deadline):
            pass
        ok = fetch_symbol(api, "LC", TQ_SYMBOL_MAP["LC"])
        log_line(f"LC backfill finished ok={ok}")
    finally:
        api.close()
    if not ok:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
