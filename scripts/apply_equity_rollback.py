"""Apply an approved equity rollback for audit_invalid closes.

Conservative: backs up state, subtracts net_pnl from symbol/global equity under lock,
marks audit_invalid_closes with equity_rollback_applied. Does not delete trade history.
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages" / "fengji_core"))

from fengji_core.state_lock import update_state_file  # noqa: E402


def _now_text() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _symbol_from_order_id(order_id: str) -> str | None:
    text = str(order_id or "").strip().upper()
    if not text:
        return None
    if text.endswith("USDT"):
        return text.split("-", 1)[0] + "USDT" if "-" in text else text
    head = text.split("-", 1)[0]
    return head or None


def _find_close_record(state: dict[str, Any], order_id: str) -> tuple[str | None, dict[str, Any] | None]:
    for record in state.get("audit_invalid_closes") or []:
        if str(record.get("order_id", "")) == order_id:
            sym = str(record.get("symbol", "") or "").strip().upper() or _symbol_from_order_id(order_id)
            return sym or None, record
    for record in state.get("closed_trades") or []:
        if str(record.get("order_id", "")) == order_id:
            return None, record
    symbols = state.get("symbols") or {}
    if isinstance(symbols, dict):
        for symbol, bucket in symbols.items():
            if not isinstance(bucket, dict):
                continue
            for record in bucket.get("closed_trades") or []:
                if str(record.get("order_id", "")) == order_id:
                    return str(symbol), record
            for record in bucket.get("audit_invalid_closes") or []:
                if str(record.get("order_id", "")) == order_id:
                    return str(symbol), record
    return None, None


def _subtract_equity(state: dict[str, Any], symbol: str, net_pnl: float, order_id: str, reason: str) -> dict[str, Any]:
    symbols = state.setdefault("symbols", {})
    bucket = symbols.setdefault(symbol, {})
    for key in ("realized_pnl",):
        if key in bucket:
            bucket[key] = float(bucket.get(key, 0.0) or 0.0) - net_pnl
    if "initial_cash" in bucket:
        bucket["equity"] = float(bucket.get("initial_cash", 0.0) or 0.0) + float(bucket.get("realized_pnl", 0.0) or 0.0)
    elif "equity" in bucket:
        bucket["equity"] = float(bucket.get("equity", 0.0) or 0.0) - net_pnl

    money = state.get("money_mode")
    if isinstance(money, dict):
        if "total_realized_pnl" in money:
            money["total_realized_pnl"] = float(money.get("total_realized_pnl", 0.0) or 0.0) - net_pnl
        if "total_equity" in money:
            money["total_equity"] = float(money.get("total_equity", 0.0) or 0.0) - net_pnl

    rollback_meta = {
        "order_id": order_id,
        "symbol": symbol,
        "net_pnl_reversed": net_pnl,
        "applied_at": _now_text(),
        "reason": reason,
        "equity_rollback_applied": True,
    }
    state.setdefault("equity_rollbacks", []).append(rollback_meta)

    for collection_key in ("audit_invalid_closes", "closed_trades"):
        for record in state.get(collection_key) or []:
            if str(record.get("order_id", "")) == order_id:
                record["equity_rollback_applied"] = True
                record["equity_rollback_at"] = rollback_meta["applied_at"]
        sym_bucket = symbols.get(symbol) or {}
        for record in sym_bucket.get(collection_key) or []:
            if str(record.get("order_id", "")) == order_id:
                record["equity_rollback_applied"] = True
                record["equity_rollback_at"] = rollback_meta["applied_at"]

    return rollback_meta


def apply_rollback(state_path: Path, order_id: str, *, net_pnl: float | None, reason: str, dry_run: bool) -> dict[str, Any]:
    symbol_hint, record = _find_close_record(json.loads(state_path.read_text(encoding="utf-8")), order_id)
    if record is None:
        raise SystemExit(f"order_id not found in state: {order_id}")
    if record.get("equity_rollback_applied"):
        raise SystemExit(f"equity rollback already applied for {order_id}")
    amount = float(net_pnl if net_pnl is not None else record.get("net_pnl", 0.0) or 0.0)
    symbol = str(record.get("symbol") or symbol_hint or "").strip().upper()
    if not symbol:
        raise SystemExit(f"cannot resolve symbol for {order_id}")

    if dry_run:
        return {
            "dry_run": True,
            "order_id": order_id,
            "symbol": symbol,
            "net_pnl_to_reverse": amount,
            "state_path": str(state_path),
        }

    backup_dir = state_path.parent / "backups" / f"equity_rollback_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    backup_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(state_path, backup_dir / state_path.name)

    def mutator(state: dict[str, Any]) -> None:
        _subtract_equity(state, symbol, amount, order_id, reason)

    update_state_file(state_path, mutator)
    return {
        "dry_run": False,
        "order_id": order_id,
        "symbol": symbol,
        "net_pnl_reversed": amount,
        "backup_dir": str(backup_dir),
        "state_path": str(state_path),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Apply approved equity rollback for audit_invalid close")
    parser.add_argument("--state", required=True, help="paper state.json path")
    parser.add_argument("--order-id", required=True)
    parser.add_argument("--net-pnl", type=float, default=None, help="override net_pnl to reverse")
    parser.add_argument("--reason", default="approved audit_invalid equity rollback")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    result = apply_rollback(
        Path(args.state),
        args.order_id,
        net_pnl=args.net_pnl,
        reason=args.reason,
        dry_run=args.dry_run,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
