#!/usr/bin/env python
"""Import trade_context_snapshots.csv + context_bucket_stats.csv into PostgreSQL."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services"))
sys.path.insert(0, str(ROOT / "packages" / "fengji_core"))

from db.context_queries import import_context_csvs  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Import context stats CSV into PostgreSQL.")
    parser.add_argument("--result-dir", required=True)
    parser.add_argument("--no-replace", action="store_true")
    args = parser.parse_args()
    counts = import_context_csvs(Path(args.result_dir), replace=not args.no_replace)
    print(counts)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
