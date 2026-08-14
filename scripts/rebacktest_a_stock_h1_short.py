"""Re-run A-share sector backtests for stocks whose old h1_rows < 500 (now backfilled to 1023 bars).

Reads results/a_stock_all_sectors_master_summary.csv, groups rows by source_file (sector dir),
and invokes resume_a_stock_sector_from_rank.py --symbols <...> per sector so that DS07/DS08
actually run on the newly backfilled 60m data. Data is served from market_data.sqlite (auto source),
so no downloads are triggered.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RESUME = ROOT / "scripts" / "resume_a_stock_sector_from_rank.py"
SUMMARY = ROOT / "results" / "a_stock_all_sectors_master_summary.csv"
H1_MIN = 500


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Re-backtest A-share stocks with old h1_rows < H1_MIN.")
    p.add_argument("--summary", default=str(SUMMARY))
    p.add_argument("--only-board", default="", help="Only process sector dirs whose source path contains one of these substrings (comma-separated).")
    p.add_argument("--sleep-seconds", type=float, default=0.0)
    p.add_argument("--download-pause-seconds", type=float, default=0.0)
    p.add_argument("--dry-run", action="store_true")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    only_boards = [s.strip() for s in args.only_board.split(",") if s.strip()]
    df = pd.read_csv(args.summary, encoding="utf-8-sig")
    low = df[df["h1_rows"] < H1_MIN]
    if low.empty:
        print(f"No rows with h1_rows < {H1_MIN}; nothing to re-run.")
        return

    groups: dict[str, list[str]] = {}
    for _, row in low.iterrows():
        src = str(row["source_file"])
        if only_boards and not any(t in src for t in only_boards):
            continue
        sector_dir = str(Path(src).parent)
        groups.setdefault(sector_dir, []).append(str(row["symbol"]).zfill(6))

    print(f"Found {len(low)} rows, {len(groups)} sector dirs to re-run.")
    total_ok = total_err = 0
    for sector_dir, symbols in sorted(groups.items()):
        symbols_sorted = ",".join(sorted(set(symbols)))
        cmd = [
            sys.executable,
            str(RESUME),
            "--sector-dir", sector_dir,
            "--symbols", symbols_sorted,
            "--sleep-seconds", str(args.sleep_seconds),
            "--download-pause-seconds", str(args.download_pause_seconds),
        ]
        print(f"\n=== {Path(sector_dir).name} ({len(set(symbols))} symbols) ===", flush=True)
        if args.dry_run:
            print(" ".join(cmd))
            continue
        result = subprocess.run(cmd, cwd=ROOT)
        if result.returncode == 0:
            total_ok += 1
        else:
            total_err += 1
            print(f"FAILED sector dir: {sector_dir} (rc={result.returncode})", flush=True)

    print(f"\nDone: {total_ok} sectors ok, {total_err} failed.")


if __name__ == "__main__":
    main()
