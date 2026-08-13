#!/usr/bin/env python3
"""Archive domestic futures CSVs misnamed as *USDT under data/1d (catalog pollution)."""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages" / "fengji_core"))

from fengji_core.symbol_names import FUTURES_CN_NAMES  # noqa: E402

MIS_TAG_MAP = {
    "AGUSDT": ("AG", "沪银"),
    "BRUSDT": ("BR", "合成橡胶"),
    "ECUSDT": ("EC", "集运欧线"),
}


def main() -> int:
    legacy = ROOT / "data" / "1d"
    archive = ROOT / "data" / "_archive_mis_tagged_usdt"
    archive.mkdir(parents=True, exist_ok=True)
    moved = 0
    for usdt_name, (code, cn) in MIS_TAG_MAP.items():
        if code not in FUTURES_CN_NAMES:
            print(f"SKIP unknown code {code}")
            continue
        src = legacy / f"{usdt_name}.csv"
        if not src.exists():
            print(f"SKIP missing {src}")
            continue
        dst = archive / f"{usdt_name}.csv"
        shutil.move(str(src), str(dst))
        print(f"ARCHIVED {usdt_name} -> {dst} (futures {code}/{cn} uses data/futures/1d/{cn}.csv)")
        moved += 1
    print(f"done moved={moved}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
