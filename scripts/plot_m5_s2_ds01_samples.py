#!/usr/bin/env python3
"""Wave 4 S2: plot M5 B-zone representative DS01 audit sandboxes (AG camp + RB N04)."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results" / "m5_samples"
PY = sys.executable
SCRIPT = ROOT / "scripts" / "plot_ds01_audit_sandbox.py"

SAMPLES = [
    {
        "csv": "data/1d/AG.csv",
        "symbol": "AGUSDT",
        "side": "short",
        "entry_date": "2026-05-27",
        "fill_price": 18135.0,
        "start": "2026-05-10",
        "end": "2026-06-10",
        "order_tag": "756e2840 camp_mismatch",
        "verdict": "监督: signal_camp=1(5/26棍) 空DS01需蓝营",
        "out": OUT / "AGUSDT_ds01_audit_20260527.png",
    },
    {
        "csv": "data/1d/RB.csv",
        "symbol": "RBUSDT",
        "side": "short",
        "entry_date": "2026-06-08",
        "fill_price": 3151.0,
        "start": "2026-05-20",
        "end": "2026-06-12",
        "order_tag": "5b4e7fd4 N04 camp",
        "verdict": "N04后RB_1d蓝→红；信号棍红营；空DS01需蓝营",
        "out": OUT / "RBUSDT_ds01_audit_20260608.png",
    },
]


def run_one(spec: dict) -> None:
    cmd = [
        PY, str(SCRIPT),
        "--csv", spec["csv"],
        "--market", "futures",
        "--symbol", spec["symbol"],
        "--side", spec["side"],
        "--entry-date", spec["entry_date"],
        "--fill-price", str(spec["fill_price"]),
        "--start", spec["start"],
        "--end", spec["end"],
        "--order-tag", spec["order_tag"],
        "--verdict", spec["verdict"],
        "--out", str(spec["out"]),
    ]
    subprocess.run(cmd, check=True, cwd=str(ROOT))


def main() -> int:
    for spec in SAMPLES:
        run_one(spec)
    print(f"S2 samples -> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
