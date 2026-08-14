from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from backtest_a_stock_fengji import run_stock_backtest  # noqa: E402


def clean_filename(value: str) -> str:
    import re

    text = re.sub(r'[\\/:*?"<>|]+', "_", value.strip())
    text = re.sub(r"\s+", "_", text)
    return text[:80] or "stock"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Resume one A-share sector backtest from a stock-pool rank.")
    parser.add_argument("--sector-dir", required=True)
    parser.add_argument("--start-rank", type=int, default=0)
    parser.add_argument("--end-rank", type=int, default=0)
    parser.add_argument("--symbols", default="", help="Comma-separated symbols to re-run (overrides rank range).")
    parser.add_argument("--start", default="20200101")
    parser.add_argument("--end", default="20500101")
    parser.add_argument("--db", default="data/market_data.sqlite")
    parser.add_argument("--data-source", choices=["auto", "db", "download"], default="auto")
    parser.add_argument("--cache-dir", default="data/a_stock")
    parser.add_argument("--strategies", default="DS01,DS02,DS03,DS04,DS05,DS06,DS07,DS08")
    parser.add_argument("--initial-cash", type=float, default=20000.0)
    parser.add_argument("--commission-rate", type=float, default=0.0003)
    parser.add_argument("--min-commission", type=float, default=5.0)
    parser.add_argument("--stamp-duty-rate", type=float, default=0.0005)
    parser.add_argument("--transfer-fee-rate", type=float, default=0.00001)
    parser.add_argument("--slippage-rate", type=float, default=0.0003)
    parser.add_argument("--lot-size", type=int, default=100)
    parser.add_argument("--atr-window", type=int, default=14)
    parser.add_argument("--gap", type=int, default=3)
    parser.add_argument("--download-pause-seconds", type=float, default=6.0)
    parser.add_argument("--sleep-seconds", type=float, default=15.0)
    parser.add_argument("--only-status", default="", help="Only run symbols whose existing summary status matches this value.")
    parser.add_argument("--refresh", action="store_true")
    parser.add_argument("--no-update-db", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    sector_dir = Path(args.sector_dir)
    pool_path = sector_dir / "stock_pool.csv"
    summary_path = sector_dir / "sector_summary_partial.csv"
    final_summary_path = sector_dir / "sector_summary.csv"

    if pool_path.exists():
        pool = pd.read_csv(pool_path, dtype={"symbol": str})
    else:
        # Fallback: build the pool from existing summary rows when stock_pool.csv is absent.
        summary_src = summary_path if summary_path.exists() else final_summary_path
        if not summary_src.exists():
            raise SystemExit(f"No stock_pool.csv and no summary to build pool from: {sector_dir}")
        pool = pd.read_csv(summary_src, dtype={"symbol": str})
        if "board_rank" in pool.columns:
            pool = pool.rename(columns={"board_rank": "rank"})
        if "rank" not in pool.columns:
            pool["rank"] = range(1, len(pool) + 1)
    pool["rank"] = pool["rank"].astype(int)
    pool["symbol"] = pool["symbol"].astype(str).str.zfill(6)
    if args.symbols:
        wanted = {s.strip().zfill(6) for s in args.symbols.split(",") if s.strip()}
        target_pool = pool[pool["symbol"].isin(wanted)].copy()
        if target_pool.empty:
            raise SystemExit(f"No stocks in {pool_path} match symbols: {args.symbols}")
    else:
        end_rank = int(args.end_rank or pool["rank"].max())
        target_pool = pool[(pool["rank"] >= args.start_rank) & (pool["rank"] <= end_rank)].copy()
        if target_pool.empty:
            raise SystemExit(f"No stocks found in rank range {args.start_rank}-{end_rank}: {pool_path}")

    summary_by_symbol: dict[str, dict] = {}
    if summary_path.exists():
        existing = pd.read_csv(summary_path, dtype={"symbol": str})
        for _, item in existing.iterrows():
            row = item.to_dict()
            symbol = str(row.get("symbol", "")).zfill(6)
            if symbol:
                summary_by_symbol[symbol] = row

    board_code = sector_dir.name.split("_")[-1]
    board_name = sector_dir.name[: -(len(board_code) + 1)] if board_code else sector_dir.name

    if args.symbols:
        print(f"Resuming {board_name} {board_code} symbols={args.symbols}", flush=True)
    else:
        print(f"Resuming {board_name} {board_code} ranks {args.start_rank}-{end_rank}", flush=True)
    for index, row in target_pool.iterrows():
        symbol = str(row["symbol"]).zfill(6)
        name = str(row["name"])
        rank = int(row["rank"])
        previous = summary_by_symbol.get(symbol)
        if args.only_status and previous and str(previous.get("status", "")) != args.only_status:
            print(f"\n[{board_name} rank {rank}] {name}({symbol}) status={previous.get('status')}，跳过", flush=True)
            continue
        if args.only_status and previous is None:
            print(f"\n[{board_name} rank {rank}] {name}({symbol}) 无历史状态，跳过", flush=True)
            continue
        print(f"\n[{board_name} rank {rank}] {name}({symbol})", flush=True)

        stock_args = argparse.Namespace(**vars(args))
        stock_args.symbol = symbol
        stock_args.name = name
        stock_args.out_dir = str(sector_dir / f"{symbol}_{clean_filename(name)}")

        try:
            summary = run_stock_backtest(stock_args)
            summary["status"] = "ok"
            summary["error"] = ""
        except Exception as exc:
            summary = {
                "symbol": symbol,
                "name": name,
                "status": "error",
                "error": str(exc),
                "out_dir": str(stock_args.out_dir),
            }
            print(f"{name}({symbol}): error {exc}", flush=True)

        summary["board_code"] = board_code
        summary["board_name"] = board_name
        summary["board_type"] = ""
        summary["board_rank"] = rank
        summary_by_symbol[symbol] = summary

        partial = pd.DataFrame(summary_by_symbol.values())
        if "board_rank" in partial.columns:
            partial = partial.sort_values("board_rank")
        partial.to_csv(summary_path, index=False, encoding="utf-8-sig")
        print(f"Updated partial summary: {summary_path}", flush=True)

        if args.sleep_seconds > 0:
            time.sleep(args.sleep_seconds)

    summary_df = pd.DataFrame(summary_by_symbol.values())
    if "board_rank" in summary_df.columns:
        summary_df = summary_df.sort_values("board_rank")
    summary_df.to_csv(final_summary_path, index=False, encoding="utf-8-sig")
    print(f"\nSaved final sector summary: {final_summary_path}", flush=True)


if __name__ == "__main__":
    main()
