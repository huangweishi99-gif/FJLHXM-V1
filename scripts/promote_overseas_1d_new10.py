#!/usr/bin/env python3
"""Copy newer overseas_1d CSV into data/1d for new10 symbols (followup/audit)."""
from __future__ import annotations

import argparse
import json
import shutil
from datetime import datetime
from pathlib import Path

NEW10 = {
    "XRPUSDT", "HYPEUSDT", "ATHUSDT", "PEPEUSDT", "ARBUSDT",
    "OPUSDT", "SUIUSDT", "NEARUSDT", "INJUSDT", "WLDUSDT",
}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", default="data")
    args = parser.parse_args()
    data = Path(args.data_dir)
    src_dir = data / "overseas_1d"
    dst_dir = data / "1d"
    dst_dir.mkdir(parents=True, exist_ok=True)
    promoted: list[str] = []
    for sym in sorted(NEW10):
        src = src_dir / f"{sym}.csv"
        if not src.is_file():
            continue
        dst = dst_dir / f"{sym}.csv"
        if not dst.is_file() or src.stat().st_mtime > dst.stat().st_mtime:
            shutil.copy2(src, dst)
            promoted.append(sym)
    print(json.dumps({"promoted": promoted, "count": len(promoted)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
