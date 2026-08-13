#!/usr/bin/env python3
"""Inventory results/ for archive vs keep (read-only)."""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results"

KEEP_PREFIXES = (
    "ops_round_",
    "new10_",
    "iousdt_",
    "shadow_observation",
    "pending_monitor_verify",
    "server_health",
    "main_contract_paper_recalc",
    "futures_tier_post_activation",
    "futures_bucket_merge",
    "completion_round",
)

KEEP_EXACT = {
    "sandbox",
    "_archive",
    "S2_DEEP_REVIEW_INDEX.md",
    "RESULTS_ARCHIVE_INVENTORY_20260618.md",
}

ARCHIVE_PATTERNS = (
    "_smoke",
    "smoke_",
    "ds01_sample",
    "ds02_sample",
    "ds05_sample",
    "old_9dds",
    "doc_images",
    "structure",
    "unified_smoke",
    "unified_batch_smoke",
    "_io_radar",
    "fengji_total_pattern_okx16_5y_m15",
    "ds09_sol_5y_m15",
    "ds05_crypto_hot",
)

LARGE_ARCHIVE_CANDIDATES = (
    "plan_a_us_stock_c1",
    "plan_a_a_stock_c1",
)

REVIEW_BEFORE_DELETE = (
    "fengji_total_ds01_ds08_futures_15_5y",
    "fengji_total_ds01_ds08_okx16_5y",
    "fengji_total_a_stock_sectors_virtual_robot_ds07_fixed",
    "crypto_off_paper_sandbox_20260616",
    "m5_samples",
    "os_state_rebuild",
    "s2_ds01_sandbox_20260614",
    "plan_a_crypto_180d",
    "plan_a_futures_c1",
)


def dir_size(path: Path) -> tuple[int, int]:
    files = [f for f in path.rglob("*") if f.is_file()]
    return len(files), sum(f.stat().st_size for f in files)


def classify(name: str) -> str:
    if name in KEEP_EXACT:
        return "KEEP"
    for p in KEEP_PREFIXES:
        if name.startswith(p) or name == p:
            return "KEEP"
    for p in LARGE_ARCHIVE_CANDIDATES:
        if name == p:
            return "ARCHIVE_LARGE"
    for p in REVIEW_BEFORE_DELETE:
        if name == p:
            return "REVIEW_ARCHIVE"
    for p in ARCHIVE_PATTERNS:
        if p in name:
            return "ARCHIVE_SAFE"
    if name.startswith("context_market_calibration"):
        return "ARCHIVE_SAFE"
    if name.startswith("futures_tier_audit"):
        return "ARCHIVE_SAFE"
    if name.startswith("fengji_total_") and "user20" in name:
        return "ARCHIVE_SAFE"
    if name.startswith("ds0") and ("recheck" in name or "cotton" in name or "crypto_hot" in name):
        return "ARCHIVE_SAFE"
    return "REVIEW"


def main() -> None:
    rows = []
    for d in sorted(RESULTS.iterdir()):
        if d.is_file():
            continue
        n, size = dir_size(d)
        mtime = datetime.fromtimestamp(d.stat().st_mtime).strftime("%Y-%m-%d")
        cat = classify(d.name)
        rows.append({"name": d.name, "category": cat, "files": n, "size_mb": round(size / 1024 / 1024, 2), "mtime": mtime})

    by_cat: dict[str, list] = {}
    for r in rows:
        by_cat.setdefault(r["category"], []).append(r)

    summary = {
        "total_dirs": len(rows),
        "total_mb": round(sum(r["size_mb"] for r in rows), 1),
        "by_category_mb": {
            cat: round(sum(x["size_mb"] for x in items), 1) for cat, items in sorted(by_cat.items())
        },
    }
    out = RESULTS / "RESULTS_ARCHIVE_INVENTORY_20260618.json"
    out.write_text(json.dumps({"summary": summary, "rows": rows}, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "# results/ 归档瘦身清单 · 2026-06-18",
        "",
        f"- 目录数：**{summary['total_dirs']}** · 合计约 **{summary['total_mb']} MB**",
        "",
        "## 分类说明",
        "",
        "| 分类 | 含义 |",
        "|---|---|",
        "| **KEEP** | 近期运维、用户验收、沙盒基准 — 不删 |",
        "| **ARCHIVE_SAFE** | 早期 smoke/样例/空目录 — 可 zip 归档后删 |",
        "| **ARCHIVE_LARGE** | 大块历史回测 — 建议 zip 到冷存储再删 |",
        "| **REVIEW_ARCHIVE** | 有参考价值但体积大 — 人工确认后归档 |",
        "| **REVIEW** | 未自动分类 — 逐项确认 |",
        "",
        "## 按分类汇总（MB）",
        "",
    ]
    for cat, mb in summary["by_category_mb"].items():
        lines.append(f"- **{cat}**：{mb} MB")
    for cat in ("KEEP", "ARCHIVE_SAFE", "ARCHIVE_LARGE", "REVIEW_ARCHIVE", "REVIEW"):
        items = sorted(by_cat.get(cat, []), key=lambda x: -x["size_mb"])
        if not items:
            continue
        lines.extend(["", f"## {cat}", ""])
        lines.append("| 目录 | MB | 文件 | mtime |")
        lines.append("|---|---:|---:|---|")
        for r in items:
            lines.append(f"| `{r['name']}` | {r['size_mb']} | {r['files']} | {r['mtime']} |")

    lines.extend(
        [
            "",
            "## 禁止自动删除",
            "",
            "- `results/sandbox/`（OS 沙盒基准）",
            "- 含 `USER_SIGNOFF.md` 的验收目录",
            "- 本轮 `ops_round_*` / `new10_*` / `iousdt_*`",
            "",
            "## 建议第一批归档（约可释放）",
            "",
        ]
    )
    safe_mb = sum(r["size_mb"] for r in rows if r["category"] == "ARCHIVE_SAFE")
    large_mb = sum(r["size_mb"] for r in rows if r["category"] == "ARCHIVE_LARGE")
    lines.append(f"- **ARCHIVE_SAFE**：约 **{safe_mb} MB**（smoke、old_9dds、空目录等）")
    lines.append(f"- **ARCHIVE_LARGE**（需确认）：约 **{large_mb} MB**（plan_a 美股/A股 C1 大块）")

    md = RESULTS / "RESULTS_ARCHIVE_INVENTORY_20260618.md"
    md.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {md} ({summary['total_mb']} MB total)")


if __name__ == "__main__":
    main()
