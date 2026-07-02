#!/usr/bin/env python
"""统计 trade_context_snapshots.csv / PG API 中 exit_price 覆盖率。"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services"))


def scan_csv_dirs(root: Path) -> dict[str, int]:
    total = 0
    with_exit = 0
    dirs_missing_col = 0
    for path in root.rglob("trade_context_snapshots.csv"):
        try:
            df = pd.read_csv(path)
        except Exception:
            continue
        if df.empty:
            continue
        total += len(df)
        if "exit_price" not in df.columns:
            dirs_missing_col += 1
            continue
        with_exit += int(df["exit_price"].notna().sum())
    return {
        "csv_files": len(list(root.rglob("trade_context_snapshots.csv"))),
        "dirs_missing_exit_price_col": dirs_missing_col,
        "snapshot_rows": total,
        "rows_with_exit_price": with_exit,
    }


def scan_pg(limit: int = 5000) -> dict[str, int]:
    from db.context_queries import list_trades_with_strength

    markets = ["CRYPTO", "FUTURES", "A_STOCK", "US_STOCK"]
    total = 0
    with_exit = 0
    for mkt in markets:
        try:
            from db.context_queries import list_context_symbol_summary

            syms = list_context_symbol_summary(market=mkt, limit=200)
        except Exception as exc:
            return {"pg_error": str(exc)}
        for row in syms[:50]:
            sym = str(row.get("symbol") or "")
            if not sym:
                continue
            trades = list_trades_with_strength(symbol=sym, market=mkt, limit=min(limit, 200))
            total += len(trades)
            with_exit += sum(1 for t in trades if t.get("exit_price") not in (None, "", 0))
    return {"pg_trade_rows_sampled": total, "pg_with_exit_price": with_exit}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=str(ROOT / "results"))
    parser.add_argument("--pg", action="store_true")
    args = parser.parse_args()

    csv_stats = scan_csv_dirs(Path(args.root))
    print("CSV coverage:", csv_stats)
    if csv_stats["snapshot_rows"]:
        pct = csv_stats["rows_with_exit_price"] / csv_stats["snapshot_rows"] * 100
        print(f"CSV exit_price fill rate: {pct:.1f}%")

    if args.pg:
        pg_stats = scan_pg()
        print("PG sample:", pg_stats)
        if pg_stats.get("pg_trade_rows_sampled"):
            pct = pg_stats["pg_with_exit_price"] / pg_stats["pg_trade_rows_sampled"] * 100
            print(f"PG exit_price fill rate (sample): {pct:.1f}%")

    missing = csv_stats.get("dirs_missing_exit_price_col", 0)
    return 1 if missing > 0 else 0


if __name__ == "__main__":
    raise SystemExit(main())
