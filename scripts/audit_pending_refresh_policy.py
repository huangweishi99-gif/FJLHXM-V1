#!/usr/bin/env python3
"""Audit pending-order refresh and conflict-cancel policy.

This is a read-only contract audit. It verifies that pending orders are
refreshed by the radar loop, that production watchdogs use the expected refresh
cadence, and that filled orders suppress conflicting same-symbol candidates via
the shared monitor state instead of requiring a separate daily bulk reset.
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
for extra in (ROOT / "src", ROOT / "packages" / "fengji_core"):
    if str(extra) not in sys.path:
        sys.path.insert(0, str(extra))

from fengji_pending_orders import default_valid_until  # noqa: E402


@dataclass(frozen=True)
class CheckResult:
    name: str
    ok: bool
    detail: str

    def as_dict(self) -> dict[str, Any]:
        return {"name": self.name, "ok": self.ok, "detail": self.detail}


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def normalized(text: str) -> str:
    return text.replace("\\", "/")


def check_contains(name: str, text: str, tokens: list[str]) -> CheckResult:
    body = normalized(text)
    missing = [token for token in tokens if normalized(token) not in body]
    return CheckResult(name, not missing, "missing=" + ",".join(missing) if missing else "ok")


def check_radar_loop_refreshes_pending(root: Path) -> CheckResult:
    text = read_text(root / "src" / "fengji_radar_order_loop.py")
    return check_contains(
        "radar_loop_refreshes_pending_each_cycle",
        text,
        [
            'parser.add_argument("--loop-seconds", type=int, default=300)',
            "refresh_lock(lock_path)",
            "src\" / \"fengji_total_radar.py",
            "src\" / \"fengji_pending_orders.py",
            "--radar",
            "--out-dir",
            "--monitor-state",
            "pending_cmd.append(\"--include-triggered\")",
            "time.sleep(max(30, int(args.loop_seconds)))",
        ],
    )


def check_pending_order_valid_until_contract(root: Path) -> CheckResult:
    text = read_text(root / "src" / "fengji_pending_orders.py")
    source_check = check_contains(
        "pending_order_valid_until_source",
        text,
        [
            "def default_valid_until(",
            "anchor_time: str | None = None",
            "ts = pd.to_datetime(anchor_time or latest_time, errors=\"coerce\")",
            "pd.Timedelta(days=2)",
            "pd.Timedelta(hours=6)",
            "pd.Timedelta(hours=12)",
            "valid_until=default_valid_until(",
            "anchor_time=created",
            "json_path = out_dir / \"pending_orders.json\"",
            "json_path.write_text(",
        ],
    )
    if not source_check.ok:
        return source_check
    h1 = default_valid_until("2020-01-01 09:00:00", "H1", anchor_time="2026-07-10 10:00:00")
    d1 = default_valid_until("2020-01-01 09:00:00", "D1", anchor_time="2026-07-10 10:00:00")
    m15 = default_valid_until("2020-01-01 09:00:00", "M15", anchor_time="2026-07-10 10:00:00")
    ok = h1 == "2026-07-10 16:00:00" and d1 == "2026-07-12 10:00:00" and m15 == "2026-07-10 22:00:00"
    detail = "ok" if ok else f"h1={h1} d1={d1} m15={m15}"
    return CheckResult("pending_order_valid_until_anchor", ok, detail)


def check_watchdog_refresh_cadence(root: Path) -> CheckResult:
    domestic = read_text(root / "scripts" / "watchdog_domestic.ps1")
    overseas = read_text(root / "scripts" / "watchdog_overseas.sh")
    return check_contains(
        "watchdog_refresh_cadence",
        domestic + "\n" + overseas,
        [
            "--include-triggered --loop-seconds 600",
            "src\\fengji_futures_pending_order_monitor.py",
            "--loop-seconds 5 --max-ds01-entries 3",
            "--enforce-valid-until",
            "--include-triggered --loop-seconds 900",
            "src/fengji_pending_order_monitor.py",
            "--loop-seconds 5 >> pending_order_monitor.log",
        ],
    )


def check_monitor_filters_cancelled_orders(root: Path) -> CheckResult:
    crypto = read_text(root / "src" / "fengji_pending_order_monitor.py")
    futures = read_text(root / "src" / "fengji_futures_pending_order_monitor.py")
    return check_contains(
        "monitor_filters_cancelled_orders_and_setups",
        crypto + "\n" + futures,
        [
            'str(order.get("status", "")).upper() in {"ACTIVE", "READY_TRIGGERED"}',
            'str(order.get("order_id", "")) not in cancelled_ids',
            "order_setup_key(order) not in cancelled_setup_keys",
            "and not order_expired(order)",
            'getattr(args, "enforce_valid_until", False)',
            "cancel_conflicting_orders(state, order, orders)",
        ],
    )


def check_conflict_cancel_contract(root: Path) -> CheckResult:
    audit = read_text(root / "scripts" / "audit_pending_order_contract.py")
    tests = read_text(root / "tests" / "test_audit_pending_order_contract.py")
    return check_contains(
        "conflict_cancel_contract_is_covered",
        audit + "\n" + tests,
        [
            "check_conflict_cancel_non_ds01",
            "check_conflict_cancel_ds01_add_kept",
            "check_cancel_records",
            "cancel_reason\") == \"conflict_after_fill\"",
            "state[\"cancelled_order_ids\"]",
            "state.get(\"cancelled_setup_keys\")",
            "test_conflict_cancel_contract_keeps_ds01_same_direction_add",
            "test_conflict_cancel_contract_cancels_non_ds01_same_symbol_orders",
        ],
    )


def runtime_snapshot(root: Path) -> dict[str, Any]:
    orders_path = root / "runtime" / "fengji_pending_orders" / "pending_orders.json"
    state_path = root / "runtime" / "fengji_pending_orders" / "state.json"
    futures_state_path = root / "runtime" / "fengji_pending_orders" / "futures_pending_state.json"
    order_count: int | None = None
    if orders_path.is_file():
        try:
            payload = json.loads(orders_path.read_text(encoding="utf-8"))
            order_count = len(payload) if isinstance(payload, list) else None
        except Exception:
            order_count = None
    return {
        "orders_path": str(orders_path),
        "orders_exists": orders_path.is_file(),
        "order_count": order_count,
        "crypto_state_exists": state_path.is_file(),
        "futures_state_exists": futures_state_path.is_file(),
    }


def policy_summary() -> dict[str, str]:
    return {
        "pre_open_bulk_refresh": (
            "not required by current contract; radar_order_loop refreshes radar and rewrites "
            "pending_orders.json every production cycle"
        ),
        "domestic_refresh": "watchdog_domestic uses radar loop 600s and pending monitor 5s with valid_until enforcement",
        "overseas_refresh": "watchdog_overseas uses radar loop 900s and pending monitor 5s",
        "after_fill_conflict_cancel": (
            "shared monitor state cancels same-symbol conflicts; DS01 preserves same-direction DS01 add orders"
        ),
    }


def run_checks(root: Path = ROOT) -> list[CheckResult]:
    return [
        check_radar_loop_refreshes_pending(root),
        check_pending_order_valid_until_contract(root),
        check_watchdog_refresh_cadence(root),
        check_monitor_filters_cancelled_orders(root),
        check_conflict_cancel_contract(root),
    ]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit pending refresh and conflict-cancel policy.")
    parser.add_argument("--root", default=str(ROOT))
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = Path(args.root).resolve()
    checks = run_checks(root)
    failures = [check for check in checks if not check.ok]
    payload = {
        "checks": [check.as_dict() for check in checks],
        "failures": len(failures),
        "policy": policy_summary(),
        "runtime": runtime_snapshot(root),
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
