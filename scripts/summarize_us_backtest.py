#!/usr/bin/env python
"""汇总美股 11 板块回测 us_summary.csv。"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ROOT = ROOT / "results" / "fengji_total_us_stock_sectors"


def load_summaries(root: Path) -> pd.DataFrame:
    rows: list[dict] = []
    for path in root.rglob("us_summary.csv"):
        df = pd.read_csv(path)
        if df.empty:
            continue
        r = df.iloc[0].to_dict()
        r["ticker"] = path.parent.name.split("_")[0]
        parts = path.parts
        idx = parts.index("fengji_total_us_stock_sectors")
        r["sector_dir"] = parts[idx + 1]
        rows.append(r)
    return pd.DataFrame(rows)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=str(DEFAULT_ROOT))
    parser.add_argument("--out", default=str(DEFAULT_ROOT / "us_backtest_aggregate.csv"))
    args = parser.parse_args()

    df = load_summaries(Path(args.root))
    if df.empty:
        print("no us_summary.csv found")
        return 1

    df["ret"] = pd.to_numeric(df["total_return"], errors="coerce")
    df["wr"] = pd.to_numeric(df["win_rate"], errors="coerce")
    df["mdd"] = pd.to_numeric(df["max_drawdown"], errors="coerce")
    df["trades_n"] = pd.to_numeric(df["trades"], errors="coerce")
    df["bad_audits_n"] = pd.to_numeric(df.get("bad_audits", 0), errors="coerce").fillna(0)

    print(f"=== 全池汇总 ({len(df)} 只) ===")
    print(f"平均收益: {df['ret'].mean() * 100:.2f}%")
    print(f"中位收益: {df['ret'].median() * 100:.2f}%")
    print(f"盈利票占比: {(df['ret'] > 0).mean() * 100:.1f}%")
    print(f"平均胜率: {df['wr'].mean() * 100:.1f}%")
    print(f"平均最大回撤: {df['mdd'].mean() * 100:.2f}%")
    print(f"平均成交笔数: {df['trades_n'].mean():.0f}")
    print(f"bad_audits 合计: {int(df['bad_audits_n'].sum())}")

    sec = (
        df.groupby("sector_dir", as_index=False)
        .agg(
            n=("ret", "count"),
            avg_ret=("ret", "mean"),
            med_ret=("ret", "median"),
            pct_pos=("ret", lambda s: (s > 0).mean()),
            avg_wr=("wr", "mean"),
            avg_mdd=("mdd", "mean"),
            avg_trades=("trades_n", "mean"),
        )
        .sort_values("avg_ret", ascending=False)
    )
    sec.to_csv(args.out, index=False, encoding="utf-8-sig")

    print("\n=== 板块排名（平均收益） ===")
    for _, row in sec.iterrows():
        label = row["sector_dir"].replace("_GICS", " ").split("_")[0]
        print(
            f"{label:28s} n={int(row.n):2d} "
            f"avg={row.avg_ret * 100:7.2f}% med={row.med_ret * 100:7.2f}% "
            f"盈利票={row.pct_pos * 100:4.0f}% wr={row.avg_wr * 100:4.1f}% "
            f"mdd={row.avg_mdd * 100:6.2f}% trades={row.avg_trades:.0f}"
        )

    print("\n=== Top 10 ===")
    for _, r in df.nlargest(10, "ret").iterrows():
        print(
            f"{r['ticker']:6s} ret={r['ret'] * 100:7.2f}% wr={r['wr'] * 100:4.1f}% "
            f"mdd={r['mdd'] * 100:6.2f}% trades={int(r['trades_n'])}"
        )

    print("\n=== Bottom 10 ===")
    for _, r in df.nsmallest(10, "ret").iterrows():
        print(
            f"{r['ticker']:6s} ret={r['ret'] * 100:7.2f}% wr={r['wr'] * 100:4.1f}% "
            f"mdd={r['mdd'] * 100:6.2f}% trades={int(r['trades_n'])}"
        )

    nan_ret = df["ret"].isna().sum()
    if nan_ret:
        print(f"\n注意: {nan_ret} 只 total_return=nan（评分/汇总异常）")
    print(f"\n板块汇总已写入: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
