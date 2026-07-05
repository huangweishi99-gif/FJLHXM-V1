#!/usr/bin/env python3
"""One-shot 15m probe for domestic futures (bypasses data_manager market-hours gate)."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import data_manager_futures as dm  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Probe Tianqin 15m fetch for selected futures symbols.")
    parser.add_argument("--symbols", default="PG,SC", help="Comma-separated short codes, e.g. PG,SC")
    parser.add_argument("--timeframe", default="15m", choices=["15m", "5m", "1h", "1d"])
    parser.add_argument(
        "--write",
        action="store_true",
        help="Write fetched frame to data/{tf}/{SYMBOL}.csv (ops catchup; bypasses market-hours gate)",
    )
    args = parser.parse_args()

    symbols = [item.strip().upper() for item in str(args.symbols).split(",") if item.strip()]
    if not symbols:
        print("no symbols")
        return 2

    api = dm.connect_api()
    exit_code = 0
    try:
        for sym in symbols:
            tq_code = dm.TQ_SYMBOL_MAP.get(sym)
            if not tq_code:
                print(f"[SKIP] unknown symbol {sym}")
                exit_code = 1
                continue
            try:
                contract, underlying = dm.resolve_data_contract(api, sym, tq_code)
            except Exception as exc:
                print(f"[FAIL] {sym} resolve_data_contract: {exc}")
                exit_code = 1
                continue
            print(f"=== {sym} tq={tq_code} contract={contract} underlying={underlying} ===")
            try:
                frame = dm.fetch_frame(api, contract, args.timeframe)
                tail = str(frame["date"].iloc[-1]) if not frame.empty else "empty"
                print(f"[OK] {args.timeframe} rows={len(frame)} tail={tail}")
                if args.write:
                    frame = frame.copy()
                    frame["symbol"] = contract
                    primary = dm.DATA_DIR / args.timeframe / f"{sym}.csv"
                    dm.atomic_write_csv(frame, primary)
                    legacy = dm.DATA_DIR / args.timeframe / f"{sym}USDT.csv"
                    if legacy != primary:
                        dm.atomic_write_csv(frame, legacy)
                    source_symbols = sorted({str(v) for v in frame["symbol"].astype(str) if str(v).strip()})
                    dm.record_manifest_timeframe(sym, args.timeframe, contract, source_symbols, len(frame))
                    print(f"[WRITE] {primary}")
            except Exception as exc:
                print(f"[FAIL] {sym} {args.timeframe}: {exc}")
                exit_code = 1
    finally:
        try:
            api.close()
        except Exception:
            pass
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
