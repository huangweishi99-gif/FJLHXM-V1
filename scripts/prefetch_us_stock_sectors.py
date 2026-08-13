#!/usr/bin/env python
"""预下载 gics_sectors.json 中全部 ticker 的 1D/1H CSV，避免回测时触发 yfinance 限流。"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from us_stock_data import fetch_us_kline, normalize_ticker

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CATALOG = ROOT / "data" / "us_stock" / "gics_sectors.json"


def load_tickers(catalog: Path, top_n: int) -> list[str]:
    payload = json.loads(catalog.read_text(encoding="utf-8"))
    seen: list[str] = []
    for sector in payload.get("sectors", []):
        for raw in sector.get("tickers", [])[:top_n]:
            sym = normalize_ticker(str(raw))
            if sym and sym not in seen:
                seen.append(sym)
    return seen


def main() -> int:
    parser = argparse.ArgumentParser(description="Prefetch US stock OHLCV for sector backtests.")
    parser.add_argument("--catalog", default=str(DEFAULT_CATALOG))
    parser.add_argument("--top-n", type=int, default=21)
    parser.add_argument("--cache-dir", default=str(ROOT / "data" / "us_stock"))
    parser.add_argument("--start", default="2020-01-01")
    parser.add_argument("--end", default="2050-01-01")
    parser.add_argument("--source", default="auto", choices=["auto", "yahoo_chart", "yfinance"])
    parser.add_argument("--refresh", action="store_true")
    parser.add_argument("--sleep-seconds", type=float, default=1.0, help="Extra pause between tickers")
    parser.add_argument("--skip-hourly", action="store_true")
    args = parser.parse_args()

    cache = Path(args.cache_dir)
    tickers = load_tickers(Path(args.catalog), args.top_n)
    ok, fail = 0, 0
    for i, ticker in enumerate(tickers, start=1):
        print(f"[{i}/{len(tickers)}] {ticker}")
        try:
            fetch_us_kline(
                ticker,
                "1d",
                args.start,
                args.end,
                cache / f"{ticker}_1D.csv",
                source=args.source,
                refresh=args.refresh,
                pause_seconds=0.8,
            )
            if not args.skip_hourly:
                fetch_us_kline(
                    ticker,
                    "1h",
                    args.start,
                    args.end,
                    cache / f"{ticker}_1H.csv",
                    source=args.source,
                    refresh=args.refresh,
                    pause_seconds=0.8,
                )
            ok += 1
        except Exception as exc:
            fail += 1
            print(f"  FAIL {ticker}: {exc}")
        if args.sleep_seconds > 0:
            time.sleep(args.sleep_seconds)
    print(f"done ok={ok} fail={fail} cache={cache}")
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
