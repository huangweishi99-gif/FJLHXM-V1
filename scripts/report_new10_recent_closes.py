#!/usr/bin/env python3
"""Export recent new10 closed trades from paper state."""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NEW10 = {
    "XRPUSDT", "HYPEUSDT", "ATHUSDT", "PEPEUSDT", "ARBUSDT",
    "OPUSDT", "SUIUSDT", "NEARUSDT", "INJUSDT", "WLDUSDT",
}

R39_ORDERS = {
    "XRPUSDT-DS01-D1-short-4d468b98ca428fbb": "#23",
    "NEARUSDT-DS08-H1-long-adf7ca5441bcf706": "#24",
    "SUIUSDT-DS01-D1-short-29aaad4d76ce298b": "#25",
    "PEPEUSDT-DS01-D1-short-4df983727621dae9": "#26",
    "HYPEUSDT-DS05-D1-long-745d2a2100e81337": "#27",
    "OPUSDT-DS09-M15-short-0004f7200a729e31": "#29",
}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--paper-state", default=str(ROOT / "runtime" / "overseas_paper_state.json"))
    parser.add_argument("--since", default="2026-06-28 00:00:00")
    parser.add_argument("--out-dir", default="")
    args = parser.parse_args()
    path = Path(args.paper_state)
    if not path.is_file():
        print(f"missing: {path}", file=sys.stderr)
        return 1
    ps = json.loads(path.read_text(encoding="utf-8"))
    since = datetime.strptime(args.since, "%Y-%m-%d %H:%M:%S")
    rows = []
    for row in ps.get("closed_trades", []) or []:
        sym = str(row.get("symbol", "")).upper()
        if sym not in NEW10:
            continue
        exit_time = str(row.get("exit_time") or row.get("closed_at") or "")
        try:
            if datetime.strptime(exit_time, "%Y-%m-%d %H:%M:%S") < since:
                continue
        except ValueError:
            continue
        oid = str(row.get("order_id", ""))
        item = dict(row)
        item["signoff_index"] = R39_ORDERS.get(oid, "")
        rows.append(item)
    rows.sort(key=lambda r: str(r.get("exit_time", "")))
    report = {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "since": args.since,
        "count": len(rows),
        "closes": rows,
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if args.out_dir:
        out = Path(args.out_dir)
        out.mkdir(parents=True, exist_ok=True)
        (out / "closes.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        (out / "CLOSES_SUMMARY.md").write_text(render_md(report), encoding="utf-8")
    return 0


def render_md(report: dict) -> str:
    lines = [
        f"# new10 r39 平仓签收 · {report['generated_at']}",
        "",
        f"自 **{report['since']}** 起共 **{report['count']}** 笔 new10 平仓。",
        "",
        "| 索引 | 品种 | 定式 | 方向 | 入场 | 出场 | 原因 | net PnL | 签收 |",
        "|------|------|------|------|------|------|------|---------|------|",
    ]
    for row in report["closes"]:
        idx = row.get("signoff_index") or "—"
        verdict = "VALID+EXEC_GAP" if idx in {"#23", "#24", "#25", "#26", "#27"} else "VALID"
        if idx == "#29":
            verdict = "VALID CLOSE"
        lines.append(
            f"| {idx} | {row.get('symbol')} | {row.get('strategy_id')} | {row.get('direction')} | "
            f"{row.get('entry_price')} @ {str(row.get('entry_time',''))[:16]} | "
            f"{row.get('exit_price')} @ {str(row.get('exit_time',''))[:16]} | "
            f"{row.get('exit_reason')} | **{row.get('net_pnl', 0):.2f}** | {verdict} |"
        )
    lines.extend(
        [
            "",
            "## 说明",
            "",
            "- **#23–#26**：结构仍按 r39 OPEN 签收 **VALID**；出场为 06-30 止损热修后补执行，标 **EXEC_GAP**（延迟止损，非结构 FAIL）",
            "- **#27 HYPE**：旧仓 DS05 long 在热修同轮 `gap_stop` 平仓；**11:35:53** 同策略新仓已重开（见 `open_new10`）",
            "- 详见 `STOP_EXEC_REVIEW.md` · `USER_SIGNOFF.md`",
        ]
    )
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    raise SystemExit(main())
