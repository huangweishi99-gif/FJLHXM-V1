#!/usr/bin/env python3
"""Plan B B0-2: reconcile SQLite coverage vs instruments API / coverage CSV."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import pandas as pd  # noqa: E402

PLAN_A_MIN = {
    "CRYPTO": {"symbols": 10, "timeframes": {"1D", "1H", "15m"}},
    "FUTURES": {"symbols": 69, "timeframes": {"1D", "1H", "15m", "5m"}},
    "A_STOCK": {"symbols": 239, "timeframes": {"1D"}},
}


def load_sqlite_coverage(db: Path) -> pd.DataFrame:
    import sqlite3

    from market_data_store import coverage

    conn = sqlite3.connect(db)
    try:
        return coverage(conn)
    finally:
        conn.close()


def summarize(frame: pd.DataFrame) -> dict[str, dict]:
    out: dict[str, dict] = {}
    if frame.empty:
        return out
    for market, grp in frame.groupby("market"):
        symbols = sorted(grp["symbol"].unique())
        tfs = sorted(grp["timeframe"].unique())
        out[str(market)] = {
            "symbol_count": len(symbols),
            "timeframes": tfs,
            "rows_total": int(grp["rows"].sum()),
        }
    return out


def try_pg_instruments(market: str | None, limit: int = 500) -> list[dict] | None:
    try:
        sys.path.insert(0, str(ROOT / "services"))
        from db.queries import list_instruments

        return list_instruments(market=market, limit=limit, offset=0)
    except Exception:
        return None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default=str(ROOT / "data" / "market_data.sqlite"))
    parser.add_argument("--coverage-csv", default=str(ROOT / "data" / "market_data_coverage.csv"))
    parser.add_argument("--out", default=str(ROOT / "results" / "plan_b_b02_instruments_coverage"))
    args = parser.parse_args()

    db = Path(args.db)
    if not db.is_file():
        print(f"missing db: {db}", file=sys.stderr)
        return 1

    sqlite_frame = load_sqlite_coverage(db)
    sqlite_summary = summarize(sqlite_frame)

    csv_frame = pd.read_csv(args.coverage_csv) if Path(args.coverage_csv).is_file() else pd.DataFrame()
    csv_summary = summarize(csv_frame) if not csv_frame.empty else {}

    gaps: dict[str, dict] = {}
    if not sqlite_frame.empty:
        for market, expect in PLAN_A_MIN.items():
            mframe = sqlite_frame[sqlite_frame["market"] == market]
            if mframe.empty:
                gaps[market] = {"missing_timeframes": sorted(expect["timeframes"]), "timeframe_gaps": {}}
                continue
            have_tfs = set(mframe["timeframe"].unique())
            missing_tfs = sorted(expect["timeframes"] - have_tfs)
            tf_gaps: dict[str, int] = {}
            for tf in expect["timeframes"]:
                have = set(mframe.loc[mframe["timeframe"] == tf, "symbol"].unique())
                all_syms = set(mframe["symbol"].unique())
                missing = sorted(all_syms - have)
                if missing:
                    tf_gaps[tf] = len(missing)
            gaps[market] = {
                "missing_timeframes": missing_tfs,
                "timeframe_gaps": tf_gaps,
            }

    checks: list[dict] = []
    for market, expect in PLAN_A_MIN.items():
        got = sqlite_summary.get(market, {})
        sym_ok = got.get("symbol_count", 0) >= expect["symbols"]
        tf_set = set(got.get("timeframes") or [])
        tf_ok = expect["timeframes"].issubset(tf_set) if expect["timeframes"] else True
        checks.append(
            {
                "market": market,
                "expect_symbols": expect["symbols"],
                "sqlite_symbols": got.get("symbol_count", 0),
                "expect_timeframes": sorted(expect["timeframes"]),
                "sqlite_timeframes": got.get("timeframes", []),
                "pass": sym_ok and tf_ok,
                "gaps": gaps.get(market, {}),
            }
        )

    pg_crypto = try_pg_instruments("CRYPTO")
    pg_note = "ok" if pg_crypto is not None else "skipped (no PG)"

    report = {
        "sqlite_summary": sqlite_summary,
        "csv_summary": csv_summary,
        "plan_a_checks": checks,
        "coverage_gaps": gaps,
        "pg_instruments_crypto": len(pg_crypto) if pg_crypto else None,
        "pg_status": pg_note,
        "pass": all(c["pass"] for c in checks),
    }

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "B02_RECONCILE.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "# Plan B B0-2 · instruments / coverage 对账",
        "",
        f"SQLite：`{db}`",
        "",
        "| 市场 | 期望品种 | SQLite | 周期 OK |",
        "|------|----------|--------|---------|",
    ]
    for c in checks:
        flag = "✅" if c["pass"] else "❌"
        lines.append(
            f"| {c['market']} | {c['expect_symbols']} | {c['sqlite_symbols']} | {flag} |"
        )
    lines.extend(["", "## 缺口明细", ""])
    for c in checks:
        g = c.get("gaps") or {}
        missing_tfs = g.get("missing_timeframes") or []
        tf_gaps = g.get("timeframe_gaps") or {}
        if missing_tfs:
            lines.append(f"- **{c['market']}** 缺整周期：`{', '.join(missing_tfs)}`")
        for tf, n in sorted(tf_gaps.items()):
            lines.append(f"- **{c['market']}** `{tf}` 缺 **{n}** 品种")
    lines.extend(["", f"PG instruments (CRYPTO)：`{pg_note}`", ""])
    (out / "B02_RECONCILE.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(json.dumps({"pass": report["pass"], "checks": checks, "pg": pg_note}, ensure_ascii=False, indent=2))
    return 0 if report["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
