#!/usr/bin/env python3
"""Render N04 OS rebuild fill supervision disposition draft (M5-style)."""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOMESTIC_FILL = ROOT / "results" / "os_state_rebuild" / "domestic_fill_audit.json"
OVERSEAS_FILL = ROOT / "results" / "os_state_rebuild" / "overseas_fill_audit.json"
DOMESTIC_DIFF = ROOT / "results" / "os_state_rebuild" / "domestic_diff.json"
OVERSEAS_DIFF = ROOT / "results" / "os_state_rebuild" / "overseas_diff.json"
ACK_PATH = ROOT / "runtime" / "fill_supervision_acknowledged.json"
OUT_MD = ROOT / "results" / "n04_rebuild_disposition_draft_2026-06-10.md"
OUT_JSON = ROOT / "runtime" / "n04_rebuild_disposition_draft.json"

# N04 rebuild 后国内唯一新增 invalid（RB 1d camp 蓝→红，DS01 空单 signal_camp 不符）
N04_NEW_INVALID = "RBUSDT-DS01-D1-short-5b4e7fd42ee68111"


def load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def camp_changed_rows(diff: dict) -> list[dict]:
    rows = []
    for row in diff.get("rows") or []:
        if row.get("status") == "changed" and "camp" in str(row.get("changed_fields", "")):
            rows.append(row)
    return rows


def find_fill(fill_audit: dict, order_id: str) -> dict | None:
    for key in ("invalid_fills", "all_results"):
        for row in fill_audit.get(key) or []:
            if row.get("order_id") == order_id:
                return row
    return None


def main() -> int:
    domestic_fill = load_json(DOMESTIC_FILL)
    overseas_fill = load_json(OVERSEAS_FILL)
    domestic_diff = load_json(DOMESTIC_DIFF)
    overseas_diff = load_json(OVERSEAS_DIFF)
    ack = load_json(ACK_PATH)
    ack_ids = set(ack.get("acknowledged") or [])

    def recount_invalid_new(fill_audit: dict) -> int:
        invalid = fill_audit.get("invalid_fills") or []
        return sum(1 for row in invalid if row.get("order_id") not in ack_ids)

    domestic_invalid_new = recount_invalid_new(domestic_fill)
    overseas_invalid_new = recount_invalid_new(overseas_fill)

    rb = find_fill(domestic_fill, N04_NEW_INVALID) or {}
    rb_checks = rb.get("checks") or {}
    rb_issues = list(rb.get("issues") or [])

    domestic_camp = camp_changed_rows(domestic_diff)
    overseas_camp = camp_changed_rows(overseas_diff)

    recommended = "audit_invalid"
    if N04_NEW_INVALID in ack_ids:
        status = "ack_registered"
    else:
        status = "pending_ack"

    payload = {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "status": status,
        "context": "N04 os_engine break-rule + C-class defense fallback; OS state full rebuild 2026-06-10",
        "summary": {
            "domestic_fill": domestic_fill.get("summary") or {},
            "overseas_fill": overseas_fill.get("summary") or {},
            "domestic_camp_changed": len(domestic_camp),
            "overseas_camp_changed": len(overseas_camp),
        },
        "audit_invalid": [N04_NEW_INVALID],
        "equity_review": [],
        "rows": [
            {
                "order_id": N04_NEW_INVALID,
                "profile": "domestic",
                "symbol": "RBUSDT",
                "strategy_id": "DS01",
                "side": "short",
                "entry_date": rb.get("entry_date", "2026-06-08"),
                "fill_time": rb.get("fill_time", ""),
                "issues": rb_issues,
                "issue_bucket": "DS01 camp",
                "recommended": recommended,
                "os_context": "RB_1d.json camp blue->red after N04 rebuild; signal bar camp=red (1) but DS01 short expects blue (-1)",
                "checks": rb_checks,
            }
        ],
        "camp_changed_reference": {
            "domestic": [
                {
                    "state_file": r.get("state_file"),
                    "before_camp": r.get("before_camp"),
                    "after_camp": r.get("after_camp"),
                }
                for r in domestic_camp
            ],
            "overseas": [
                {
                    "state_file": r.get("state_file"),
                    "before_camp": r.get("before_camp"),
                    "after_camp": r.get("after_camp"),
                }
                for r in overseas_camp
            ],
        },
    }
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "# N04 OS rebuild 处置草案（2026-06-10）",
        "",
        f"- generated_at: {payload['generated_at']}",
        f"- status: **{status}**",
        f"- 背景: N04 破极规则 + C 类防守极 fallback；国内/海外 OS state 已全量 rebuild 并 swap。",
        "",
        "## Fill 复核摘要（720h，新引擎）",
        "",
        "| 端 | valid | invalid | invalid_ack | invalid_new |",
        "|---|---:|---:|---:|---:|",
        f"| 国内 | {payload['summary']['domestic_fill'].get('valid', '?')} | "
        f"{payload['summary']['domestic_fill'].get('invalid', '?')} | "
        f"{payload['summary']['domestic_fill'].get('invalid_acknowledged', '?')} | "
        f"{domestic_invalid_new} |",
        f"| 海外 | {payload['summary']['overseas_fill'].get('valid', '?')} | "
        f"{payload['summary']['overseas_fill'].get('invalid', '?')} | "
        f"{payload['summary']['overseas_fill'].get('invalid_acknowledged', '?')} | "
        f"{overseas_invalid_new} |",
        "",
        "## 建议处置（1 笔新增 invalid）",
        "",
        "| # | profile | symbol | side | entry | 问题 | 建议 | order_id |",
        "|---:|---|---|---|---|---|---|---|",
        f"| 1 | domestic | RB | short | {rb.get('entry_date', '')} | "
        f"{'; '.join(rb_issues) or 'signal_camp mismatch'} | **audit_invalid** | `{N04_NEW_INVALID}` |",
        "",
        "### RB 结构上下文",
        "",
        "- OS diff: `RB_1d.json` **blue → red**（N04 rebuild 后 camp 修正）",
        f"- signal bar: {rb_checks.get('signal_date', '?')} camp={rb_checks.get('signal_camp', '?')}（红营）",
        "- DS01 做空要求 signal_camp=-1（蓝营）→ **逆势/阵营不符**",
        f"- trigger/stop: {rb_checks.get('trigger_calc', '?')} / {rb_checks.get('stop_calc', '?')}（几何一致，**非 equity_review**）",
        "",
        "## camp 变更参考（rebuild diff，非逐笔 fill 处置）",
        "",
        "### 国内 camp_changed=7",
        "",
        "| state_file | before | after |",
        "|---|---|---|",
    ]
    for row in domestic_camp:
        lines.append(f"| {row.get('state_file')} | {row.get('before_camp')} | {row.get('after_camp')} |")
    lines.extend(
        [
            "",
            "### 海外 camp_changed=5（含 BNB 1d 红→蓝）",
            "",
            "| state_file | before | after |",
            "|---|---|---|",
        ]
    )
    for row in overseas_camp:
        lines.append(f"| {row.get('state_file')} | {row.get('before_camp')} | {row.get('after_camp')} |")
    lines.extend(
        [
            "",
            "## 执行清单",
            "",
            "- [x] OS state rebuild + swap（国内 102/102、海外 48/48）",
            f"- [{'x' if status == 'ack_registered' else ' '}] 登记 ack: `{N04_NEW_INVALID}` → audit_invalid",
            "- [ ] **未做** equity 回滚（RB 无 trigger/stop 大偏差，仅 camp 不符）",
            "- [ ] **未做** monitor 锁 repair（如 RB 仍持仓，需单独 dry-run `repair_domestic_state_invalid_positions.py`）",
            "",
            "JSON: `runtime/n04_rebuild_disposition_draft.json`",
        ]
    )
    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"draft_md={OUT_MD}")
    print(f"draft_json={OUT_JSON}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
