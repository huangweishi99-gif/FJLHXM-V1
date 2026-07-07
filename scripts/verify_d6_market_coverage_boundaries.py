#!/usr/bin/env python3
"""D6 验收：A股 60m 覆盖审计 · 期货日夜盘表完整性 · 边界文档。"""
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages" / "fengji_core"))

from fengji_core.market_coverage import (  # noqa: E402
    A_STOCK_H1_MIN_ROWS_DS07_DS08,
    FUTURES_NIGHT_END_BY_SYMBOL,
    filter_strategies_for_a_stock_data,
    futures_symbols_missing_night_map,
    h1_eligible_for_ds07_ds08,
)

# 与 data_manager_futures.TQ_SYMBOL_MAP 保持同步（模拟盘 34 品种）
FUTURES_SYMBOLS = sorted(
    {
        "SA", "FG", "CJ", "OI", "SH", "SR", "SF", "MA", "TA", "UR", "CF",
        "RB", "FU", "SP", "NI", "AO", "RU", "BR", "AU", "AG",
        "PG", "LH", "JD", "PP", "EB", "EG", "JM", "M", "P", "V",
        "SI", "LC", "EC", "SC",
    }
)


def fail(msg: str) -> None:
    print(f"D6_VERIFY_FAIL: {msg}")
    sys.exit(1)


def audit_a_stock_h1(cache_dir: Path) -> dict:
    files = sorted(cache_dir.glob("*_60m_qfq.csv"))
    rows_out: list[dict] = []
    for path in files:
        code = path.name.split("_", 1)[0]
        try:
            df = pd.read_csv(path, usecols=["date"])
            n = len(df)
        except Exception:
            n = 0
        tier = "full_h1" if h1_eligible_for_ds07_ds08(n) else ("partial_h1" if n > 0 else "missing")
        rows_out.append({"code": code, "h1_rows": n, "tier": tier})
    full = sum(1 for r in rows_out if r["tier"] == "full_h1")
    partial = sum(1 for r in rows_out if r["tier"] == "partial_h1")
    return {
        "cache_dir": str(cache_dir),
        "files": len(files),
        "full_h1": full,
        "partial_h1": partial,
        "missing": sum(1 for r in rows_out if r["tier"] == "missing"),
        "threshold": A_STOCK_H1_MIN_ROWS_DS07_DS08,
        "samples_partial": [r for r in rows_out if r["tier"] == "partial_h1"][:8],
        "samples_full": [r for r in rows_out if r["tier"] == "full_h1"][:8],
    }


def check_docs() -> None:
    doc = ROOT / "docs" / "MARKET_COVERAGE_BOUNDARIES.md"
    if not doc.is_file():
        fail("缺少 docs/MARKET_COVERAGE_BOUNDARIES.md")
    text = doc.read_text(encoding="utf-8")
    for token in ("500", "FUTURES_WINDOWS", "23:00", "02:30", "无夜盘"):
        if token not in text:
            fail(f"MARKET_COVERAGE_BOUNDARIES.md 未提及 {token}")


def check_futures_night_map() -> None:
    missing = futures_symbols_missing_night_map(FUTURES_SYMBOLS)
    if missing:
        fail(f"期货夜盘表缺品种: {missing}")
    if len(FUTURES_NIGHT_END_BY_SYMBOL) < len(FUTURES_SYMBOLS):
        fail("FUTURES_NIGHT_END_BY_SYMBOL 条目少于模拟盘品种数")


def check_strategy_filter_smoke() -> None:
    allowed, skipped = filter_strategies_for_a_stock_data(
        ["DS01", "DS07", "DS08", "DS09"],
        h1_rows=128,
        m15_rows=0,
    )
    if allowed != ["DS01"]:
        fail(f"128 根 H1 应仅保留 DS01，实际 {allowed}")
    if not skipped:
        fail("应有跳过原因")


def write_report(a_stock: dict) -> Path:
    out_dir = ROOT / "results" / "sandbox" / f"d6_phase2_{datetime.now():%Y%m%d}"
    out_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "a_stock_h1": a_stock,
        "futures_symbols": len(FUTURES_SYMBOLS),
        "futures_night_map_size": len(FUTURES_NIGHT_END_BY_SYMBOL),
    }
    (out_dir / "d6_report.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    summary = [
        "# D6 市场覆盖边界验收",
        "",
        f"- 生成时间：{payload['generated_at']}",
        f"- A股 60m 文件：{a_stock['files']} · full={a_stock['full_h1']} · partial={a_stock['partial_h1']}",
        f"- H1 门槛：≥{a_stock['threshold']} 根方可 DS07/DS08",
        f"- 期货夜盘表：{payload['futures_night_map_size']} 品种",
        "",
        "详见 `docs/MARKET_COVERAGE_BOUNDARIES.md`。",
    ]
    (out_dir / "SUMMARY.md").write_text("\n".join(summary) + "\n", encoding="utf-8")
    return out_dir


def main() -> None:
    check_docs()
    check_futures_night_map()
    check_strategy_filter_smoke()
    cache = ROOT / "data" / "a_stock"
    a_stock = audit_a_stock_h1(cache) if cache.is_dir() else {"files": 0, "full_h1": 0, "partial_h1": 0}
    out_dir = write_report(a_stock)
    print(f"D6 report: {out_dir}")
    print("D6_VERIFY_OK")


if __name__ == "__main__":
    main()
