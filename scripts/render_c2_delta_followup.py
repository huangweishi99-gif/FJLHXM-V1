#!/usr/bin/env python3
"""C2 后续：按市场汇总 |delta| 分布与沙盒抽查建议（只读，不改回测产物）。"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MARKETS = ("CRYPTO", "FUTURES", "US_STOCK", "A_STOCK")


def load_items(market: str) -> list[dict]:
    path = ROOT / "results" / f"c2_ds01_s1_compare_{market.lower()}.json"
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    return [i for i in data.get("items", []) if i.get("status") == "ok" and i.get("delta") not in (None, 0)]


def main() -> int:
    stamp = datetime.now().strftime("%Y-%m-%d")
    lines = [
        f"# C2 DS01 delta 影响面跟进（{stamp}）",
        "",
        "> baseline = 历史 accepted DS01 笔数；rerun = 当前 OS 引擎 DS01-only D1 重跑。",
        "> **delta 混合了 OS 硬化、S1 防守极、baseline 目录来源差异**，不能当作单一规则 diff。",
        "",
    ]
    sandbox_pick: list[str] = []

    for market in MARKETS:
        items = load_items(market)
        if not items:
            lines.extend([f"## {market}", "", "- 无对比 JSON 或无 delta", ""])
            continue
        neg = sorted([i for i in items if int(i["delta"]) < 0], key=lambda x: int(x["delta"]))
        pos = sorted([i for i in items if int(i["delta"]) > 0], key=lambda x: -int(x["delta"]))
        lines.extend(
            [
                f"## {market}",
                "",
                f"- 有 delta 品种：**{len(items)}** · 减少：**{len(neg)}** · 增加：**{len(pos)}**",
                "",
            ]
        )
        if neg:
            lines.append("### 笔数减少 Top 5（新引擎更严 / baseline 偏松）")
            lines.append("")
            lines.append("| symbol | baseline | rerun | delta |")
            lines.append("|--------|----------|-------|-------|")
            for row in neg[:5]:
                lines.append(
                    f"| {row['symbol']} | {row['baseline_ds01']} | {row['rerun_ds01']} | {row['delta']} |"
                )
            lines.append("")
            if market == "FUTURES":
                sandbox_pick.extend(f"FUTURES/{row['symbol']}" for row in neg[:3])
        if pos:
            lines.append("### 笔数增加 Top 5（新引擎更松 / urgent_gap 等）")
            lines.append("")
            lines.append("| symbol | baseline | rerun | delta |")
            lines.append("|--------|----------|-------|-------|")
            for row in pos[:5]:
                lines.append(
                    f"| {row['symbol']} | {row['baseline_ds01']} | {row['rerun_ds01']} | {row['delta']} |"
                )
            lines.append("")
            if market == "CRYPTO":
                sandbox_pick.extend(f"CRYPTO/{row['symbol']}" for row in pos[:2])

    lines.extend(
        [
            "## 裁定建议",
            "",
            "| 市场 | 解读 | 动作 |",
            "|------|------|------|",
            "| FUTURES | 34/34 delta 为负或小幅正；大 |delta| 多来自旧 5y 目录 baseline 偏高 | **不批量覆盖** accepted；抽查沙盒确认 OS 硬化合理 |",
            "| CRYPTO | 增减参半；APT/RENDER 增、IO 减 | 对增多的品种做 camp/防守极沙盒 |",
            "| US/A | 普遍略减或持平 | 记录影响面即可，无需全量重跑 |",
            "",
            "## 建议沙盒抽查（非阻塞）",
            "",
        ]
    )
    if sandbox_pick:
        for pick in sandbox_pick:
            lines.append(f"- {pick}：`plot_ds01_audit_sandbox.py` 或 `plot_m5_b_zone_ds01_batch.py`")
    else:
        lines.append("- （无 JSON 输入）")
    lines.append("")

    out = ROOT / "results" / f"c2_ds01_delta_followup_{stamp.replace('-', '')}.md"
    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
