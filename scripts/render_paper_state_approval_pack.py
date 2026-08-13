#!/usr/bin/env python3
"""只读生成 domestic paper_state 人工审批包：PP 权益回滚 + 持仓复核清单。"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages" / "fengji_core"))

DEFAULT_STATE = ROOT / "runtime" / "domestic_paper_state.json"
DEFAULT_MANIFEST = ROOT / "runtime" / "domestic_futures_main_contract_sources.json"
PP_ROLLBACK_ORDER = "PPUSDT-DS01-D1-long-44b9d7cd48133592"
REVIEW_SYMBOLS = ("PGUSDT", "LHUSDT", "PPUSDT")


def _load_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def _manifest_contract(manifest: dict[str, Any], code: str) -> str:
    symbols = manifest.get("symbols") or {}
    meta = symbols.get(code.upper()) if isinstance(symbols, dict) else None
    if not isinstance(meta, dict):
        return ""
    return str(meta.get("display_contract") or meta.get("underlying_symbol") or "").strip()


def _collect_open_positions(state: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    symbols = state.get("symbols") or {}
    if not isinstance(symbols, dict):
        return rows
    for sym, bucket in symbols.items():
        if not isinstance(bucket, dict):
            continue
        for pos in bucket.get("open_positions") or []:
            if not isinstance(pos, dict):
                continue
            rows.append(
                {
                    "symbol": str(pos.get("symbol") or sym).upper(),
                    "strategy_id": str(pos.get("strategy_id") or "").upper(),
                    "direction": str(pos.get("direction") or "").lower(),
                    "entry_time": str(pos.get("entry_time") or ""),
                    "entry_price": pos.get("entry_price"),
                    "current_stop": pos.get("current_stop"),
                    "order_id": str(pos.get("order_id") or pos.get("key") or ""),
                    "setup": str(pos.get("setup") or "")[:80],
                }
            )
    rows.sort(key=lambda r: (r["symbol"], r["entry_time"], r["strategy_id"]))
    return rows


def _pp_equity_assessment(state: dict[str, Any]) -> dict[str, Any]:
    bucket = (state.get("symbols") or {}).get("PPUSDT") or {}
    closes = bucket.get("audit_invalid_closes") or []
    target = None
    for row in closes:
        if str(row.get("order_id") or "") == PP_ROLLBACK_ORDER:
            target = row
            break
    equity = bucket.get("equity")
    rollback_script = ROOT / "scripts" / "apply_equity_rollback.py"
    dry_run: dict[str, Any] = {"skipped": True, "reason": "state missing"}
    if DEFAULT_STATE.is_file() and rollback_script.is_file():
        proc = subprocess.run(
            [
                sys.executable,
                str(rollback_script),
                "--state",
                str(DEFAULT_STATE),
                "--order-id",
                PP_ROLLBACK_ORDER,
                "--dry-run",
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        try:
            dry_run = json.loads(proc.stdout) if proc.returncode == 0 else {"error": proc.stderr or proc.stdout}
        except json.JSONDecodeError:
            dry_run = {"error": proc.stdout or proc.stderr, "exit_code": proc.returncode}

    net_to_reverse = float(dry_run.get("net_pnl_to_reverse") or 0.0) if isinstance(dry_run, dict) else 0.0
    if target and target.get("new_equity") is not None:
        recommendation = "SKIP_ROLLBACK"
        reason = "权益已在标记 audit_invalid_close 时恢复到 new_equity；dry-run 待扣回 PnL=0"
    elif net_to_reverse == 0:
        recommendation = "SKIP_ROLLBACK"
        reason = "apply_equity_rollback dry-run net_pnl_to_reverse=0"
    else:
        recommendation = "EQUITY_ROLLBACK_REQUIRES_APPROVAL"
        reason = f"待扣回 net_pnl={net_to_reverse}"

    return {
        "order_id": PP_ROLLBACK_ORDER,
        "current_equity": equity,
        "audit_invalid_close": target,
        "dry_run": dry_run,
        "recommendation": recommendation,
        "reason": reason,
    }


def _symbol_review_flags(state: dict[str, Any], opens: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_symbol: dict[str, list[dict[str, Any]]] = {}
    for row in opens:
        by_symbol.setdefault(row["symbol"], []).append(row)

    flags: list[dict[str, Any]] = []
    symbols = state.get("symbols") or {}
    for sym, positions in sorted(by_symbol.items()):
        bucket = symbols.get(sym) if isinstance(symbols, dict) else {}
        invalid_n = len((bucket or {}).get("audit_invalid_positions") or [])
        invalid_close_n = len((bucket or {}).get("audit_invalid_closes") or [])
        item: dict[str, Any] = {
            "symbol": sym,
            "open_count": len(positions),
            "strategies": sorted({p["strategy_id"] for p in positions if p["strategy_id"]}),
            "audit_invalid_positions": invalid_n,
            "audit_invalid_closes": invalid_close_n,
            "priority_review": sym in REVIEW_SYMBOLS or len(positions) > 1,
        }
        if len(positions) > 1:
            item["note"] = "同品种多定式并行持仓，需沙盒图复核是否符合组合规则"
        elif sym == "PGUSDT":
            item["note"] = "液化气 PG：三定式并行，重点复核阵营与 DS01"
        elif sym == "LHUSDT":
            item["note"] = "生猪 LH：重点复核方向与 pending 一致性"
        elif sym == "PPUSDT":
            item["note"] = "聚丙烯 PP：坏行情已结案，当前仅观察 DS03 持仓"
        flags.append(item)
    return flags


def build_pack(
    *,
    state_path: Path = DEFAULT_STATE,
    manifest_path: Path = DEFAULT_MANIFEST,
) -> dict[str, Any]:
    state = _load_json(state_path)
    manifest = _load_json(manifest_path)
    opens = _collect_open_positions(state)
    pp = _pp_equity_assessment(state)
    flags = _symbol_review_flags(state, opens)

    contracts = {}
    for row in opens:
        code = row["symbol"].replace("USDT", "")
        contracts[code] = _manifest_contract(manifest, code)

    return {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "mode": "read_only_approval_pack",
        "state_path": str(state_path),
        "manifest_path": str(manifest_path) if manifest_path.is_file() else None,
        "summary": {
            "symbol_buckets": len(state.get("symbols") or {}),
            "open_positions": len(opens),
            "pp_equity_recommendation": pp["recommendation"],
            "priority_review_symbols": sum(1 for f in flags if f.get("priority_review")),
        },
        "pp_equity": pp,
        "open_positions": opens,
        "manifest_contracts_for_opens": contracts,
        "symbol_review_flags": flags,
        "disclaimer": "只读清单；不得静默删除持仓或自动改 equity；apply 须显式 --apply 与人工确认",
    }


def render_markdown(pack: dict[str, Any]) -> str:
    summary = pack.get("summary") or {}
    pp = pack.get("pp_equity") or {}
    lines = [
        "# Domestic paper_state 人工审批包",
        "",
        f"生成时间：{pack.get('generated_at')}",
        "",
        "## 摘要",
        "",
        f"- 持仓数：**{summary.get('open_positions', 0)}**",
        f"- PP 权益建议：**{pp.get('recommendation')}** — {pp.get('reason')}",
        f"- 优先复核品种：**{summary.get('priority_review_symbols', 0)}**",
        "",
        "## 1. PP 权益回滚候选",
        "",
        f"- order_id：`{pp.get('order_id')}`",
        f"- 当前 PP equity：`{pp.get('current_equity')}`",
        f"- **裁定：{pp.get('recommendation')}**",
        f"- 说明：{pp.get('reason')}",
        "",
        "## 2. 当前开仓列表（只读）",
        "",
        "| 品种 | 定式 | 方向 | 开仓时间 | 价 | 守护 |",
        "|------|------|------|----------|-----|------|",
    ]
    for row in pack.get("open_positions") or []:
        lines.append(
            f"| {row.get('symbol')} | {row.get('strategy_id')} | {row.get('direction')} "
            f"| {row.get('entry_time')} | {row.get('entry_price')} | {row.get('current_stop')} |"
        )
    lines.extend(["", "## 3. 优先复核标记", ""])
    for flag in pack.get("symbol_review_flags") or []:
        if not flag.get("priority_review"):
            continue
        note = flag.get("note") or ""
        lines.append(
            f"- **{flag.get('symbol')}**：{flag.get('open_count')} 仓 · "
            f"定式 {', '.join(flag.get('strategies') or [])} · "
            f"invalid_pos={flag.get('audit_invalid_positions')} · {note}"
        )
    lines.extend(
        [
            "",
            "## 4. 人工动作边界",
            "",
            "- PP 权益：**无需**执行 `apply_equity_rollback.py --apply`（PnL 已归零 / equity 已恢复）。",
            "- 旧主连触发的历史仓：**不得**静默删除；若需重算须先备份 + 用户书面确认。",
            "- PG 三仓并行：建议下一批 S2/沙盒图按定式分别审计，不在本包自动 apply。",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Render domestic paper_state approval pack")
    parser.add_argument("--state", type=Path, default=DEFAULT_STATE)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--out-dir", type=Path, default=ROOT / "results" / "paper_state_approval")
    args = parser.parse_args()

    pack = build_pack(state_path=args.state, manifest_path=args.manifest)
    args.out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d")
    json_path = args.out_dir / f"paper_state_approval_{stamp}.json"
    md_path = args.out_dir / f"paper_state_approval_{stamp}.md"
    json_path.write_text(json.dumps(pack, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(render_markdown(pack), encoding="utf-8")
    print(json.dumps({"ok": True, "json": str(json_path), "markdown": str(md_path), "summary": pack["summary"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
