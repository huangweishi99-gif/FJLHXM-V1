"""验证峰极 OS 状态库：同一份 K 线连跑两轮，第二轮应增量（processed_len 不变、文件体积涨幅小）。"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "packages" / "fengji_core"))

from fengji_core.ds07 import attach_os_detail  # noqa: E402
from fengji_core.os_state_store import (  # noqa: E402
    build_os_detail_frame_stateful,
    os_state_path,
    read_os_state,
)


def load_daily_csv(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path)
    frame.columns = [c.strip().lower() for c in frame.columns]
    if "date" not in frame.columns and "timestamp" in frame.columns:
        frame = frame.rename(columns={"timestamp": "date"})
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
    frame = frame.dropna(subset=["date"]).sort_values("date").reset_index(drop=True)
    return frame


def run_once(csv: Path, state_dir: Path, symbol: str, gap: int, tail: int) -> dict:
    df = load_daily_csv(csv)
    if tail > 0 and len(df) > tail:
        df = df.tail(tail).reset_index(drop=True)
    state_path = os_state_path(state_dir, symbol, "1d")
    size_before = state_path.stat().st_size if state_path.exists() else 0
    st_before = read_os_state(state_path)
    pl_before = int((st_before or {}).get("processed_len", 0) or 0)

    build_os_detail_frame_stateful(df, gap, state_path, attach_os_detail, record_hardened_by_bar=True)

    st_after = read_os_state(state_path) or {}
    size_after = state_path.stat().st_size
    return {
        "state_path": str(state_path),
        "rows": len(df),
        "processed_len_before": pl_before,
        "processed_len_after": int(st_after.get("processed_len", 0) or 0),
        "last_date": st_after.get("last_date"),
        "size_before": size_before,
        "size_after": size_after,
        "size_delta": size_after - size_before,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", required=True)
    parser.add_argument("--symbol", required=True)
    parser.add_argument("--state-dir", default="runtime/fengji_os_state_verify")
    parser.add_argument("--gap", type=int, default=3)
    parser.add_argument("--tail", type=int, default=400)
    args = parser.parse_args()

    state_dir = Path(args.state_dir)
    state_dir.mkdir(parents=True, exist_ok=True)
    state_path = os_state_path(state_dir, args.symbol, "1d")
    if state_path.exists():
        state_path.unlink()

    r1 = run_once(Path(args.csv), state_dir, args.symbol, args.gap, args.tail)
    r2 = run_once(Path(args.csv), state_dir, args.symbol, args.gap, args.tail)

    incremental_ok = (
        r2["processed_len_before"] == r2["processed_len_after"]
        and r2["processed_len_after"] == r1["processed_len_after"]
        and r2["size_delta"] < max(500_000, int(r1["size_after"] * 0.02))
    )

    out = {"run1": r1, "run2": r2, "incremental_ok": incremental_ok}
    print(json.dumps(out, ensure_ascii=False, indent=2))
    if not incremental_ok:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
