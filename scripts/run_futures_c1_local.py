#!/usr/bin/env python3
"""Wave 3 C1-F: incremental domestic futures backtest from local D1 CSV.

Uses `data/futures/1d` (+ optional `data/futures_lc/1d`). Skips crypto mis-tags
(APT/ETH/IO/RENDER) and LC_CORRUPT. DS07/08/09 skip when H1/M15 missing.

Usage:
  python scripts/run_futures_c1_local.py --dry-run
  python scripts/run_futures_c1_local.py --limit 2
  python scripts/run_futures_c1_local.py
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "src"))

from audit_coverage_gaps import build_report, load_backtest_index, match_key  # noqa: E402
from chart_symbol_catalog import list_local_chart_symbols  # noqa: E402
from fengji_core.symbol_names import FUTURES_CN_NAMES  # noqa: E402

SKIP_MATCH_KEYS = frozenset({"APT", "ETH", "IO", "RENDER", "LC_CORRUPT"})
CODE_TO_BATCH_NAME = {"TA": "PTA"}


def futures_gap_symbols(results_root: Path) -> list[tuple[str, str, str]]:
    """Return [(catalog_symbol, match_key, batch_name), ...] needing backtest."""
    backtest = load_backtest_index(results_root)
    bt_keys = backtest["FUTURES"]
    rows: list[tuple[str, str, str]] = []
    for catalog_sym in list_local_chart_symbols("FUTURES"):
        key = match_key("FUTURES", catalog_sym)
        if key in SKIP_MATCH_KEYS:
            continue
        bt = bt_keys.get(key)
        if bt is not None and int(bt.get("trade_count") or 0) > 0:
            continue
        batch_name = CODE_TO_BATCH_NAME.get(key) or FUTURES_CN_NAMES.get(key) or catalog_sym
        rows.append((catalog_sym, key, batch_name))
    # de-dupe by match_key (LC may appear twice in catalog)
    seen: set[str] = set()
    out: list[tuple[str, str, str]] = []
    for item in rows:
        if item[1] in seen:
            continue
        seen.add(item[1])
        out.append(item)
    return sorted(out, key=lambda x: x[1])


def resolve_daily_dirs(batch_name: str) -> tuple[Path, Path]:
    """Pick daily-dir and minute-dir for batch_unified_whitelist_engine."""
    candidates = [
        ROOT / "data" / "futures" / "1d",
        ROOT / "data" / "futures_lc" / "1d",
    ]
    daily_dir = candidates[0]
    for folder in candidates:
        if (folder / f"{batch_name}.csv").exists():
            daily_dir = folder
            break
    minute_roots = [
        ROOT / "data" / "futures" / "60m",
        ROOT / "data" / "futures" / "15m",
        ROOT / "data" / "1h",
        ROOT / "data" / "15m",
    ]
    minute_dir = next((p for p in minute_roots if p.is_dir()), ROOT / "data" / "futures" / "60m")
    return daily_dir, minute_dir


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Wave 3 C1-F local futures incremental backtest.")
    parser.add_argument("--out-dir", default=str(ROOT / "results" / "plan_a_futures_c1"))
    parser.add_argument("--limit", type=int, default=0, help="Max symbols (0=all gaps)")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--symbols", default="", help="Override comma list of batch names (Chinese/PTA)")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    gaps = futures_gap_symbols(ROOT / "results")
    if args.symbols.strip():
        names = [s.strip() for s in args.symbols.split(",") if s.strip()]
        gaps = [(n, n, n) for n in names]
    if args.limit > 0:
        gaps = gaps[: args.limit]

    if not gaps:
        print("C1-F: no futures gaps (all catalog symbols have backtest dirs with trades)")
        return 0

    print(f"C1-F: {len(gaps)} futures to backtest")
    for catalog_sym, key, batch_name in gaps:
        daily_dir, minute_dir = resolve_daily_dirs(batch_name)
        d1 = daily_dir / f"{batch_name}.csv"
        print(f"  {key:6} batch={batch_name:8} d1={d1.exists()} path={d1}")

    if args.dry_run:
        return 0

    out_root = Path(args.out_dir)
    out_root.mkdir(parents=True, exist_ok=True)
    whitelist_path = out_root / "_c1_whitelist.txt"
    whitelist_path.write_text("\n".join(item[2] for item in gaps) + "\n", encoding="utf-8")

    # Use first gap's dirs; all domestic futures share data/futures/1d layout.
    daily_dir, minute_dir = resolve_daily_dirs(gaps[0][2])
    minute_dir.mkdir(parents=True, exist_ok=True)

    cmd = [
        sys.executable,
        str(ROOT / "src" / "batch_unified_whitelist_engine.py"),
        "--whitelist",
        str(whitelist_path),
        "--daily-dir",
        str(daily_dir),
        "--minute-dir",
        str(minute_dir),
        "--out-dir",
        str(out_root),
    ]
    print("RUN", " ".join(cmd))
    proc = subprocess.run(cmd, cwd=str(ROOT), check=False)
    return proc.returncode


if __name__ == "__main__":
    raise SystemExit(main())
