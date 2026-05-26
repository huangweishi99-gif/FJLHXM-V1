"""Download OKX 15m bars for DS09 (峰极总定式 D1+M15).

Usage:
    python scripts/fetch_crypto_m15_for_ds09.py --symbols DEFAULT --days 180
    python scripts/fetch_crypto_m15_for_ds09.py --symbols ETH-USDT,BTC-USDT --days 1825 --refresh
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from batch_unified_crypto_whitelist import DEFAULT_CRYPTO_WHITELIST, fetch_okx_history, read_symbols  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fetch OKX 15m history for DS09 backtests.")
    parser.add_argument("--symbols", default="DEFAULT", help="Comma list, DEFAULT, or a text file.")
    parser.add_argument("--days", type=int, default=180)
    parser.add_argument("--cache-dir", default="data/crypto_okx")
    parser.add_argument("--atr-window", type=int, default=14)
    parser.add_argument("--refresh", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    symbols = read_symbols(args.symbols)
    cache_root = Path(args.cache_dir)
    cache_root.mkdir(parents=True, exist_ok=True)

    for inst_id in symbols:
        out = cache_root / f"{inst_id}_15m_{args.days}d.csv"
        try:
            frame = fetch_okx_history(inst_id, "15m", args.days, out, args.atr_window, args.refresh)
            print(f"{inst_id}: saved {len(frame)} rows -> {out}")
        except Exception as exc:
            print(f"{inst_id}: ERROR {exc}")


if __name__ == "__main__":
    main()
