#!/usr/bin/env python
"""FJLHXM-UI.pen 设计定稿：从 build_fjlhxm_ui_pen.py 全量重建 9 屏 + 审阅说明。"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PEN = ROOT / "FJLHXM-UI.pen"
BUILD = ROOT / "scripts" / "build_fjlhxm_ui_pen.py"

EXPECTED = [
    "01 · Dashboard",
    "02 · Backtest",
    "03 · Monitor",
    "04 · Strategies",
    "05 · Pricing",
    "06 · Symbol Chart",
    "07 · Auth",
    "08 · Community ·",
    "09 · Payment",
]


def main() -> int:
    spec = importlib.util.spec_from_file_location("build_fjlhxm_ui_pen", BUILD)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    rc = mod.main()
    data = json.loads(PEN.read_text(encoding="utf-8"))
    names = [str(c.get("name", "")) for c in data.get("children", [])]
    glass = [n for n in names if "Glass Gold" in n or "定稿" in n]
    print(f"\n定稿屏位 ({len(glass)} frames):")
    for n in sorted(glass):
        try:
            print(f"  · {n}")
        except UnicodeEncodeError:
            print(f"  · {n.encode('ascii', 'backslashreplace').decode()}")
    missing = [k for k in EXPECTED if not any(k in n for n in glass)]
    if missing:
        print("WARN missing:", missing)
        return 1
    print(f"\nOK · {PEN.name} finalized")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
