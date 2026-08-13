#!/usr/bin/env python
"""Rebuild CRYPTO context snapshots using period-aware OKX CSV binding."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages" / "fengji_core"))
sys.path.insert(0, str(ROOT / "scripts"))

from discover_backtest_results import discover  # noqa: E402
from fengji_core.context_stats import (  # noqa: E402
    build_from_result_dir,
    infer_crypto_period_from_hint,
    resolve_data_csv,
    write_outputs,
)


def _run_id_from_realtime_dir(result_dir: Path) -> str | None:
    parts = result_dir.parts
    for idx, part in enumerate(parts):
        if part == "crypto_realtime_monitor" and idx + 1 < len(parts):
            return parts[idx + 1]
    return None


def _asof_data_dir(result_dir: Path) -> Path | None:
    run_id = _run_id_from_realtime_dir(result_dir)
    if not run_id:
        return None
    path = ROOT / "data" / "crypto_okx_asof" / run_id
    return path if path.exists() else None


def _period_hint(result_dir: Path) -> str | Path:
    if _run_id_from_realtime_dir(result_dir):
        return f"{result_dir}_180d"
    return result_dir


def _load_targets(path: Path) -> set[str]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    targets = {
        str(item["result_dir"])
        for item in payload.get("items", [])
        if item.get("market") == "CRYPTO"
        and str(item.get("classification", ""))
        in {
            "NEEDS_PERIOD_AWARE_CRYPTO_REBUILD",
            "RECOVERABLE_PERIOD_AWARE_CRYPTO",
            "MISSING_ORIGINAL_REALTIME_WINDOW",
        }
    }
    return targets


def main() -> int:
    parser = argparse.ArgumentParser(description="Rebuild failed CRYPTO context stats with exact OKX period CSVs.")
    parser.add_argument("--audit", default=str(ROOT / "results" / "context_stats_failure_audit_2026-06-02.json"))
    parser.add_argument("--root", default=str(ROOT / "results"))
    parser.add_argument("--data-dir", default=str(ROOT / "data"))
    parser.add_argument("--log", default=str(ROOT / "results" / "context_crypto_period_rebuild_2026-06-02.json"))
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    targets = _load_targets(Path(args.audit))
    inventory = [item for item in discover(Path(args.root)) if item["market"] == "CRYPTO" and item["result_dir"] in targets]
    inventory.sort(key=lambda x: x["result_dir"])

    ok = 0
    skipped = 0
    fail = 0
    log_items: list[dict] = []
    data_dir = Path(args.data_dir)
    for item in inventory:
        result_dir = Path(item["result_dir"])
        data_dir_for_item = _asof_data_dir(result_dir) or data_dir
        source_hint = _period_hint(result_dir)
        timeframe = item["timeframe"]
        if _run_id_from_realtime_dir(result_dir):
            timeframe = "15m"
        period = infer_crypto_period_from_hint(source_hint)
        source_csv = None
        try:
            source_csv = resolve_data_csv(
                data_dir_for_item,
                item["symbol"],
                timeframe,
                item["market"],
                source_hint=source_hint,
            )
        except FileNotFoundError as exc:
            print(f"SKIP {item['symbol']} {item['timeframe']} period={period} {result_dir}: {exc}")
            log_items.append({**item, "status": "skipped", "period": period, "error": str(exc)})
            skipped += 1
            continue

        if args.dry_run:
            print(f"DRY {item['symbol']} {item['timeframe']} period={period} source={source_csv} -> {result_dir}")
            log_items.append({**item, "status": "dry_run", "period": period, "source_csv": str(source_csv)})
            ok += 1
            continue

        try:
            snapshots, stats = build_from_result_dir(
                result_dir,
                data_dir=data_dir_for_item,
                market=item["market"],
                symbol=item["symbol"],
                timeframe=timeframe,
                source_hint=source_hint,
            )
            write_outputs(result_dir, snapshots, stats)
            print(
                f"OK {item['symbol']} {item['timeframe']} period={period} "
                f"snapshots={len(snapshots)} buckets={len(stats)} source={source_csv}"
            )
            log_items.append(
                {
                    **item,
                    "status": "ok",
                    "period": period,
                    "source_csv": str(source_csv),
                    "snapshots": len(snapshots),
                    "buckets": len(stats),
                }
            )
            ok += 1
        except Exception as exc:
            print(f"FAIL {item['symbol']} {item['timeframe']} period={period} {result_dir}: {exc}")
            log_items.append(
                {**item, "status": "error", "period": period, "source_csv": str(source_csv), "error": str(exc)}
            )
            fail += 1

    summary = {
        "targets": len(targets),
        "inventory_items": len(inventory),
        "ok": ok,
        "skipped": skipped,
        "fail": fail,
        "items": log_items,
    }
    Path(args.log).write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"done ok={ok} skipped={skipped} fail={fail} log={args.log}")
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
