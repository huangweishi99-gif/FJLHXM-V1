#!/usr/bin/env python
"""Wave 1 C0: CSV catalog × backtest results × context × PG coverage gap report."""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "services"))
sys.path.insert(0, str(ROOT / "packages" / "fengji_core"))
sys.path.insert(0, str(ROOT / "scripts"))

from chart_symbol_catalog import (  # noqa: E402
    _futures_match_key,
    _symbol_match_key,
    list_local_chart_symbols,
)
from discover_backtest_results import discover, context_snapshots_ready  # noqa: E402

MARKETS = ("A_STOCK", "FUTURES", "CRYPTO", "US_STOCK")


def match_key(market: str, symbol: str) -> str:
    return _symbol_match_key(market, symbol)


def load_backtest_index(results_root: Path) -> dict[str, dict[str, dict]]:
    """market -> match_key -> {result_dir, trade_count, has_context_csv}."""
    index: dict[str, dict[str, dict]] = {m: {} for m in MARKETS}
    for row in discover(results_root):
        market = str(row.get("market", "UNKNOWN")).upper()
        if market not in index:
            continue
        sym = str(row.get("symbol", ""))
        if not sym:
            continue
        key = match_key(market, sym)
        trade_count = int(row.get("trade_count") or 0)
        result_dir = Path(row["result_dir"])
        has_ctx = context_snapshots_ready(result_dir)
        prev = index[market].get(key)
        if prev is None or trade_count > int(prev.get("trade_count") or 0):
            index[market][key] = {
                "symbol": sym,
                "result_dir": str(result_dir),
                "trade_count": trade_count,
                "has_context_csv": has_ctx,
            }
    return index


def load_pg_index() -> tuple[dict[str, set[str]], str | None]:
    """market -> set of match_keys; error message if PG unavailable."""
    try:
        from sqlalchemy import func, select
        from sqlalchemy.orm import Session

        from db.models import TradeContextSnapshot
        from db.session import get_engine

        out: dict[str, set[str]] = {m: set() for m in MARKETS}
        with Session(get_engine()) as session:
            rows = session.execute(
                select(
                    TradeContextSnapshot.market,
                    TradeContextSnapshot.symbol,
                    func.count(),
                ).group_by(TradeContextSnapshot.market, TradeContextSnapshot.symbol)
            ).all()
        for market, symbol, _ in rows:
            mkt = str(market).upper()
            if mkt not in out:
                continue
            out[mkt].add(match_key(mkt, str(symbol)))
        return out, None
    except Exception as exc:
        return {m: set() for m in MARKETS}, str(exc)


def build_report(results_root: Path, include_pg: bool) -> dict:
    csv_by_market = {m: {match_key(m, s) for s in list_local_chart_symbols(m)} for m in MARKETS}
    backtest = load_backtest_index(results_root)
    pg_index, pg_error = load_pg_index() if include_pg else ({m: set() for m in MARKETS}, "skipped")

    markets_out: dict[str, dict] = {}
    totals = defaultdict(int)

    for market in MARKETS:
        csv_keys = csv_by_market[market]
        bt_keys = set(backtest[market].keys())
        pg_keys = pg_index[market]

        csv_only: list[str] = []
        backtest_no_context: list[str] = []
        context_no_pg: list[str] = []
        complete: list[str] = []

        for key in sorted(csv_keys):
            bt = backtest[market].get(key)
            in_pg = key in pg_keys
            if bt is None or int(bt.get("trade_count") or 0) <= 0:
                csv_only.append(key)
                totals["csv_only"] += 1
                continue
            if not bt.get("has_context_csv"):
                backtest_no_context.append(key)
                totals["backtest_no_context"] += 1
                continue
            if include_pg and not pg_error and not in_pg:
                context_no_pg.append(key)
                totals["context_no_pg"] += 1
                continue
            complete.append(key)
            totals["complete"] += 1

        # backtest dirs not in csv catalog (informational)
        backtest_only = sorted(bt_keys - csv_keys)

        markets_out[market] = {
            "csv_count": len(csv_keys),
            "backtest_count": len(bt_keys),
            "pg_count": len(pg_keys) if not pg_error else None,
            "complete_count": len(complete),
            "csv_only_count": len(csv_only),
            "backtest_no_context_count": len(backtest_no_context),
            "context_no_pg_count": len(context_no_pg),
            "csv_only_sample": csv_only[:20],
            "backtest_no_context_sample": backtest_no_context[:20],
            "context_no_pg_sample": context_no_pg[:20],
            "complete_sample": complete[:10],
            "backtest_only_catalog_missing_sample": backtest_only[:10],
        }

    return {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "results_root": str(results_root),
        "pg_available": pg_error is None,
        "pg_error": pg_error,
        "totals": dict(totals),
        "markets": markets_out,
    }


def render_markdown(report: dict) -> str:
    lines = [
        "# 四市场样本覆盖缺口报告（Wave 1 · C0）",
        "",
        f"生成时间：{report['generated_at']}",
        "",
        "## 汇总",
        "",
        "| 市场 | CSV | 回测目录 | PG 品种 | 完整链路 | 仅CSV | 缺context | 缺PG |",
        "|------|-----|----------|---------|----------|-------|-----------|------|",
    ]
    for market in MARKETS:
        m = report["markets"][market]
        pg_c = m["pg_count"] if m["pg_count"] is not None else "N/A"
        lines.append(
            f"| {market} | {m['csv_count']} | {m['backtest_count']} | {pg_c} | "
            f"{m['complete_count']} | {m['csv_only_count']} | {m['backtest_no_context_count']} | {m['context_no_pg_count']} |"
        )
    lines.extend(
        [
            "",
            f"**PG 可用**：{'是' if report['pg_available'] else '否'}",
        ]
    )
    if report.get("pg_error") and report["pg_error"] != "skipped":
        lines.append(f"**PG 错误**：{report['pg_error']}")
    lines.extend(
        [
            "",
            "## 解读",
            "",
            "- **仅 CSV**：有 K 线、无回测产物 → Wave 3 **C1 增量回测**",
            "- **缺 context**：有回测、无 `trade_context_snapshots.csv` → Wave 2 **C3**",
            "- **缺 PG**：有 context CSV、未导入 PG → Wave 2 **C4**",
            "- **完整链路**：CSV + 回测 + context（+ PG）",
            "",
            "## 各市场缺口样例（前 20）",
            "",
        ]
    )
    for market in MARKETS:
        m = report["markets"][market]
        lines.append(f"### {market}")
        lines.append(f"- 仅 CSV（{m['csv_only_count']}）：{', '.join(m['csv_only_sample']) or '—'}")
        lines.append(f"- 缺 context（{m['backtest_no_context_count']}）：{', '.join(m['backtest_no_context_sample']) or '—'}")
        if report["pg_available"]:
            lines.append(f"- 缺 PG（{m['context_no_pg_count']}）：{', '.join(m['context_no_pg_sample']) or '—'}")
        lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Coverage gap: CSV vs backtest vs context vs PG.")
    parser.add_argument("--root", default=str(ROOT))
    parser.add_argument("--results", default=str(ROOT / "results"))
    parser.add_argument("--no-pg", action="store_true")
    parser.add_argument("--json-out", default=str(ROOT / "results" / "coverage_gap_report.json"))
    parser.add_argument("--md-out", default=str(ROOT / "results" / "coverage_gap_report.md"))
    args = parser.parse_args()

    report = build_report(Path(args.results), include_pg=not args.no_pg)
    json_path = Path(args.json_out)
    md_path = Path(args.md_out)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(render_markdown(report), encoding="utf-8")

    print(f"C0 report json={json_path} md={md_path}")
    for market in MARKETS:
        m = report["markets"][market]
        print(
            f"  {market}: csv={m['csv_count']} backtest={m['backtest_count']} "
            f"complete={m['complete_count']} csv_only={m['csv_only_count']} "
            f"no_ctx={m['backtest_no_context_count']} no_pg={m['context_no_pg_count']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
