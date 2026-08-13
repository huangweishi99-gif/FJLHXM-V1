#!/usr/bin/env python3
"""Wave 4 M5: Render fill supervision review pack (720h, ack vs new invalid)."""
from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def load_ack_ids(path: Path) -> set[str]:
    if not path.exists():
        return set()
    payload = load_json(path)
    rows = payload.get("acknowledged", payload)
    if isinstance(rows, dict):
        return {str(k) for k in rows.keys()}
    if isinstance(rows, list):
        out: set[str] = set()
        for item in rows:
            if isinstance(item, str):
                out.add(item)
            elif isinstance(item, dict) and item.get("order_id"):
                out.add(str(item["order_id"]))
        return out
    return set()


def classify_invalid(report: dict, ack_ids: set[str]) -> tuple[list[dict], list[dict]]:
    invalid = list(report.get("invalid_fills") or [])
    new_rows: list[dict] = []
    ack_rows: list[dict] = []
    for row in invalid:
        oid = str(row.get("order_id") or "")
        if oid and oid in ack_ids:
            ack_rows.append(row)
        else:
            new_rows.append(row)
    return new_rows, ack_rows


def issue_bucket(issues: list[str]) -> str:
    text = "; ".join(issues)
    if "resolve_ds03_attack" in text:
        return "DS03 attack"
    if "os_defense_missing" in text:
        return "DS01 defense"
    if "signal_camp" in text:
        return "DS01 camp"
    if "entry_fill=False" in text:
        return "DS01 fill bar"
    if "trigger mismatch" in text:
        return "trigger/stop"
    if "make_ds08" in text or "skeleton" in text.lower():
        return "DS08 structure"
    return "other"


def render_table(rows: list[dict], start: int = 1) -> list[str]:
    lines = [
        "| # | 端 | 品种 | 方向 | 入场日 | 定式 | 问题类型 | 问题摘要 | order_id |",
        "|---|-----|------|------|--------|------|----------|----------|----------|",
    ]
    for i, row in enumerate(rows, start):
        issues = row.get("issues") or []
        summary = "; ".join(issues)[:100]
        lines.append(
            f"| {i} | {row.get('_profile', '')} | {row.get('symbol', '')} | {row.get('side', '')} | "
            f"{row.get('entry_date', '')} | {row.get('strategy_id', '')} | {issue_bucket(issues)} | "
            f"{summary} | `{row.get('order_id', '')}` |"
        )
    return lines


def main() -> int:
    parser = argparse.ArgumentParser(description="Render M5 fill supervision review pack.")
    parser.add_argument(
        "--domestic",
        default=str(ROOT / "runtime/logs/fill_supervision/fill_supervision_domestic_remote_latest.json"),
    )
    parser.add_argument(
        "--overseas",
        default=str(ROOT / "runtime/logs/fill_supervision/fill_supervision_overseas_remote_latest.json"),
    )
    parser.add_argument(
        "--ack-file",
        default=str(ROOT / "runtime/fill_supervision_acknowledged.json"),
    )
    parser.add_argument(
        "--out",
        default=str(ROOT / "results/fill_supervision_m5_review_2026-06-10.md"),
    )
    args = parser.parse_args()

    ack_ids = load_ack_ids(Path(args.ack_file))
    domestic = load_json(Path(args.domestic))
    overseas = load_json(Path(args.overseas))

    all_new: list[dict] = []
    all_ack: list[dict] = []
    for profile, report in (("domestic", domestic), ("overseas", overseas)):
        new_rows, ack_rows = classify_invalid(report, ack_ids)
        for row in new_rows:
            row = dict(row)
            row["_profile"] = profile
            all_new.append(row)
        for row in ack_rows:
            row = dict(row)
            row["_profile"] = profile
            all_ack.append(row)

    new_by_strategy = Counter(str(r.get("strategy_id", "")) for r in all_new)
    ack_by_strategy = Counter(str(r.get("strategy_id", "")) for r in all_ack)
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    lines = [
        "# 成交监督 M5 人工复核包（Wave 4）",
        "",
        f"生成时间：{now}",
        "",
        "> **禁止**自动改 equity / 静默删持仓。处置须逐笔勾选后走 repair 或权益审批。",
        "> M2 修复后（2026-06-10）：海外近 **72h** 已 `valid=7 invalid=0`；本包为 **720h** 历史窗口全量复核。",
        "",
        "## 摘要",
        "",
        f"| 端 | 扫描 | valid | invalid | 新 invalid | 已 ack | needs_data | skipped |",
        f"|----|------|-------|---------|------------|--------|------------|---------|",
    ]
    for profile, report in (("国内", domestic), ("海外", overseas)):
        s = report.get("summary") or {}
        lines.append(
            f"| {profile} | {report.get('fills_scanned', '?')} | {s.get('valid', '?')} | "
            f"{s.get('invalid', '?')} | {s.get('invalid_new', '?')} | {s.get('invalid_acknowledged', '?')} | "
            f"{s.get('needs_data', '?')} | {s.get('skipped', '?')} |"
        )
    lines.extend(
        [
            "",
            f"- **M4 已登记 order_id**：{len(ack_ids)} 笔",
            f"- **720h 新 invalid（待人工）**：{len(all_new)} 笔 — "
            + ", ".join(f"{k}={v}" for k, v in sorted(new_by_strategy.items()) if k),
            f"- **720h 仍 invalid 且已 ack**：{len(all_ack)} 笔 — "
            + ", ".join(f"{k}={v}" for k, v in sorted(ack_by_strategy.items()) if k),
            "",
            "## A. 待人工确认 · 新 invalid（优先）",
            "",
            "每笔勾选：**保留模拟成交** / **标记 audit_invalid** / **权益复核** / **仅文档登记**",
            "",
        ]
    )
    if all_new:
        lines.extend(render_table(all_new))
    else:
        lines.append("_（无新 invalid）_")
    lines.extend(
        [
            "",
            "### A 区处置建议（初筛，非最终裁定）",
            "",
            "| 问题类型 | 典型原因 | 建议动作 |",
            "|----------|----------|----------|",
            "| DS03 attack | 入场日 attack 解析失败 / 跨周期 | 对照 D1+H1 沙盒；S1 部署前历史可标 audit_invalid |",
            "| DS01 defense/camp | OS 防守极或信号棍阵营 | 对照 D1 沙盒 + M4 清单；多数为 S1 前遗留 |",
            "| DS01 fill bar | 日 K 未收完 | M2 已修 pending fill；720h 旧记录可重跑 audit 复核 |",
            "| trigger/stop | 挂单字段与重算偏差 | 核对 events.jsonl setup_key；期货换月/加腿单独列 |",
            "",
            "## B. M4 已登记 · 仍 invalid（历史清单跟进）",
            "",
            "已在 `runtime/fill_supervision_acknowledged.json` 登记，watchdog 不重复告警；**M5 权益/repair 仍待逐笔批准**。",
            "",
        ]
    )
    if all_ack:
        lines.extend(render_table(all_ack))
    else:
        lines.append("_（无）_")
    lines.extend(
        [
            "",
            "## C. 人工确认清单（整包）",
            "",
            f"- [ ] 已阅读 A 区 **{len(all_new)}** 笔新 invalid 并按品种分组复核",
            "- [ ] DS01 类：已对照 D1 沙盒或 OS 快照（S2 可点名品种补图）",
            "- [ ] DS03 类：已确认是否为 S1/跨周期历史遗留",
            "- [ ] B 区 M4 **33** 笔：已决定 repair / 权益 / 仅登记",
            "- [ ] 批准后方可执行 `repair_corrupt_futures_state_from_audit.py --apply` 或权益回滚脚本",
            "- [ ] 处置完成后更新 ack 文件并同步双端服务器",
            "",
            "## 数据源",
            "",
            f"- 国内：`{args.domestic}`",
            f"- 海外：`{args.overseas}`",
            f"- ack：`{args.ack_file}`",
            "",
        ]
    )

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"M5 review -> {out} ({len(all_new)} new, {len(all_ack)} ack-invalid)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
