#!/usr/bin/env python3
"""本机 domestic futures D1 末根 K 线新鲜度审计（周一补抓窗口验证用）。"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_D1_DIR = ROOT / "data" / "futures" / "1d"


def last_bar_date(csv_path: Path) -> str:
    df = pd.read_csv(csv_path)
    for col in ("date", "timestamp", "datetime"):
        if col in df.columns:
            return str(df[col].iloc[-1])[:10]
    return str(df.iloc[-1, 0])[:10]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--d1-dir", default=str(DEFAULT_D1_DIR))
    parser.add_argument("--stale-hours", type=int, default=72, help="Mark stale if last bar older than this many hours from now.")
    parser.add_argument("--out-dir", default=str(ROOT / "results" / "domestic_futures_d1_freshness_latest"))
    args = parser.parse_args()

    d1_dir = Path(args.d1_dir)
    if not d1_dir.is_dir():
        print(f"missing d1 dir: {d1_dir}", file=sys.stderr)
        return 1

    cutoff = (datetime.now() - timedelta(hours=args.stale_hours)).strftime("%Y-%m-%d")
    rows: list[dict] = []
    for path in sorted(d1_dir.glob("*.csv")):
        try:
            last = last_bar_date(path)
            rows.append({"code": path.stem, "last_bar": last, "stale": last < cutoff})
        except Exception as exc:
            rows.append({"code": path.stem, "last_bar": "", "stale": True, "error": str(exc)})

    stale = [r for r in rows if r.get("stale")]
    ok = [r for r in rows if not r.get("stale")]
    report = {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "d1_dir": str(d1_dir),
        "cutoff_date": cutoff,
        "stale_hours": args.stale_hours,
        "total": len(rows),
        "ok": len(ok),
        "stale": len(stale),
        "rows": rows,
    }

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "# 国内期货 D1 本机新鲜度审计",
        "",
        f"生成：{report['generated_at']}",
        f"目录：`{d1_dir}`",
        f"cutoff（末根 < {cutoff} 视为 stale）：**{args.stale_hours}h**",
        "",
        f"| 项 | 数量 |",
        f"|---|---|",
        f"| 品种 | {len(rows)} |",
        f"| OK | {len(ok)} |",
        f"| stale | {len(stale)} |",
        "",
    ]
    if stale:
        lines.append("## stale 列表")
        lines.append("")
        for r in stale[:20]:
            lines.append(f"- {r['code']}: {r.get('last_bar', '?')}")
        if len(stale) > 20:
            lines.append(f"- … 共 {len(stale)} 个")
    (out_dir / "SUMMARY.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(json.dumps({"ok": len(ok), "stale": len(stale), "total": len(rows), "out": str(out_dir)}, ensure_ascii=False))
    return 0 if not stale else 2


if __name__ == "__main__":
    raise SystemExit(main())
