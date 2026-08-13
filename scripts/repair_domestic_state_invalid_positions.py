from __future__ import annotations

import argparse
import csv
import json
import shutil
from contextlib import nullcontext
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any


ACTIVE_PENDING_STATUSES = {"ACTIVE", "READY_TRIGGERED", "TRIGGERED"}


try:
    from fengji_core.state_lock import file_lock
except Exception:
    file_lock = None


def parse_time(value: Any) -> datetime:
    text = str(value or "").strip()[:19]
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%Y/%m/%d %H:%M:%S"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return datetime.min


def normalize_symbol(symbol: Any) -> str:
    text = str(symbol or "").strip().upper().replace("-", "").replace("_", "")
    if text and not text.endswith("USDT") and not text.isdigit():
        text += "USDT"
    return text


def side_text(value: Any) -> str:
    if value in {1, "1", "long", "LONG", "多", "buy"}:
        return "long"
    if value in {-1, "-1", "short", "SHORT", "空", "sell"}:
        return "short"
    text = str(value or "").strip().lower()
    return text if text in {"long", "short"} else ""


def safe_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def load_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def save_json(path: Path, data: dict[str, Any]) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    tmp.replace(path)


def load_pending_sides(path: Path) -> dict[str, dict[str, Any]]:
    if not path.is_file():
        return {}
    out: dict[str, dict[str, Any]] = {}
    with path.open("r", newline="", encoding="utf-8-sig") as fh:
        for row in csv.DictReader(fh):
            status = str(row.get("status") or row.get("radar_status") or "").strip().upper()
            if status not in ACTIVE_PENDING_STATUSES:
                continue
            side = side_text(row.get("side"))
            if not side:
                continue
            symbol = normalize_symbol(row.get("symbol"))
            latest = parse_time(row.get("latest_time") or row.get("created_at"))
            old = out.get(symbol)
            if old is None or latest >= old.get("latest_time", datetime.min):
                out[symbol] = {
                    "side": side,
                    "os_camp": str(row.get("os_camp") or "").strip().lower(),
                    "latest_time": latest,
                }
    return out


def invalid_reason(symbol: str, position: dict[str, Any], pending: dict[str, dict[str, Any]], now: datetime) -> str:
    entry_time = parse_time(position.get("entry_time") or position.get("created_at"))
    if entry_time == datetime.min:
        return "invalid entry_time"
    if entry_time < datetime(2020, 1, 1) or entry_time > now + timedelta(days=1):
        return "future or out-of-range entry_time"
    if safe_float(position.get("entry_price") or position.get("trigger_price")) <= 0:
        return "invalid entry_price"

    side = side_text(position.get("direction") or position.get("side"))
    current = pending.get(normalize_symbol(symbol))
    if current and side and side != current["side"]:
        pending_time = current.get("latest_time", datetime.min)
        if pending_time != datetime.min and pending_time.date() >= entry_time.date():
            return f"contradicted by current pending side={current['side']} camp={current.get('os_camp', '')}"
    return ""


def repair_state(state: dict[str, Any], pending: dict[str, dict[str, Any]], *, apply: bool) -> list[dict[str, Any]]:
    now = datetime.now()
    audit_time = now.strftime("%Y-%m-%d %H:%M:%S")
    findings: list[dict[str, Any]] = []
    symbols = state.get("symbols") or {}
    if not isinstance(symbols, dict):
        return findings

    for symbol, symbol_state in symbols.items():
        if not isinstance(symbol_state, dict):
            continue
        kept: list[dict[str, Any]] = []
        for position in symbol_state.get("open_positions") or []:
            if not isinstance(position, dict) or position.get("closed"):
                kept.append(position)
                continue
            reason = invalid_reason(str(position.get("symbol") or symbol), position, pending, now)
            if not reason:
                kept.append(position)
                continue
            finding = {
                "symbol": normalize_symbol(position.get("symbol") or symbol),
                "strategy_id": str(position.get("strategy_id") or ""),
                "side": side_text(position.get("direction") or position.get("side")),
                "entry_time": str(position.get("entry_time") or ""),
                "entry_price": safe_float(position.get("entry_price") or position.get("trigger_price")),
                "reason": reason,
            }
            findings.append(finding)
            if apply:
                invalid = dict(position)
                invalid.update(
                    {
                        "closed": True,
                        "audit_invalid": True,
                        "audit_invalid_at": audit_time,
                        "audit_invalid_reason": reason,
                    }
                )
                symbol_state.setdefault("audit_invalid_positions", []).append(invalid)
                key = str(position.get("key") or position.get("order_id") or position.get("trade_key") or "")
                if key:
                    symbol_state.setdefault("closed_entries", []).append(key)
                    symbol_state.setdefault("audit_invalid_entries", []).append(key)
        if apply:
            symbol_state["open_positions"] = kept
            symbol_state["last_updated"] = audit_time
    if apply and findings:
        state["last_audit_invalid_repair_at"] = audit_time
    return findings


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--state", required=True, type=Path)
    parser.add_argument("--pending", required=True, type=Path)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    pending = load_pending_sides(args.pending)
    lock_cm = file_lock(args.state) if args.apply and file_lock is not None else nullcontext()
    with lock_cm:
        state = load_json(args.state)
        findings = repair_state(state, pending, apply=args.apply)
        if args.apply and findings:
            backup = args.state.with_suffix(args.state.suffix + ".bak")
            if args.state.is_file() and not backup.exists():
                shutil.copy2(args.state, backup)
            save_json(args.state, state)

    action = "INVALIDATED" if args.apply else "WOULD_INVALIDATE"
    for item in findings:
        print(
            f"{action} {item['symbol']} {item['strategy_id']} {item['side']} "
            f"{item['entry_time']} {item['entry_price']} {item['reason']}"
        )
    print(f"count={len(findings)} apply={args.apply}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
