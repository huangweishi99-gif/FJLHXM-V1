"""Verify FengJi OS engine includes N04 break-rule + C-class defense fallback."""
from __future__ import annotations

import inspect
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages" / "fengji_core"))

from fengji_core.os_engine import FengJiOSIdentityEngine  # noqa: E402


def main() -> int:
    blue_src = inspect.getsource(FengJiOSIdentityEngine.turn_blue_to_red)
    red_src = inspect.getsource(FengJiOSIdentityEngine.turn_red_to_blue)
    trans_src = inspect.getsource(FengJiOSIdentityEngine.check_transition)

    checks = [
        ("N04 blue_peak→red_ext", "blue peak redefined to red ext (C-class/detachment, N04)" in blue_src),
        ("N04 red_peak→blue_ext", "red peak redefined to blue ext (C-class/detachment, N04)" in red_src),
        ("break red_ext wick/flat", "low <= self.red_ext.price" in trans_src),
        ("break blue_ext wick/flat", "high >= self.blue_ext.price" in trans_src),
    ]
    failed = [name for name, ok in checks if not ok]
    if failed:
        print("OS_ENGINE_N04_FAIL:", ", ".join(failed))
        return 1
    print("OS_ENGINE_N04_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
