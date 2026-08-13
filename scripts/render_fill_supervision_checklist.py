#!/usr/bin/env python
"""Wave 1 M4: Render fill supervision invalid fills as human review checklist."""
from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load_report(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def render_section(profile: str, report: dict) -> list[str]:
    invalid = report.get("invalid_fills") or []
    lines = [
        f"## {profile}",
        "",
        f"- 扫描成交：{report.get('fills_scanned', '?')}",
        f"- invalid：{len(invalid)}",
        "",
        "| # | 品种 | 方向 | 入场日 | 定式 | 问题摘要 | order_id |",
        "|---|------|------|--------|------|----------|----------|",
    ]
    for i, row in enumerate(invalid, 1):
        issues = "; ".join(row.get("issues") or [])[:120]
        lines.append(
            f"| {i} | {row.get('symbol','')} | {row.get('side','')} | {row.get('entry_date','')} | "
            f"{row.get('strategy_id','')} | {issues} | `{row.get('order_id','')}` |"
        )
    lines.extend(
        [
            "",
            "### 人工确认项（每笔勾选）",
            "",
            "- [ ] 已对照 `events.jsonl` / setup_key",
            "- [ ] 已对照 D1 沙盒或 OS 快照",
            "- [ ] 决策：保留 / 标记 audit_invalid / 权益复核",
            "",
        ]
    )
    return lines


def main() -> int:
    parser = argparse.ArgumentParser(description="Render M4 fill supervision checklist.")
    parser.add_argument(
        "--domestic",
        default=str(ROOT / "runtime/logs/fill_supervision/fill_supervision_domestic_remote_latest.json"),
    )
    parser.add_argument(
        "--overseas",
        default=str(ROOT / "runtime/logs/fill_supervision/fill_supervision_overseas_remote_latest.json"),
    )
    parser.add_argument(
        "--out",
        default=str(ROOT / "results" / "fill_supervision_invalid_checklist_2026-06-09.md"),
    )
    args = parser.parse_args()

    domestic = load_report(Path(args.domestic))
    overseas = load_report(Path(args.overseas))
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    lines = [
        "# 成交后监督 · invalid 人工确认清单（Wave 1 · M4）",
        "",
        f"生成时间：{now}",
        "",
        "> 本清单来自 `audit_paper_fills.py` 远端复核 JSON。**不得**自动改 equity 或静默删持仓。",
        "",
        f"**合计 invalid**：国内 {len(domestic.get('invalid_fills') or [])} + 海外 {len(overseas.get('invalid_fills') or [])} = "
        f"{len(domestic.get('invalid_fills') or []) + len(overseas.get('invalid_fills') or [])} 笔",
        "",
    ]
    lines.extend(render_section("国内 domestic", domestic))
    lines.extend(render_section("海外 overseas", overseas))
    lines.extend(
        [
            "## 处置 SOP",
            "",
            "1. 备份当次 JSON 报告。",
            "2. 核对 `paper_state` / `events.jsonl`。",
            "3. 需归档时走 `repair_corrupt_futures_state_from_audit.py` dry-run + 人工 `--apply`。",
            "4. 权益变更单独审批（参见 BNB/PP 案例）。",
            "",
        ]
    )

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"M4 checklist -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
