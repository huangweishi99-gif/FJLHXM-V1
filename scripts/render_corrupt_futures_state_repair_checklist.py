from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any


def now_text() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def load_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def count(plan: dict[str, Any], key: str) -> int:
    counts = plan.get("counts") or {}
    try:
        return int(counts.get(key) or 0)
    except (TypeError, ValueError):
        return 0


def decision(plan: dict[str, Any]) -> tuple[str, str]:
    if bool(plan.get("apply")):
        return (
            "APPLIED_REVIEW_REQUIRED",
            "This plan was generated after apply=True; verify backups, archived records, monitor locks, and equity manually.",
        )
    invalidated = count(plan, "invalidated_positions")
    released = count(plan, "released_monitor_locks")
    equity = count(plan, "equity_rollback_candidates")
    invalid_closes = count(plan, "already_invalid_closes")
    targets = count(plan, "targets")

    if invalidated > 0 or released > 0:
        return (
            "APPLY_REQUIRES_CONFIRMATION",
            "State/monitor changes are proposed. Apply only after manual evidence review and backup confirmation.",
        )
    if equity > 0:
        return (
            "EQUITY_REVIEW_REQUIRED",
            "No state/monitor repair is needed, but fake PnL exists. Equity rollback requires separate manual approval.",
        )
    if invalid_closes > 0 or targets > 0:
        return (
            "AUDIT_ONLY_NO_APPLY",
            "Targets are already archived or no writable residue remains. Keep audit evidence; do not apply repair.",
        )
    return ("NO_ACTION", "No target, position, lock, invalid close, or equity candidate was found.")


def bullet_list(values: list[Any], empty: str = "None") -> list[str]:
    if not values:
        return [f"- {empty}"]
    return [f"- `{value}`" for value in values]


def record_line(record: dict[str, Any]) -> str:
    symbol = record.get("symbol") or record.get("_symbol") or ""
    strategy = record.get("strategy_id") or ""
    order_id = record.get("order_id") or ""
    trade_key = record.get("trade_key") or record.get("key") or ""
    entry_time = record.get("entry_time") or ""
    price = record.get("entry_price") or record.get("exit_price") or record.get("net_pnl_to_reverse") or ""
    parts = [str(item) for item in (symbol, strategy, order_id or trade_key, entry_time, price) if str(item)]
    return "- " + " | ".join(parts)


def command_block(plan: dict[str, Any], *, apply: bool) -> str:
    audit = plan.get("audit") or "<audit.json>"
    state = plan.get("state") or "<state_futures_v2.json>"
    monitor = plan.get("monitor_state") or "<futures_pending_state.json>"
    args = [
        "python scripts\\repair_corrupt_futures_state_from_audit.py",
        f"--audit \"{audit}\"",
        f"--state \"{state}\"",
    ]
    if monitor:
        args.append(f"--monitor-state \"{monitor}\"")
    args.append("--out \"runtime\\logs\\corrupt_futures_state_repair_plan_RECHECK.json\"")
    if apply:
        args.append("--apply")
    return " ".join(args)


def render_markdown(plan: dict[str, Any], title: str) -> str:
    status, explanation = decision(plan)
    counts = plan.get("counts") or {}
    released = plan.get("released_monitor_locks") or {}
    equity_candidates = plan.get("equity_rollback_candidates") or []
    invalidated_positions = plan.get("invalidated_positions") or []
    invalid_closes = plan.get("already_invalid_closes") or []
    targets = plan.get("targets") or []

    lines: list[str] = [
        f"# {title}",
        "",
        f"- Generated at: `{now_text()}`",
        f"- Repair plan: `{plan.get('audit', '')}`",
        f"- State file: `{plan.get('state', '')}`",
        f"- Monitor state: `{plan.get('monitor_state', '')}`",
        f"- Decision: **{status}**",
        f"- Reason: {explanation}",
        "",
        "## 1. Counts",
        "",
    ]
    for key in (
        "targets",
        "invalidated_positions",
        "released_monitor_locks",
        "already_invalid_closes",
        "equity_rollback_candidates",
    ):
        lines.append(f"- {key}: `{counts.get(key, 0)}`")

    lines.extend(["", "## 2. Target IDs", ""])
    lines.extend(bullet_list(targets))

    lines.extend(["", "## 3. Proposed State/Monitor Actions", ""])
    lines.append("### 3.1 Open positions to archive")
    lines.extend([record_line(item) for item in invalidated_positions] or ["- None"])
    lines.extend(["", "### 3.2 Monitor locks to release/archive"])
    for list_name in ("filled_order_ids", "filled_setup_keys", "consumed_ds03_setup_keys"):
        lines.append(f"- {list_name}: `{len(released.get(list_name) or [])}`")
        lines.extend(f"  - `{item}`" for item in released.get(list_name) or [])
    lines.extend(["", "### 3.3 Already invalid closes"])
    lines.extend([record_line(item) for item in invalid_closes] or ["- None"])

    lines.extend(["", "## 4. Equity Review", ""])
    if equity_candidates:
        lines.append("- Equity rollback is **not automatic**. Review each candidate manually.")
        lines.extend(record_line(item) for item in equity_candidates)
    else:
        lines.append("- No equity rollback candidate.")

    lines.extend(
        [
            "",
            "## 5. Manual Checklist",
            "",
            "- [ ] The audit JSON was generated from the same symbol and corrupt K-line window.",
            "- [ ] The repair plan was produced without `--apply` first.",
            "- [ ] The state file and monitor state file paths are the live files intended for repair.",
            "- [ ] All target IDs can be traced to suspicious fill/close records or existing audit-invalid records.",
            "- [ ] Backups will be created before any apply action.",
            "- [ ] No peak/valley, camp conversion, or DS01-DS09 strategy rule is being changed.",
            "- [ ] If `equity_rollback_candidates > 0`, equity change has separate explicit approval.",
            "- [ ] If decision is `NO_ACTION`, `AUDIT_ONLY_NO_APPLY`, or `EQUITY_REVIEW_REQUIRED`, do not run apply.",
            "",
            "## 6. Commands",
            "",
            "Dry-run recheck:",
            "",
            "```powershell",
            command_block(plan, apply=False),
            "```",
            "",
            "Apply command template, only after approval:",
            "",
            "```powershell",
            command_block(plan, apply=True),
            "```",
            "",
            "## 7. Sign-off",
            "",
            "| Item | Result | Reviewer | Time |",
            "|---|---|---|---|",
            "| Evidence reviewed | Pending |  |  |",
            "| Backup confirmed | Pending |  |  |",
            "| Apply allowed | Pending |  |  |",
            "| Equity rollback allowed | Pending |  |  |",
        ]
    )
    return "\n".join(lines) + "\n"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Render a manual checklist from a corrupt futures state repair plan.")
    parser.add_argument("--plan", required=True, type=Path, help="JSON produced by repair_corrupt_futures_state_from_audit.py.")
    parser.add_argument("--out", required=True, type=Path, help="Markdown checklist output path.")
    parser.add_argument("--title", default="Corrupt Futures State Repair Manual Checklist")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    plan = load_json(args.plan)
    markdown = render_markdown(plan, args.title)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(markdown, encoding="utf-8")
    status, _ = decision(plan)
    print(f"checklist={args.out} decision={status}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
