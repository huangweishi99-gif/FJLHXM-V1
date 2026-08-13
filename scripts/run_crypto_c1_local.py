#!/usr/bin/env python3
"""Wave 3 C1: unified crypto backtest from local overseas_1d CSV (non-OKX symbols).

Usage:
  python scripts/run_crypto_c1_local.py --symbols IOUSDT,TAOUSDT
  python scripts/run_crypto_c1_local.py --symbols TAOUSDT --skip-existing
"""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from batch_unified_crypto_whitelist import (  # noqa: E402
    DEFAULT_STRATEGIES_CSV,
    normalize_symbol,
    score_crypto_results,
)
from unified_whitelist_engine import UnifiedConfig, run_unified_symbol  # noqa: E402


def to_usdt_symbol(value: str) -> str:
    text = value.strip().upper().replace("-", "")
    if not text.endswith("USDT"):
        text = f"{text}USDT"
    return text


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Local overseas_1d crypto unified backtest (C1).")
    parser.add_argument("--symbols", required=True, help="Comma list e.g. IOUSDT,TAOUSDT")
    parser.add_argument("--out-dir", default=str(ROOT / "results" / "plan_a_crypto_180d"))
    parser.add_argument("--d1-dir", default=str(ROOT / "data" / "overseas_1d"))
    parser.add_argument("--h1-dir", default=str(ROOT / "data" / "1h"))
    parser.add_argument("--m15-dir", default=str(ROOT / "data" / "15m"))
    parser.add_argument("--promote-from", default="", help="Copy existing result dir instead of rerun, format SYM=path")
    parser.add_argument("--skip-existing", action="store_true")
    parser.add_argument("--strategies", default=DEFAULT_STRATEGIES_CSV)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    out_root = Path(args.out_dir)
    d1_dir = Path(args.d1_dir)
    h1_dir = Path(args.h1_dir)
    m15_dir = Path(args.m15_dir)
    strategies = [s.strip().upper() for s in args.strategies.split(",") if s.strip()]
    promote = {}
    for item in args.promote_from.split(","):
        item = item.strip()
        if not item or "=" not in item:
            continue
        sym, path = item.split("=", 1)
        promote[to_usdt_symbol(sym)] = Path(path)

    failures = 0
    for raw in args.symbols.split(","):
        sym = to_usdt_symbol(raw.strip())
        if not sym:
            continue
        inst_id = normalize_symbol(sym)
        symbol_dir = out_root / inst_id
        if args.skip_existing and (symbol_dir / "accepted_trades.csv").exists():
            print(f"SKIP {sym} existing {symbol_dir}")
            continue

        if sym in promote:
            src = promote[sym]
            if not (src / "accepted_trades.csv").exists():
                print(f"FAIL {sym} promote missing accepted_trades at {src}")
                failures += 1
                continue
            symbol_dir.mkdir(parents=True, exist_ok=True)
            for name in (
                "accepted_trades.csv",
                "candidate_trades.csv",
                "rejected_orders.csv",
                "ledger_events.csv",
                "strategy_bad_trades.csv",
            ):
                p = src / name
                if p.exists():
                    shutil.copy2(p, symbol_dir / name)
            trade_count = sum(1 for _ in open(symbol_dir / "accepted_trades.csv", encoding="utf-8-sig")) - 1
            print(f"OK {sym} promoted trades={trade_count} -> {symbol_dir}")
            continue

        d1 = d1_dir / f"{sym}.csv"
        if not d1.exists():
            print(f"FAIL {sym} missing D1 {d1}")
            failures += 1
            continue
        h1 = h1_dir / f"{sym}.csv"
        m15 = m15_dir / f"{sym}.csv"
        config = UnifiedConfig(
            initial_cash=1000.0,
            lots=1,
            commission_rate=0.0,
            slippage_ticks=0.0,
            atr_window=14,
            gap=3,
            max_same_direction_entries=3,
            futures_mode=False,
            spec=None,
        )
        name = sym.replace("USDT", "")
        try:
            ledger = run_unified_symbol(
                name,
                config,
                d1,
                h1 if h1.exists() else None,
                m15 if m15.exists() else None,
                strategies,
                symbol_dir,
            )
            score = score_crypto_results(symbol_dir, 1000.0, 200.0, 2.0, 0.0005, 0.0003, 0.005, None)
            print(
                f"OK {sym} candidates={ledger['candidates']} accepted={score['accepted']} "
                f"return={score['total_return'] * 100:.2f}% -> {symbol_dir}"
            )
        except Exception as exc:  # noqa: BLE001
            print(f"FAIL {sym} {exc}")
            failures += 1

    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
