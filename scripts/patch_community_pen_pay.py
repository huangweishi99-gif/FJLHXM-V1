"""追加 FJLHXM-UI.pen 第 8 屏付款态（08 · Community Pay）。"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PEN = ROOT / "FJLHXM-UI.pen"
SCRIPTS = ROOT / "scripts"


def _load_build():
    spec = importlib.util.spec_from_file_location("build_fjlhxm_ui_pen", SCRIPTS / "build_fjlhxm_ui_pen.py")
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def main() -> int:
    build = _load_build()
    data = json.loads(PEN.read_text(encoding="utf-8"))
    data["children"] = [
        c for c in data.get("children", []) if "08 · Community Pay" not in str(c.get("name", ""))
    ]
    data["children"].append(build.screen_community_pay())
    PEN.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Appended 08 · Community Pay to {PEN.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
