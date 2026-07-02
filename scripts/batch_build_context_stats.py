#!/usr/bin/env python
"""对 discover_backtest_results 扫描到的目录批量生成 context stats CSV。"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages" / "fengji_core"))
sys.path.insert(0, str(ROOT / "scripts"))

from discover_backtest_results import context_snapshots_ready, discover  # noqa: E402
from fengji_core.context_stats import build_from_result_dir, write_outputs  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Batch build trade context snapshots.")
    parser.add_argument("--root", default=str(ROOT / "results"))
    parser.add_argument("--market", default="", help="Only process one market tag")
    parser.add_argument("--limit", type=int, default=0, help="Max dirs to process (0=all)")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--only-missing", action="store_true", help="Skip dirs that already have trade_context_snapshots.csv")
    parser.add_argument("--force-rebuild", action="store_true", help="Rebuild even when trade_context_snapshots.csv already exists")
    parser.add_argument("--log", default="", help="Write JSON log path (default: results/context_stats_batch_log.json)")
    args = parser.parse_args()

    items = discover(Path(args.root))
    if args.market:
        items = [i for i in items if i["market"] == args.market.upper()]
    items = [i for i in items if int(i.get("trade_count", 0)) > 0 and i["market"] != "UNKNOWN"]
    if args.only_missing and not args.force_rebuild:
        items = [i for i in items if not context_snapshots_ready(Path(i["result_dir"]))]

    if args.limit > 0:
        items = items[: args.limit]

    ok, fail = 0, 0
    log: list[dict] = []
    for item in items:
        result_dir = Path(item["result_dir"])
        if args.dry_run:
            print(f"DRY {item['market']} {item['symbol']} -> {result_dir}")
            ok += 1
            continue
        try:
            snapshots, stats = build_from_result_dir(
                result_dir,
                data_dir=ROOT / item["data_dir"],
                market=item["market"],
                symbol=item["symbol"],
                timeframe=item["timeframe"],
            )
            write_outputs(result_dir, snapshots, stats)
            print(f"OK {item['market']} {item['symbol']} snapshots={len(snapshots)} buckets={len(stats)}")
            log.append({**item, "status": "ok", "snapshots": len(snapshots), "buckets": len(stats)})
            ok += 1
        except Exception as exc:
            print(f"FAIL {item['market']} {item['symbol']} {result_dir}: {exc}")
            log.append({**item, "status": "error", "error": str(exc)})
            fail += 1

    summary_path = Path(args.log) if args.log else Path(args.root) / "context_stats_batch_log.json"
    summary_path.write_text(json.dumps({"ok": ok, "fail": fail, "items": log}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"done ok={ok} fail={fail} log={summary_path}")
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
