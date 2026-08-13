#!/usr/bin/env python3
"""Wave 3 C1-U: incremental US stock backtest from local data/us_stock CSV.

Usage:
  python scripts/run_us_stock_c1_local.py --dry-run
  python scripts/run_us_stock_c1_local.py --limit 10
  python scripts/run_us_stock_c1_local.py --symbols ABBV,AMD,NVDA
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "src"))

from audit_coverage_gaps import load_backtest_index, match_key  # noqa: E402
from backtest_us_stock_fengji import run_us_stock_backtest  # noqa: E402
from chart_symbol_catalog import list_local_chart_symbols  # noqa: E402
from unified_whitelist_engine import DEFAULT_STRATEGIES_CSV  # noqa: E402
from us_stock_data import normalize_ticker  # noqa: E402


def us_gap_symbols(results_root: Path, cache_dir: Path) -> list[str]:
    backtest = load_backtest_index(results_root)
    bt_keys = backtest["US_STOCK"]
    gaps: list[str] = []
    for sym in list_local_chart_symbols("US_STOCK"):
        key = match_key("US_STOCK", sym)
        row = bt_keys.get(key)
        if row is not None and int(row.get("trade_count") or 0) > 0:
            continue
        ticker = normalize_ticker(sym)
        if not (cache_dir / f"{ticker}_1D.csv").exists():
            continue
        gaps.append(ticker)
    return sorted(set(gaps))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Wave 3 C1-U local US stock incremental backtest.")
    parser.add_argument("--out-dir", default=str(ROOT / "results" / "plan_a_us_stock_c1"))
    parser.add_argument("--cache-dir", default=str(ROOT / "data" / "us_stock"))
    parser.add_argument("--limit", type=int, default=10, help="Batch size (0=all gaps)")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--symbols", default="", help="Override comma tickers")
    parser.add_argument("--refresh", action="store_true", help="Re-download K-line even if cache exists")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    cache_dir = Path(args.cache_dir)
    out_root = Path(args.out_dir)
    out_root.mkdir(parents=True, exist_ok=True)

    if args.symbols.strip():
        tickers = [normalize_ticker(s) for s in args.symbols.split(",") if s.strip()]
    else:
        tickers = us_gap_symbols(ROOT / "results", cache_dir)
        if args.limit > 0:
            tickers = tickers[: args.limit]

    if not tickers:
        print("C1-U: no US stock gaps with local D1 CSV")
        return 0

    print(f"C1-U: {len(tickers)} US stocks")
    for t in tickers:
        d1 = cache_dir / f"{t}_1D.csv"
        h1 = cache_dir / f"{t}_1H.csv"
        print(f"  {t} d1={d1.exists()} h1={h1.exists()}")

    if args.dry_run:
        return 0

    strategies = DEFAULT_STRATEGIES_CSV.replace(",DS09", "")
    failures = 0
    summaries: list[dict] = []
    for index, ticker in enumerate(tickers, start=1):
        print(f"\n[{index}/{len(tickers)}] {ticker}")
        stock_args = argparse.Namespace(
            symbol=ticker,
            name=ticker,
            start="2020-01-01",
            end="2050-01-01",
            cache_dir=str(cache_dir),
            out_dir=str(out_root / ticker),
            data_source="auto",
            download_pause_seconds=0.0,
            strategies=strategies,
            initial_cash=100_000.0,
            commission_rate=0.0005,
            slippage_rate=0.0002,
            atr_window=14,
            gap=3,
            refresh=args.refresh,
        )
        try:
            summary = run_us_stock_backtest(stock_args)
            summary["status"] = "ok"
            summary["error"] = ""
        except Exception as exc:  # noqa: BLE001
            failures += 1
            summary = {"symbol": ticker, "status": "error", "error": str(exc), "out_dir": str(out_root / ticker)}
            print(f"{ticker}: FAIL {exc}")
        summaries.append(summary)

    if summaries:
        import pandas as pd

        pd.DataFrame(summaries).to_csv(out_root / "us_stock_c1_summary.csv", index=False, encoding="utf-8-sig")

    print(f"\nC1-U done ok={len(tickers) - failures} fail={failures} out={out_root}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
