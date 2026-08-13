#!/usr/bin/env python3
"""Wave 4 M5 B-zone: categorize DS01 ack invalids + recommended disposition."""
from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REVIEW = ROOT / "results" / "fill_supervision_m5_review_2026-06-10.md"
DOMESTIC_JSON = ROOT / "runtime/logs/fill_supervision/fill_supervision_domestic_remote_latest.json"
OVERSEAS_JSON = ROOT / "runtime/logs/fill_supervision/fill_supervision_overseas_remote_latest.json"
OUT = ROOT / "results/m5_b_zone_disposition_draft_2026-06-10.md"
DISPOSITION_JSON = ROOT / "runtime/m5_b_zone_disposition_draft.json"

ORDER_ID_RE = re.compile(r"`([A-Z0-9_.-]+-DS01-[A-Z0-9]+-(?:long|short)-[0-9a-f]+)`")

# 权益复核：换月/大偏差 trigger-stop（单独审批，不批量 apply equity）
EQUITY_REVIEW_IDS = {
    "ECUSDT-DS01-D1-long-2dfeae944abdef49",
    "ECUSDT-DS01-D1-long-f48041169975e929",
    "LHUSDT-DS01-D1-short-58b2638967b67a32",
    "LHUSDT-DS01-D1-long-50754f2091ac9227",
    "BNBUSDT-DS01-D1-long-ebfd3882424f3fc6",
}


def bucket(issues: list[str]) -> str:
    text = "; ".join(issues)
    if "trigger mismatch" in text or "stop mismatch" in text:
        return "trigger/stop"
    if "os_defense_missing" in text:
        return "DS01 defense"
    if "signal_camp" in text:
        return "DS01 camp"
    if "entry_fill=False" in text:
        return "DS01 fill bar"
    if "signal bar not" in text:
        return "DS01 signal bar"
    return "other"


def extract_b_zone(review_path: Path) -> list[dict]:
    text = review_path.read_text(encoding="utf-8")
    in_b = False
    rows: list[dict] = []
    for line in text.splitlines():
        if line.startswith("## B."):
            in_b = True
            continue
        if in_b and line.startswith("## C."):
            break
        if not in_b or not line.startswith("|") or "---" in line or "# |" in line:
            continue
        parts = [p.strip() for p in line.split("|")]
        if len(parts) < 10 or not parts[1].isdigit():
            continue
        oid_match = ORDER_ID_RE.search(line)
        if not oid_match:
            continue
        rows.append(
            {
                "num": int(parts[1]),
                "profile": parts[2],
                "symbol": parts[3],
                "side": parts[4],
                "entry_date": parts[5],
                "issues_summary": parts[8],
                "order_id": oid_match.group(1),
            }
        )
    return rows


def load_checks(order_id: str) -> dict:
    for path in (DOMESTIC_JSON, OVERSEAS_JSON):
        if not path.exists():
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        for row in data.get("all_results") or []:
            if row.get("order_id") == order_id:
                return row.get("checks") or {}
    return {}


def recommended(row: dict, issues: list[str]) -> str:
    oid = row["order_id"]
    if oid in EQUITY_REVIEW_IDS:
        return "equity_review"
    return "audit_invalid"


def main() -> int:
    rows = extract_b_zone(REVIEW)
    if len(rows) != 33:
        raise SystemExit(f"expected 33 B-zone rows, got {len(rows)}")

    enriched: list[dict] = []
    by_rec: Counter[str] = Counter()
    by_bucket: Counter[str] = Counter()
    for row in rows:
        checks = load_checks(row["order_id"])
        issues = []
        for path in (DOMESTIC_JSON, OVERSEAS_JSON):
            if not path.exists():
                continue
            data = json.loads(path.read_text(encoding="utf-8"))
            for r in data.get("invalid_fills") or []:
                if r.get("order_id") == row["order_id"]:
                    issues = list(r.get("issues") or [])
        b = bucket(issues)
        rec = recommended(row, issues)
        by_rec[rec] += 1
        by_bucket[b] += 1
        enriched.append({**row, "issue_bucket": b, "issues": issues, "checks": checks, "recommended": rec})

    audit_ids = [r["order_id"] for r in enriched if r["recommended"] == "audit_invalid"]
    equity_ids = [r["order_id"] for r in enriched if r["recommended"] == "equity_review"]

    payload = {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "status": "draft_pending_user_approval",
        "audit_invalid": audit_ids,
        "equity_review": equity_ids,
        "rows": enriched,
    }
    DISPOSITION_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "# M5 B 区处置草案（33 笔 DS01 · 待批准）",
        "",
        f"生成时间：{payload['generated_at']}",
        "",
        "> B 区已在 ack 清单（watchdog 不告警）。本草案供你**一次性批准**后执行 repair；**equity 回滚仍须单独确认**。",
        "",
        "## 分组统计",
        "",
        f"| 建议处置 | 笔数 |",
        f"|----------|------|",
        f"| audit_invalid | {by_rec['audit_invalid']} |",
        f"| equity_review（先 audit_invalid 标记，权益另批） | {by_rec['equity_review']} |",
        "",
        "### 按问题类型",
        "",
    ]
    for k, v in sorted(by_bucket.items(), key=lambda x: -x[1]):
        lines.append(f"- **{k}**：{v} 笔")

    lines.extend(
        [
            "",
            "## 建议批量口径（草案）",
            "",
            "```text",
            f"audit_invalid：{len(audit_ids)} 笔（camp/defense/signal bar 等 S1 前遗留）",
            f"equity_review：{len(equity_ids)} 笔（EC×2、LH×2、BNB-ebfd3882…）— 标记 invalid 后单独算权益",
            "```",
            "",
            "## equity_review 清单（5 笔）",
            "",
            "| # | 端 | 品种 | 入场日 | order_id | 问题摘要 |",
            "|---|-----|------|--------|----------|----------|",
        ]
    )
    for r in enriched:
        if r["recommended"] != "equity_review":
            continue
        lines.append(
            f"| {r['num']} | {r['profile']} | {r['symbol']} | {r['entry_date']} | `{r['order_id']}` | {r['issues_summary'][:80]} |"
        )

    lines.extend(
        [
            "",
            "## 样本追溯",
            "",
            "详见 `results/m5_b_zone_sample_trace_2026-06-10.md` + `results/m5_samples/*_ds01*.svg`",
            "",
            "## 批准后我将执行",
            "",
            "1. `runtime/m5_b_zone_disposition.json` 写入最终口径",
            "2. 双端 `repair_corrupt_futures_state_from_audit.py --apply`（仅标记 invalid / 释放锁，**不**自动 equity）",
            "3. equity_review 5 笔产出 dry-run 回滚估算供你二次确认",
            "",
            "## 请你回复（一行）",
            "",
            "```text",
            "同意 B 区草案：28 audit_invalid + 5 equity_review",
            "```",
            "",
            "或逐笔修改 equity_review 列表。",
            "",
        ]
    )
    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"B-zone draft -> {OUT} ({len(audit_ids)} audit_invalid, {len(equity_ids)} equity_review)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
