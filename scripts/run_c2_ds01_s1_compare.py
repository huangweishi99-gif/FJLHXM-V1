#!/usr/bin/env python3
"""Wave 3 C2: DS01 S1 后选择性重跑 — 对比 accepted_trades 中 DS01 笔数 vs 当前引擎重跑。

只读对比 + 可选写出 rerun 清单；不自动覆盖 results/ 产物。

Usage:
  python scripts/run_c2_ds01_s1_compare.py --market CRYPTO
  python scripts/run_c2_ds01_s1_compare.py --market FUTURES --limit 10
  python scripts/run_c2_ds01_s1_compare.py --market A_STOCK --limit 20 --dry-run
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "packages" / "fengji_core"))

from audit_coverage_gaps import match_key  # noqa: E402
from backtest_ds01 import DS01BacktestConfig, run_ds01_backtest  # noqa: E402
from chart_symbol_catalog import list_local_chart_symbols  # noqa: E402
from discover_backtest_results import discover  # noqa: E402
from fengji_core.context_stats import resolve_data_csv  # noqa: E402
from quant.data import load_ohlcv_for_engine  # noqa: E402
from quant.futures_specs import get_futures_spec  # noqa: E402


def find_accepted(result_dir: Path) -> Path | None:
    for rel in ("accepted_trades.csv", "raw_fengji/accepted_trades.csv", "stock_long_accepted_trades.csv"):
        path = result_dir / rel
        if path.exists():
            return path
    return None


def count_ds01_trades(accepted_path: Path) -> int:
    df = pd.read_csv(accepted_path)
    if df.empty or "strategy_id" not in df.columns:
        return int(len(df))
    return int((df["strategy_id"].astype(str).str.upper() == "DS01").sum())


def dedupe_by_symbol(items: list[dict], *, catalog_only: bool, market: str) -> list[dict]:
    """每个 match_key 只保留一个主结果目录（与 C0 load_backtest_index 口径一致）。"""
    catalog_keys: set[str] | None = None
    if catalog_only:
        catalog_keys = {match_key(market, s) for s in list_local_chart_symbols(market)}

    best: dict[str, dict] = {}
    for item in items:
        sym = str(item.get("symbol", ""))
        if not sym:
            continue
        key = match_key(market, sym)
        if catalog_keys is not None and key not in catalog_keys:
            continue
        rd = Path(item["result_dir"])
        item = dict(item)
        item["_has_context"] = (rd / "trade_context_snapshots.csv").exists()
        score = (
            1 if "plan_a_" in str(item["result_dir"]).lower() else 0,
            1 if item["_has_context"] else 0,
            int(item.get("trade_count") or 0),
        )
        prev = best.get(key)
        if prev is None or score > prev["_score"]:
            item["_score"] = score
            best[key] = item
    out = sorted(best.values(), key=lambda x: match_key(market, str(x["symbol"])))
    for row in out:
        row.pop("_score", None)
        row.pop("_has_context", None)
    return out


def resolve_data_root(market: str, item: dict) -> Path:
    market = market.upper()
    if market == "A_STOCK":
        return ROOT / "data" / "a_stock"
    if market == "US_STOCK":
        return ROOT / "data" / "us_stock"
    if market == "FUTURES":
        rel = str(item.get("data_dir") or "data/futures")
        return ROOT / rel if not Path(rel).is_absolute() else Path(rel)
    return ROOT / "data"


def futures_csv_symbol(item: dict) -> str:
    """回测目录名（中文/PTA）优先于 catalog 推断 symbol。"""
    name = Path(item["result_dir"]).name
    if name:
        return name
    return str(item.get("symbol") or "")


def rerun_ds01_count(market: str, symbol: str, data_dir: Path, timeframe: str, *, source_hint: Path | None = None) -> int:
    csv_path = resolve_data_csv(data_dir, symbol, timeframe, market, source_hint=source_hint)
    spec = get_futures_spec(csv_path) if market == "FUTURES" else None
    config = DS01BacktestConfig(
        futures_mode=market == "FUTURES",
        spec=spec,
        gap=3,
        atr_window=14,
    )
    df = load_ohlcv_for_engine(csv_path, config.atr_window)
    result = run_ds01_backtest(df, config)
    return int(len(result["trades"]))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="C2: compare baseline DS01 trade count vs S1 engine rerun.")
    parser.add_argument("--root", default=str(ROOT / "results"))
    parser.add_argument("--market", required=True, choices=["A_STOCK", "FUTURES", "CRYPTO", "US_STOCK"])
    parser.add_argument("--limit", type=int, default=0, help="Max symbols (0=all discovered)")
    parser.add_argument("--catalog-only", action=argparse.BooleanOptionalAction, default=True, help="Only catalog symbols, one dir per match_key")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--out", default=str(ROOT / "results" / "c2_ds01_s1_compare.json"))
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    market = args.market.upper()
    raw = [i for i in discover(Path(args.root)) if i["market"] == market and int(i.get("trade_count") or 0) > 0]
    items = dedupe_by_symbol(raw, catalog_only=args.catalog_only, market=market)
    if args.limit > 0:
        items = items[: args.limit]

    print(f"C2 {market} dirs={len(raw)} unique={len(items)} catalog_only={args.catalog_only}")

    rows: list[dict] = []
    failures = 0
    for item in items:
        symbol = str(item["symbol"])
        result_dir = Path(item["result_dir"])
        data_dir = resolve_data_root(market, item)
        accepted = find_accepted(result_dir)
        if accepted is None:
            failures += 1
            rows.append({"market": market, "symbol": symbol, "status": "error", "error": "no accepted_trades"})
            continue
        baseline = count_ds01_trades(accepted)
        row = {
            "market": market,
            "symbol": symbol,
            "result_dir": str(result_dir),
            "baseline_ds01": baseline,
            "rerun_ds01": None,
            "delta": None,
            "status": "pending",
        }
        if args.dry_run:
            row["status"] = "dry_run"
            rows.append(row)
            continue
        try:
            sym = futures_csv_symbol(item) if market == "FUTURES" else symbol
            rerun = rerun_ds01_count(
                market,
                sym,
                data_dir,
                str(item.get("timeframe") or "1d"),
                source_hint=result_dir,
            )
            row["rerun_ds01"] = rerun
            row["delta"] = rerun - baseline
            row["status"] = "ok"
        except Exception as exc:  # noqa: BLE001
            failures += 1
            row["status"] = "error"
            row["error"] = str(exc)
        rows.append(row)
        tag = "DELTA" if row.get("delta") not in (None, 0) else "OK"
        print(f"{tag} {symbol} baseline={baseline} rerun={row.get('rerun_ds01')} delta={row.get('delta')}")

    changed = [r for r in rows if r.get("delta") not in (None, 0)]
    summary = {
        "market": market,
        "dirs_discovered": len(raw),
        "symbols_compared": len(rows),
        "scanned": len(rows),
        "changed": len(changed),
        "errors": failures,
        "catalog_only": args.catalog_only,
        "items": rows,
    }
    out_path = Path(args.out)
    if args.market != "CRYPTO" or len(rows) > 1:
        out_path = out_path.with_name(f"c2_ds01_s1_compare_{market.lower()}.json")
    out_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"C2 {market} scanned={len(rows)} changed={len(changed)} errors={failures} -> {out_path}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
