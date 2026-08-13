#!/usr/bin/env python3
"""Audit pending-order trigger and conflict-cancel contract."""
from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
for extra in (ROOT / "src", ROOT / "packages" / "fengji_core"):
    if str(extra) not in sys.path:
        sys.path.insert(0, str(extra))

from fengji_futures_pending_order_monitor import bar_crossed  # noqa: E402
from fengji_pending_order_monitor import cancel_conflicting_orders, triggered  # noqa: E402
from fengji_pending_orders import DEFAULT_INCLUDE_STRATEGIES  # noqa: E402

EXPECTED_DEFAULT_STRATEGIES = {"DS01", "DS03", "DS04", "DS05", "DS07", "DS08", "DS09"}


@dataclass(frozen=True)
class CheckResult:
    name: str
    ok: bool
    detail: str

    def as_dict(self) -> dict[str, Any]:
        return {"name": self.name, "ok": self.ok, "detail": self.detail}


def check_default_strategies() -> CheckResult:
    actual = set(DEFAULT_INCLUDE_STRATEGIES)
    missing = sorted(EXPECTED_DEFAULT_STRATEGIES - actual)
    extra = sorted(actual - EXPECTED_DEFAULT_STRATEGIES)
    ok = not missing and not extra
    detail = "ok" if ok else f"missing={missing} extra={extra}"
    return CheckResult("default_pending_strategies", ok, detail)


def check_crypto_price_trigger() -> CheckResult:
    long_ok = triggered({"side": "long", "trigger_price": 100.0}, 100.0)
    long_block = not triggered({"side": "long", "trigger_price": 100.0}, 99.99)
    short_ok = triggered({"side": "short", "trigger_price": 100.0}, 100.0)
    short_block = not triggered({"side": "short", "trigger_price": 100.0}, 100.01)
    ok = long_ok and long_block and short_ok and short_block
    return CheckResult("crypto_price_trigger", ok, "ok" if ok else "long/short threshold mismatch")


def check_futures_bar_trigger() -> CheckResult:
    long_ok = bar_crossed(
        {"side": "long", "trigger_price": 100.0},
        {"high": 100.0, "low": 99.0},
    )
    long_block = not bar_crossed(
        {"side": "long", "trigger_price": 100.0},
        {"high": 99.99, "low": 98.0},
    )
    short_ok = bar_crossed(
        {"side": "short", "trigger_price": 100.0},
        {"high": 101.0, "low": 100.0},
    )
    short_block = not bar_crossed(
        {"side": "short", "trigger_price": 100.0},
        {"high": 101.0, "low": 100.01},
    )
    ok = long_ok and long_block and short_ok and short_block
    return CheckResult("futures_bar_trigger", ok, "ok" if ok else "high/low threshold mismatch")


def order(order_id: str, strategy: str, side: str, symbol: str = "BTCUSDT") -> dict[str, Any]:
    return {
        "order_id": order_id,
        "symbol": symbol,
        "strategy_id": strategy,
        "side": side,
        "setup_key": f"{symbol}|{strategy}|{side}|{order_id}",
    }


def check_conflict_cancel_non_ds01() -> CheckResult:
    state = {"filled_order_ids": ["fill"], "cancelled_order_ids": [], "cancelled_setup_keys": []}
    filled = order("fill", "DS03", "long")
    orders = [
        filled,
        order("same", "DS01", "long"),
        order("opp", "DS05", "short"),
        order("other_symbol", "DS05", "short", symbol="ETHUSDT"),
    ]
    cancelled = cancel_conflicting_orders(state, filled, orders)
    cancelled_ids = {item["order_id"] for item in cancelled}
    ok = cancelled_ids == {"same", "opp"} and state["cancelled_order_ids"] == ["opp", "same"]
    return CheckResult("conflict_cancel_non_ds01", ok, f"cancelled={sorted(cancelled_ids)}")


def check_conflict_cancel_ds01_add_kept() -> CheckResult:
    state = {"filled_order_ids": ["fill"], "cancelled_order_ids": [], "cancelled_setup_keys": []}
    filled = order("fill", "DS01", "long")
    orders = [
        filled,
        order("same_ds01", "DS01", "long"),
        order("same_ds03", "DS03", "long"),
        order("opp_ds01", "DS01", "short"),
    ]
    cancelled = cancel_conflicting_orders(state, filled, orders)
    cancelled_ids = {item["order_id"] for item in cancelled}
    ok = cancelled_ids == {"same_ds03", "opp_ds01"}
    return CheckResult("conflict_cancel_ds01_add_kept", ok, f"cancelled={sorted(cancelled_ids)}")


def check_cancel_records() -> CheckResult:
    state = {"filled_order_ids": ["fill"], "cancelled_order_ids": [], "cancelled_setup_keys": []}
    filled = order("fill", "DS05", "short")
    cancelled = cancel_conflicting_orders(state, filled, [filled, order("cancel_me", "DS07", "short")])
    ok = (
        len(cancelled) == 1
        and cancelled[0].get("event_type") == "cancel"
        and cancelled[0].get("cancel_reason") == "conflict_after_fill"
        and cancelled[0].get("filled_order_id") == "fill"
        and bool(state.get("cancelled_setup_keys"))
    )
    return CheckResult("conflict_cancel_record_fields", ok, "ok" if ok else "missing cancel audit fields")


def run_checks() -> list[CheckResult]:
    return [
        check_default_strategies(),
        check_crypto_price_trigger(),
        check_futures_bar_trigger(),
        check_conflict_cancel_non_ds01(),
        check_conflict_cancel_ds01_add_kept(),
        check_cancel_records(),
    ]


def main() -> int:
    checks = run_checks()
    failures = [check for check in checks if not check.ok]
    print(
        json.dumps(
            {"checks": [check.as_dict() for check in checks], "failures": len(failures)},
            ensure_ascii=False,
            indent=2,
        )
    )
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
