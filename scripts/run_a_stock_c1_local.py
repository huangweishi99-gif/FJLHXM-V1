#!/usr/bin/env python3
"""Wave 3 C1-A: incremental A-stock backtest from local data/a_stock qfq CSV.

Usage:
  python scripts/run_a_stock_c1_local.py --dry-run
  python scripts/run_a_stock_c1_local.py --limit 30
  python scripts/run_a_stock_c1_local.py --symbols 000049,000063
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
from backtest_a_stock_fengji import normalize_code, run_stock_backtest  # noqa: E402
from chart_symbol_catalog import list_local_chart_symbols  # noqa: E402


def a_stock_gap_symbols(results_root: Path, cache_dir: Path) -> list[str]:
    backtest = load_backtest_index(results_root)
    bt_keys = backtest["A_STOCK"]
    gaps: list[str] = []
    for sym in list_local_chart_symbols("A_STOCK"):
        key = match_key("A_STOCK", sym)
        row = bt_keys.get(key)
        if row is not None and int(row.get("trade_count") or 0) > 0:
            continue
        code = normalize_code(sym)
        if not (cache_dir / f"{code}_1D_qfq.csv").exists():
            continue
        gaps.append(code)
    return sorted(set(gaps))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Wave 3 C1-A local A-stock incremental backtest.")
    parser.add_argument("--out-dir", default=str(ROOT / "results" / "plan_a_a_stock_c1"))
    parser.add_argument("--cache-dir", default=str(ROOT / "data" / "a_stock"))
    parser.add_argument("--db", default=str(ROOT / "data" / "market_data.sqlite"))
    parser.add_argument("--limit", type=int, default=30, help="Batch size (0=all gaps)")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--symbols", default="", help="Override comma codes e.g. 000049,000063")
    parser.add_argument("--refresh", action="store_true", help="Re-download K-line even if cache exists")
    parser.add_argument(
        "--data-source",
        choices=["auto", "db", "download"],
        default="db",
        help="A-share K-line source: db=SQLite only; auto=db then download; download=Eastmoney only.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    cache_dir = Path(args.cache_dir)
    out_root = Path(args.out_dir)
    out_root.mkdir(parents=True, exist_ok=True)

    if args.symbols.strip():
        codes = [normalize_code(s) for s in args.symbols.split(",") if s.strip()]
    else:
        codes = a_stock_gap_symbols(ROOT / "results", cache_dir)
        if args.limit > 0:
            codes = codes[: args.limit]

    if not codes:
        print("C1-A: no A-stock gaps with local D1 qfq CSV")
        return 0

    print(f"C1-A: {len(codes)} A stocks")
    for code in codes:
        d1 = cache_dir / f"{code}_1D_qfq.csv"
        h1 = cache_dir / f"{code}_60m_qfq.csv"
        print(f"  {code} d1={d1.exists()} h1={h1.exists()}")

    if args.dry_run:
        return 0

    failures = 0
    summaries: list[dict] = []
    for index, code in enumerate(codes, start=1):
        print(f"\n[{index}/{len(codes)}] {code}")
        stock_args = argparse.Namespace(
            symbol=code,
            name=code,
            start="20200101",
            end="20500101",
            db=str(args.db),
            data_source=args.data_source,
            cache_dir=str(cache_dir),
            out_dir=str(out_root / code),
            strategies="DS01,DS02,DS03,DS04,DS05,DS06,DS07,DS08,DS09",
            initial_cash=20000.0,
            commission_rate=0.0003,
            min_commission=5.0,
            stamp_duty_rate=0.0005,
            transfer_fee_rate=0.00001,
            slippage_rate=0.0003,
            lot_size=100,
            atr_window=14,
            gap=3,
            refresh=args.refresh,
            no_update_db=True,
        )
        try:
            summary = run_stock_backtest(stock_args)
            summary["status"] = "ok"
            summary["error"] = ""
        except Exception as exc:  # noqa: BLE001
            failures += 1
            summary = {"symbol": code, "status": "error", "error": str(exc), "out_dir": str(out_root / code)}
            print(f"{code}: FAIL {exc}")
        summaries.append(summary)

    if summaries:
        import pandas as pd

        pd.DataFrame(summaries).to_csv(out_root / "a_stock_c1_summary.csv", index=False, encoding="utf-8-sig")

    print(f"\nC1-A done ok={len(codes) - failures} fail={failures} out={out_root}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
