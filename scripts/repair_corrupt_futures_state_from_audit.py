from __future__ import annotations

import argparse
import json
import shutil
from contextlib import nullcontext
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


try:
    from fengji_core.state_lock import file_lock
except Exception:
    file_lock = None


STATE_ID_LISTS = ("seen_entries", "closed_entries", "audit_invalid_entries")
MONITOR_LOCK_LISTS = ("filled_order_ids", "filled_setup_keys", "consumed_ds03_setup_keys")
AUDIT_RECORD_SECTIONS = ("suspicious", "events")


@dataclass
class RepairPlan:
    targets: set[str]
    invalidated_positions: list[dict[str, Any]]
    already_invalid_closes: list[dict[str, Any]]
    released_monitor_locks: dict[str, list[str]]
    equity_rollback_candidates: list[dict[str, Any]]

    def counts(self) -> dict[str, int]:
        return {
            "targets": len(self.targets),
            "invalidated_positions": len(self.invalidated_positions),
            "already_invalid_closes": len(self.already_invalid_closes),
            "released_monitor_locks": sum(len(items) for items in self.released_monitor_locks.values()),
            "equity_rollback_candidates": len(self.equity_rollback_candidates),
        }


def now_stamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def audit_time() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def load_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def save_json(path: Path, payload: dict[str, Any]) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    tmp.replace(path)


def split_ids(value: str) -> set[str]:
    return {item.strip() for item in str(value or "").replace(";", ",").split(",") if item.strip()}


def ids_from_record(record: dict[str, Any]) -> set[str]:
    out: set[str] = set()
    for key in ("order_id", "setup_key", "trade_key", "key", "id"):
        value = str(record.get(key) or "").strip()
        if value:
            out.add(value)
            if value.startswith("pending|"):
                out.add(value.split("|", 1)[1])
    return out


def target_matches_value(value: Any, targets: set[str]) -> bool:
    text = str(value or "")
    if not text:
        return False
    return any(target and (target == text or target in text) for target in targets)


def target_matches_record(record: dict[str, Any], targets: set[str]) -> bool:
    for value in ids_from_record(record):
        if target_matches_value(value, targets):
            return True
    composite = "|".join(str(record.get(key) or "") for key in ("symbol", "strategy_id", "entry_time", "setup_key"))
    return target_matches_value(composite, targets)


def collect_targets(audit: dict[str, Any], explicit_targets: set[str]) -> set[str]:
    targets = set(explicit_targets)
    for section in AUDIT_RECORD_SECTIONS:
        records = audit.get(section) or []
        if not isinstance(records, list):
            continue
        for record in records:
            if not isinstance(record, dict):
                continue
            reasons = record.get("_suspicious_reasons") or []
            if section == "suspicious" or reasons:
                targets.update(ids_from_record(record))
    state = audit.get("state") or {}
    if isinstance(state, dict):
        for symbol_state in state.values():
            if not isinstance(symbol_state, dict):
                continue
            for record in symbol_state.get("audit_invalid_closes") or []:
                if isinstance(record, dict):
                    targets.update(ids_from_record(record))
    return {target for target in targets if target}


def add_unique(items: list[Any], value: Any) -> None:
    if value not in items:
        items.append(value)


def plan_state_repair(
    state: dict[str, Any],
    targets: set[str],
    *,
    reason: str,
    apply: bool,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    invalidated_positions: list[dict[str, Any]] = []
    already_invalid_closes: list[dict[str, Any]] = []
    equity_candidates: list[dict[str, Any]] = []
    symbols = state.get("symbols") or {}
    if not isinstance(symbols, dict):
        return invalidated_positions, already_invalid_closes, equity_candidates

    stamp = audit_time()
    for symbol, symbol_state in symbols.items():
        if not isinstance(symbol_state, dict):
            continue
        kept_positions: list[dict[str, Any]] = []
        for position in symbol_state.get("open_positions") or []:
            if not isinstance(position, dict) or not target_matches_record(position, targets):
                kept_positions.append(position)
                continue
            invalid = dict(position)
            invalid.update(
                {
                    "closed": True,
                    "audit_invalid": True,
                    "audit_invalid_at": stamp,
                    "audit_invalid_reason": reason,
                    "audit_invalid_source": "repair_corrupt_futures_state_from_audit",
                }
            )
            invalidated_positions.append(invalid)
            if apply:
                symbol_state.setdefault("audit_invalid_positions", []).append(invalid)
                for value in ids_from_record(position):
                    add_unique(symbol_state.setdefault("closed_entries", []), value)
                    add_unique(symbol_state.setdefault("audit_invalid_entries", []), value)
        if apply:
            symbol_state["open_positions"] = kept_positions
            if invalidated_positions:
                symbol_state["last_updated"] = stamp

        for record in symbol_state.get("audit_invalid_closes") or []:
            if not isinstance(record, dict) or not target_matches_record(record, targets):
                continue
            already_invalid_closes.append(record)
            pnl = record.get("fake_net_pnl", record.get("net_pnl"))
            try:
                pnl_value = float(pnl)
            except (TypeError, ValueError):
                pnl_value = None
            if pnl_value is not None:
                equity_candidates.append(
                    {
                        "symbol": symbol,
                        "order_id": record.get("order_id", ""),
                        "trade_key": record.get("trade_key", ""),
                        "net_pnl_to_reverse": pnl_value,
                    }
                )
    if apply and invalidated_positions:
        state["last_corrupt_state_repair_at"] = stamp
    return invalidated_positions, already_invalid_closes, equity_candidates


def plan_monitor_repair(monitor: dict[str, Any], targets: set[str], *, apply: bool) -> dict[str, list[str]]:
    released: dict[str, list[str]] = {name: [] for name in MONITOR_LOCK_LISTS}
    for list_name in MONITOR_LOCK_LISTS:
        values = monitor.get(list_name)
        if not isinstance(values, list):
            continue
        kept: list[Any] = []
        for value in values:
            if target_matches_value(value, targets):
                released[list_name].append(str(value))
            else:
                kept.append(value)
        if apply:
            monitor[list_name] = kept
            archive_name = f"audit_invalid_{list_name}"
            for value in released[list_name]:
                add_unique(monitor.setdefault(archive_name, []), value)
    if apply and any(released.values()):
        monitor["last_corrupt_state_repair_at"] = audit_time()
    return released


def build_repair_plan(
    *,
    audit: dict[str, Any],
    state: dict[str, Any],
    monitor: dict[str, Any],
    explicit_targets: set[str],
    reason: str,
    apply: bool,
) -> RepairPlan:
    targets = collect_targets(audit, explicit_targets)
    invalidated, already_invalid, equity_candidates = plan_state_repair(
        state,
        targets,
        reason=reason,
        apply=apply,
    )
    released = plan_monitor_repair(monitor, targets, apply=apply)
    return RepairPlan(
        targets=targets,
        invalidated_positions=invalidated,
        already_invalid_closes=already_invalid,
        released_monitor_locks=released,
        equity_rollback_candidates=equity_candidates,
    )


def backup_file(path: Path, backup_dir: Path) -> str:
    if not path.is_file():
        return ""
    backup_dir.mkdir(parents=True, exist_ok=True)
    target = backup_dir / path.name
    if target.exists():
        target = backup_dir / f"{path.stem}_{now_stamp()}{path.suffix}"
    shutil.copy2(path, target)
    return str(target)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Apply a controlled simulated-state repair from a corrupt-data audit.")
    parser.add_argument("--audit", required=True, type=Path, help="JSON generated by audit_corrupt_futures_state.py.")
    parser.add_argument("--state", required=True, type=Path, help="state_futures_v2.json path.")
    parser.add_argument("--monitor-state", default=None, type=Path, help="futures_pending_state.json path.")
    parser.add_argument("--order-id", default="", help="Optional comma-separated order ids. Defaults to audit suspicious ids.")
    parser.add_argument("--reason", default="corrupt futures data audit confirmed", help="Audit invalid reason.")
    parser.add_argument("--backup-dir", default=None, type=Path)
    parser.add_argument("--out", default=None, type=Path, help="Optional repair plan JSON output.")
    parser.add_argument("--apply", action="store_true", help="Backup and write state/monitor changes.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    audit = load_json(args.audit)
    explicit_targets = split_ids(args.order_id)
    lock_cm = file_lock(args.state) if args.apply and file_lock is not None else nullcontext()

    backups: dict[str, str] = {}
    with lock_cm:
        state = load_json(args.state)
        monitor = load_json(args.monitor_state) if args.monitor_state else {}
        plan = build_repair_plan(
            audit=audit,
            state=state,
            monitor=monitor,
            explicit_targets=explicit_targets,
            reason=args.reason,
            apply=args.apply,
        )
        if args.apply:
            backup_dir = args.backup_dir or Path("runtime") / f"corrupt_state_repair_backup_{now_stamp()}"
            backups["state"] = backup_file(args.state, backup_dir)
            if args.monitor_state:
                backups["monitor_state"] = backup_file(args.monitor_state, backup_dir)
            save_json(args.state, state)
            if args.monitor_state:
                save_json(args.monitor_state, monitor)

    payload = {
        "generated_at": audit_time(),
        "apply": bool(args.apply),
        "audit": str(args.audit),
        "state": str(args.state),
        "monitor_state": str(args.monitor_state) if args.monitor_state else "",
        "reason": args.reason,
        "backups": backups,
        "targets": sorted(plan.targets),
        "counts": plan.counts(),
        "invalidated_positions": plan.invalidated_positions,
        "already_invalid_closes": plan.already_invalid_closes,
        "released_monitor_locks": plan.released_monitor_locks,
        "equity_rollback_candidates": plan.equity_rollback_candidates,
    }
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")

    counts = plan.counts()
    print(
        f"state_repair apply={bool(args.apply)} targets={counts['targets']} "
        f"invalidated_positions={counts['invalidated_positions']} "
        f"released_monitor_locks={counts['released_monitor_locks']} "
        f"already_invalid_closes={counts['already_invalid_closes']} "
        f"equity_rollback_candidates={counts['equity_rollback_candidates']}"
    )
    if args.out:
        print(f"repair_plan={args.out}")
    if not args.apply:
        print("dry_run=1")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
