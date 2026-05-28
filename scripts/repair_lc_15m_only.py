"""仅重抓 LC 15m（交易时段或天勤可连时在国内服务器执行）。"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

from data_manager_futures import (  # noqa: E402
    DATA_DIR,
    TIMEFRAMES,
    TQ_SYMBOL_MAP,
    atomic_write_csv,
    connect_api,
    fetch_frame,
    log_line,
)


def main() -> None:
    length = int(os.getenv("FUTURES_15M_LENGTH", "8000"))
    log_line(f"LC 15m-only repair, data_length={length}")
    api = connect_api()
    try:
        deadline = time.time() + 45
        while api.wait_update(deadline=deadline):
            pass
        frame = fetch_frame(api, TQ_SYMBOL_MAP["LC"], "15m")
        for name in ("LC.csv", "LCUSDT.csv"):
            atomic_write_csv(frame, DATA_DIR / "15m" / name)
        log_line(f"LC 15m repair ok rows={len(frame)} last={frame['date'].iloc[-1]}")
    finally:
        api.close()


if __name__ == "__main__":
    main()
