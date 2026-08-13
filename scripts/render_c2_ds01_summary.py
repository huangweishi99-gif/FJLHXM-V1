#!/usr/bin/env python3
"""汇总四市场 C2 DS01 对比 JSON → Markdown 清单。"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MARKETS = ("CRYPTO", "FUTURES", "US_STOCK", "A_STOCK")


def main() -> int:
    lines = [
        "# C2 DS01 S1 对比汇总",
        "",
        f"生成时间：{datetime.now():%Y-%m-%d %H:%M:%S}",
        "",
        "> baseline = 统一回测 accepted 中 DS01 行数；rerun = 当前引擎 DS01-only D1 重跑。delta ≠ S1 纯 diff，供影响面初筛。",
        "",
    ]
    for market in MARKETS:
        path = ROOT / "results" / f"c2_ds01_s1_compare_{market.lower()}.json"
        if not path.exists():
            lines.append(f"## {market}\n\n- 报告缺失：`{path.name}`\n")
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        items = [i for i in data.get("items", []) if i.get("status") == "ok"]
        changed = [i for i in items if i.get("delta") not in (None, 0)]
        errors = [i for i in data.get("items", []) if i.get("status") == "error"]
        lines.extend(
            [
                f"## {market}",
                "",
                f"- 品种：{data.get('symbols_compared', data.get('scanned', len(items)))} · "
                f"有 delta：{len(changed)} · 错误：{len(errors)}",
                "",
            ]
        )
        if changed:
            lines.append("| symbol | baseline | rerun | delta |")
            lines.append("|--------|----------|-------|-------|")
            for row in sorted(changed, key=lambda x: abs(int(x.get("delta") or 0)), reverse=True)[:25]:
                lines.append(
                    f"| {row['symbol']} | {row.get('baseline_ds01')} | {row.get('rerun_ds01')} | {row.get('delta')} |"
                )
            if len(changed) > 25:
                lines.append(f"| … | | | +{len(changed) - 25} more |")
            lines.append("")
        if errors:
            lines.append(f"错误样例：{', '.join(str(e.get('symbol')) for e in errors[:5])}")
            lines.append("")

    out = ROOT / "results" / "c2_ds01_s1_compare_summary.md"
    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
