#!/usr/bin/env python
"""Classify context-stats batch failures without fabricating missing market data."""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages" / "fengji_core"))

from fengji_core.context_stats import infer_crypto_period_from_hint, resolve_data_csv  # noqa: E402

DEFAULT_INPUT = ROOT / "results" / "context_stats_failures.json"
DEFAULT_OUT_DIR = ROOT / "results"


def _extract_a_stock_code(result_dir: str) -> str | None:
    m = re.search(r"(?:^|[_\\/])(\d{6})(?:[_\\/]|$)", result_dir)
    return m.group(1) if m else None


def _crypto_okx_candidates(symbol: str) -> list[str]:
    base = symbol.upper().replace("USDT", "")
    okx_symbol = f"{base}-USDT"
    folder = ROOT / "data" / "crypto_okx"
    if not folder.exists():
        return []
    return [str(p.relative_to(ROOT)) for p in sorted(folder.glob(f"{okx_symbol}_1D_*.csv"))]


def _csv_row_count(path: Path) -> int:
    if not path.exists():
        return 0
    try:
        with path.open("r", encoding="utf-8-sig") as fh:
            return max(0, sum(1 for _ in fh) - 1)
    except OSError:
        return 0


def _run_id_from_realtime_dir(result_dir: str) -> str | None:
    parts = Path(result_dir).parts
    for idx, part in enumerate(parts):
        if part == "crypto_realtime_monitor" and idx + 1 < len(parts):
            return parts[idx + 1]
    return None


def _asof_data_dir(result_dir: str) -> Path | None:
    run_id = _run_id_from_realtime_dir(result_dir)
    if not run_id:
        return None
    path = ROOT / "data" / "crypto_okx_asof" / run_id
    return path if path.exists() else None


def _classify_item(item: dict[str, Any]) -> dict[str, Any]:
    result_dir = str(item.get("result_dir", ""))
    market = str(item.get("market", "")).upper()
    symbol = str(item.get("symbol", "")).upper()
    snapshots_path = Path(result_dir) / "trade_context_snapshots.csv"
    out = {
        "result_dir": result_dir,
        "market": market,
        "symbol": symbol,
        "trade_count": int(item.get("trade_count") or 0),
        "original_error": str(item.get("error", "")),
        "classification": "UNCLASSIFIED",
        "action": "manual review",
        "evidence": {},
    }

    if market == "A_STOCK":
        code = _extract_a_stock_code(result_dir)
        data_exists = bool(code and (ROOT / "data" / "a_stock" / f"{code}_1D_qfq.csv").exists())
        out["evidence"] = {
            "inferred_symbol": code,
            "data_file_exists": data_exists,
            "snapshots_exist": snapshots_path.exists(),
        }
        if code and data_exists and snapshots_path.exists():
            out["classification"] = "RECOVERED_SYMBOL_PARSE"
            out["action"] = "no further action; snapshots now exist"
        elif code and data_exists:
            out["classification"] = "RECOVERABLE_SYMBOL_PARSE"
            out["action"] = f"rebuild with --symbol {code} --data-dir data/a_stock"
        else:
            out["classification"] = "NEEDS_A_STOCK_DATA_OR_SYMBOL"
            out["action"] = "verify result directory symbol and local A-share CSV"
        return out

    if market == "CRYPTO":
        candidates = _crypto_okx_candidates(symbol)
        rows = _csv_row_count(snapshots_path)
        asof_dir = _asof_data_dir(result_dir)
        source_hint: str | Path | None = result_dir
        data_root = ROOT / "data"
        timeframe = str(item.get("timeframe", "1d"))
        if asof_dir is not None:
            source_hint = f"{result_dir}_180d"
            data_root = asof_dir
            timeframe = "15m"
        period = infer_crypto_period_from_hint(source_hint)
        exact_source = None
        exact_error = ""
        try:
            exact_source = resolve_data_csv(
                data_root,
                symbol,
                timeframe,
                "CRYPTO",
                source_hint=source_hint,
            )
        except FileNotFoundError as exc:
            exact_error = str(exc)
        out["evidence"] = {
            "okx_1d_candidates": candidates,
            "snapshots_exist": snapshots_path.exists(),
            "snapshot_rows": rows,
            "inferred_period": period,
            "exact_source_csv": str(exact_source.relative_to(ROOT)) if exact_source else None,
        }
        if snapshots_path.exists() and rows > 0:
            out["classification"] = "REBUILT_PERIOD_AWARE_CRYPTO"
            out["action"] = "no further action; period-aware snapshots now exist"
        elif snapshots_path.exists():
            out["classification"] = "REBUILT_EMPTY_CONTEXT"
            out["action"] = "rebuilt with exact period CSV, but no trades aligned to OS frame by entry_idx"
        elif exact_source is not None:
            out["classification"] = "RECOVERABLE_PERIOD_AWARE_CRYPTO"
            out["action"] = f"rebuild with exact source {exact_source.relative_to(ROOT)}"
        elif period is None and "crypto_realtime_monitor" in result_dir.replace("\\", "/").lower():
            out["classification"] = "MISSING_ORIGINAL_REALTIME_WINDOW"
            out["action"] = (
                "the monitor script defaulted to 180d, but this run needs the original as-of cache window; "
                "current 180d CSV has a different start date and would shift entry_idx"
            )
        elif candidates:
            out["classification"] = "MISSING_EXACT_PERIOD_CRYPTO_CSV"
            out["action"] = (
                "local OKX CSV exists for other windows, but exact source window is missing; "
                f"reason: {exact_error}"
            )
        else:
            out["classification"] = "MISSING_LOCAL_CRYPTO_CSV"
            out["action"] = "fetch or restore matching OHLCV CSV before rebuilding"
        return out

    if market == "FUTURES":
        probable_symbol = Path(result_dir).name
        futures_dir_exists = (ROOT / "data" / "futures").exists()
        rows = _csv_row_count(snapshots_path)
        timeframe = str(item.get("timeframe", "1d"))
        source_csv = None
        source_error = ""
        try:
            source_csv = resolve_data_csv(
                ROOT / "data" / "futures",
                probable_symbol,
                timeframe,
                "FUTURES",
                source_hint=result_dir,
            )
        except FileNotFoundError as exc:
            source_error = str(exc)
        out["evidence"] = {
            "probable_symbol_from_dir": probable_symbol,
            "data_futures_dir_exists": futures_dir_exists,
            "snapshots_exist": snapshots_path.exists(),
            "snapshot_rows": rows,
            "source_csv": str(source_csv.relative_to(ROOT)) if source_csv else None,
        }
        if snapshots_path.exists() and rows > 0:
            out["classification"] = "REBUILT_FUTURES_CONTEXT"
            out["action"] = "no further action; futures snapshots now exist"
        elif source_csv is not None:
            out["classification"] = "RECOVERABLE_FUTURES_CONTEXT"
            out["action"] = f"rebuild with source {source_csv.relative_to(ROOT)}"
        else:
            out["classification"] = "NEEDS_FUTURES_SYMBOL_MAPPING_AND_SOURCE_DATA"
            out["action"] = (
                "result directory names identify products, but source CSV is still missing; "
                f"reason: {source_error}"
            )
        return out

    return out


def _markdown_report(items: list[dict[str, Any]]) -> str:
    counts = Counter(str(i["classification"]) for i in items)
    by_market = Counter(str(i["market"]) for i in items)
    lines = [
        "# Context Stats Failure Audit 2026-06-02",
        "",
        "## Summary",
        "",
        f"- Total failed items audited: {len(items)}",
        f"- By market: `{json.dumps(dict(by_market), ensure_ascii=False)}`",
        f"- By classification: `{json.dumps(dict(counts), ensure_ascii=False)}`",
        "",
        "## Decisions",
        "",
        "- A_STOCK symbol parse failures are recoverable when a six-digit code and matching local CSV exist.",
        "- CRYPTO failures must use exact period-aware `data/crypto_okx` CSVs because context snapshots align by `entry_idx`.",
        "- FUTURES failures are recoverable after product-name daily CSVs are materialized under `data/futures/1d`.",
        "",
        "## Items",
        "",
        "| market | symbol | trades | classification | action | result_dir |",
        "| --- | --- | ---: | --- | --- | --- |",
    ]
    for item in items:
        action = str(item["action"]).replace("|", "/")
        result_dir = str(item["result_dir"]).replace(str(ROOT), ".")
        lines.append(
            f"| {item['market']} | {item['symbol']} | {item['trade_count']} | "
            f"{item['classification']} | {action} | `{result_dir}` |"
        )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit context stats failure causes and safe next actions.")
    parser.add_argument("--input", default=str(DEFAULT_INPUT))
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR))
    args = parser.parse_args()

    source = Path(args.input)
    payload = json.loads(source.read_text(encoding="utf-8"))
    items = [_classify_item(item) for item in payload.get("items", [])]
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "context_stats_failure_audit_2026-06-02.json"
    md_path = out_dir / "context_stats_failure_audit_2026-06-02.md"
    summary = {
        "source": str(source),
        "total": len(items),
        "by_market": dict(Counter(str(i["market"]) for i in items)),
        "by_classification": dict(Counter(str(i["classification"]) for i in items)),
        "items": items,
    }
    json_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(_markdown_report(items), encoding="utf-8")
    print(f"saved_json={json_path}")
    print(f"saved_report={md_path}")
    print(json.dumps(summary["by_classification"], ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
