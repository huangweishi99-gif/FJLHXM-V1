#!/usr/bin/env python
"""扫描 results/ 下所有 accepted_trades.csv，推断 market/symbol 供 context-stats 批处理。"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ACCEPTED_NAMES = ("accepted_trades.csv", "stock_long_accepted_trades.csv")


def infer_from_path(result_dir: Path, accepted_file: Path) -> dict[str, str]:
    result_dir = result_dir.resolve()
    accepted_file = accepted_file.resolve()
    try:
        rel = result_dir.relative_to(ROOT.resolve()).as_posix().lower()
    except ValueError:
        rel = result_dir.as_posix().lower()
    parent = result_dir.name
    grand = result_dir.parent.name if result_dir.parent else ""

    market = "UNKNOWN"
    symbol = ""
    timeframe = "1d"
    data_dir = "data"

    if "a_stock" in rel or re.match(r"^\d{6}_", parent):
        market = "A_STOCK"
        data_dir = "data/a_stock"
        m = re.match(r"^(\d{6})", parent) or re.search(r"(?:^|_)(\d{6})(?:_|$)", parent)
        if m:
            symbol = m.group(1)
    elif "crypto" in rel or "ds09" in rel or parent.endswith("usdt") or "-usdt" in parent.lower():
        market = "CRYPTO"
        data_dir = "data"
        sym = parent.upper().replace("-", "")
        if not sym.endswith("USDT"):
            sym = f"{sym}USDT" if sym else ""
        symbol = sym
        if "15m" in rel or "m15" in rel or "crypto_realtime_monitor" in rel:
            timeframe = "15m"
    elif "us_stock" in rel or re.match(r"^[A-Z]{1,5}_", parent):
        market = "US_STOCK"
        data_dir = "data/us_stock"
        base = parent.split("_")[0].upper()
        if re.match(r"^[A-Z][A-Z0-9.-]*$", base):
            symbol = base
        else:
            m = re.match(r"^([A-Z]{1,5})", parent.upper())
            if m:
                symbol = m.group(1)
    elif "futures" in rel or grand.upper() in {"LC", "SA", "FG"}:
        market = "FUTURES"
        data_dir = "data/futures"
        symbol = parent.upper() or grand.upper()

    if not symbol and parent:
        symbol = parent.split("_")[0].upper()

    return {
        "result_dir": str(result_dir),
        "accepted_file": str(accepted_file),
        "market": market,
        "symbol": symbol,
        "timeframe": timeframe,
        "data_dir": data_dir,
    }


def discover(root: Path) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    root = root.resolve()
    if not root.exists():
        return rows
    for name in ACCEPTED_NAMES:
        for path in root.rglob(name):
            path = path.resolve()
            result_dir = path.parent
            if result_dir.name.lower() == "raw_fengji":
                result_dir = result_dir.parent
            result_dir = result_dir.resolve()
            key = str(result_dir)
            if key in seen:
                continue
            seen.add(key)
            item = infer_from_path(result_dir, path)
            try:
                item["trade_count"] = max(0, sum(1 for _ in open(path, encoding="utf-8-sig")) - 1)
            except OSError:
                item["trade_count"] = -1
            rows.append(item)
    rows.sort(key=lambda r: (r["market"], r["symbol"], r["result_dir"]))
    return rows


def context_snapshots_ready(result_dir: Path) -> bool:
    """trade_context_snapshots.csv 存在且至少有一行数据（非仅表头）。"""
    path = Path(result_dir) / "trade_context_snapshots.csv"
    if not path.is_file() or path.stat().st_size <= 4:
        return False
    try:
        with path.open("r", encoding="utf-8-sig") as handle:
            handle.readline()
            return bool(handle.readline().strip())
    except OSError:
        return False


def main() -> int:
    parser = argparse.ArgumentParser(description="Discover backtest result directories.")
    parser.add_argument("--root", default=str(ROOT / "results"))
    parser.add_argument("--market", default="", help="Filter by market tag")
    parser.add_argument("--min-trades", type=int, default=1)
    parser.add_argument("--out", default="", help="Write JSON report path")
    args = parser.parse_args()

    rows = discover(Path(args.root))
    if args.market:
        rows = [r for r in rows if r["market"] == args.market.upper()]
    rows = [r for r in rows if int(r.get("trade_count", 0)) >= args.min_trades]

    report = {"root": args.root, "count": len(rows), "items": rows}
    text = json.dumps(report, ensure_ascii=False, indent=2)
    print(text)
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
