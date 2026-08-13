#!/usr/bin/env python
"""CLI wrapper: python scripts/build_context_stats.py --result-dir ... --symbol ..."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages" / "fengji_core"))

from fengji_core.context_stats import build_cli  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(build_cli())
