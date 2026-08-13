#!/usr/bin/env python3
"""Audit domestic futures/A-stock Feishu notification wording.

This is a read-only contract audit. It smoke-tests domestic pending fill and
stop-exit notification text, checks the local source for legacy wording, and
summarizes current runtime files when present.
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


def prepend_import_path(path: Path) -> None:
    value = str(path)
    while value in sys.path:
        sys.path.remove(value)
    sys.path.insert(0, value)


for extra in (ROOT, ROOT / "packages" / "fengji_core", ROOT / "src"):
    prepend_import_path(extra)

from fengji_futures_pending_order_monitor import format_fill, format_stop_exit
from scripts.summarize_pending_effective_status import load_json, load_orders, summarize


STATUS_BOUGHT = "\u72b6\u6001: \u5df2\u4e70\u5165"
STATUS_SOLD = "\u72b6\u6001: \u5df2\u5356\u51fa"
STATUS_SELL_CLOSE = "\u72b6\u6001: \u5df2\u5356\u51fa\u5e73\u4ed3"
STATUS_BUY_CLOSE = "\u72b6\u6001: \u5df2\u4e70\u5165\u5e73\u4ed3"
TYPE_BOUGHT = "\u6d88\u606f\u7c7b\u578b: \u5df2\u4e70\u5165 +"
TYPE_SOLD = "\u6d88\u606f\u7c7b\u578b: \u5df2\u5356\u51fa +"
EXPECTED_CLOSE_15915 = "\u9884\u8ba1\u6302\u5355\u5e73\u4ed3\u4ef7\u683c: 15915"
EXPECTED_CLOSE_1117 = "\u9884\u8ba1\u6302\u5355\u5e73\u4ed3\u4ef7\u683c: 1117"
CLOSE_FILLED_15915 = "\u5e73\u4ed3\u4ef7\u683c\u5df2\u6210\u4ea4: 15915"
CLOSE_FILLED_1117 = "\u5e73\u4ed3\u4ef7\u683c\u5df2\u6210\u4ea4: 1117"
LEGACY_TRIGGER_PRICE = "\u6302\u5355\u89e6\u53d1\u4ef7"
LEGACY_SIM_FILL_PRICE = "\u6a21\u62df\u6210\u4ea4\u4ef7"


@dataclass(frozen=True)
class CheckResult:
    name: str
    ok: bool
    detail: str

    def as_dict(self) -> dict[str, Any]:
        return {"name": self.name, "ok": self.ok, "detail": self.detail}


def check_notification_wording() -> CheckResult:
    long_fill = format_fill(
        {
            "symbol": "CF",
            "strategy_id": "DS01",
            "timeframe": "D1",
            "side": "long",
            "trigger_price": 16195.0,
            "stop_price": 15915.0,
            "os_camp": "red",
            "setup": "smoke",
        },
        16195.0,
        {"timeframe": "15m", "date": "2026-07-13 01:30:00", "high": 16200.0, "low": 16155.0},
        "DS01 允许同向连续开仓",
    )
    short_fill = format_fill(
        {
            "symbol": "SA",
            "strategy_id": "DS03",
            "timeframe": "D1",
            "side": "short",
            "trigger_price": 1079.0,
            "stop_price": 1117.0,
            "os_camp": "blue",
            "setup": "smoke",
        },
        1079.0,
        {"timeframe": "15m", "date": "2026-07-07 05:45:00", "high": 1083.0, "low": 1076.0},
        "DS03 非连续定式允许首次开仓",
    )
    long_close = format_stop_exit(
        "CF",
        {"strategy_id": "DS01", "side": 1, "entry_time": "2026-07-13", "entry_price": 16195.0, "initial_stop": 15915.0},
        15915.0,
        {"net_pnl": -10.0},
        {"timeframe": "15m", "date": "2026-07-13 10:00:00"},
    )
    short_close = format_stop_exit(
        "SA",
        {"strategy_id": "DS03", "side": -1, "entry_time": "2026-07-07", "entry_price": 1079.0, "initial_stop": 1117.0},
        1117.0,
        {"net_pnl": -10.0},
        {"timeframe": "15m", "date": "2026-07-07 10:00:00"},
    )
    required = {
        "long_fill_has_bought": STATUS_BOUGHT in long_fill and TYPE_BOUGHT in long_fill,
        "short_fill_has_sold": STATUS_SOLD in short_fill and TYPE_SOLD in short_fill,
        "long_fill_has_expected_close": EXPECTED_CLOSE_15915 in long_fill,
        "short_fill_has_expected_close": EXPECTED_CLOSE_1117 in short_fill,
        "long_close_has_sell_close": STATUS_SELL_CLOSE in long_close and CLOSE_FILLED_15915 in long_close,
        "short_close_has_buy_close": STATUS_BUY_CLOSE in short_close and CLOSE_FILLED_1117 in short_close,
        "legacy_fill_fields_removed": LEGACY_TRIGGER_PRICE not in long_fill and LEGACY_SIM_FILL_PRICE not in long_fill,
    }
    failed = [name for name, ok in required.items() if not ok]
    return CheckResult("domestic_feishu_status_wording", not failed, "ok" if not failed else f"failed={failed}")


def check_source_contract(path: Path = ROOT / "src" / "fengji_futures_pending_order_monitor.py") -> CheckResult:
    text = path.read_text(encoding="utf-8")
    required = [
        "\u5df2\u4e70\u5165",
        "\u5df2\u5356\u51fa",
        "\u5df2\u5356\u51fa\u5e73\u4ed3",
        "\u5df2\u4e70\u5165\u5e73\u4ed3",
        "\u6302\u5355\u4e70\u5165\u4ef7\u683c\u5df2\u6210\u4ea4",
        "\u6302\u5355\u5356\u51fa\u4ef7\u683c\u5df2\u6210\u4ea4",
        "\u9884\u8ba1\u6302\u5355\u5e73\u4ed3\u4ef7\u683c",
    ]
    forbidden = [
        "\u5cf0\u6781\u603b\u5b9a\u5f0f01-08\u56fd\u5185\u671f\u8d27A\u80a1\u6a21\u62df\u6302\u5355\u89e6\u53d1",
        LEGACY_TRIGGER_PRICE + ":",
        LEGACY_SIM_FILL_PRICE + ":",
    ]
    missing = [item for item in required if item not in text]
    offenders = [item for item in forbidden if item in text]
    ok = not missing and not offenders
    detail = "ok" if ok else f"missing={missing} offenders={offenders}"
    return CheckResult("domestic_pending_monitor_notification_source", ok, detail)


def strategy_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        strategy = str(row.get("strategy_id") or row.get("strategy") or "").upper()
        if strategy:
            counts[strategy] = counts.get(strategy, 0) + 1
    return dict(sorted(counts.items()))


def paper_open_counts(paper_state: dict[str, Any]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for symbol_state in (paper_state.get("symbols") or {}).values():
        if not isinstance(symbol_state, dict):
            continue
        for position in symbol_state.get("open_positions") or []:
            if isinstance(position, dict) and not position.get("closed"):
                strategy = str(position.get("strategy_id") or "").upper()
                if strategy:
                    counts[strategy] = counts.get(strategy, 0) + 1
        open_position = symbol_state.get("open_position")
        if isinstance(open_position, dict) and not open_position.get("closed"):
            strategy = str(open_position.get("strategy_id") or "").upper()
            if strategy:
                counts[strategy] = counts.get(strategy, 0) + 1
    return dict(sorted(counts.items()))


def runtime_snapshot(root: Path, *, orders_file: str, state_file: str, paper_state_file: str, radar_file: str) -> dict[str, Any]:
    orders_path = root / orders_file
    state_path = root / state_file
    paper_path = root / paper_state_file
    radar_path = root / radar_file

    orders = load_orders(orders_path)
    state = load_json(state_path, {})
    paper_state = load_json(paper_path, {})
    radar_payload = load_json(radar_path, [])
    radar_rows = radar_payload if isinstance(radar_payload, list) else []
    summary = summarize(orders, state, paper_state) if orders_path.exists() else {}
    return {
        "available": {
            "orders": orders_path.exists(),
            "state": state_path.exists(),
            "paper_state": paper_path.exists(),
            "radar": radar_path.exists(),
        },
        "radar_strategy_counts": strategy_counts([row for row in radar_rows if isinstance(row, dict)]),
        "pending_strategy_counts": strategy_counts(orders),
        "effective_status_counts": summary.get("effective_status_counts", {}),
        "actionable_orders": summary.get("actionable_orders", 0),
        "review_candidate_orders": summary.get("review_candidate_orders", 0),
        "paper_open_strategy_counts": paper_open_counts(paper_state),
    }


def run_checks() -> list[CheckResult]:
    return [check_notification_wording(), check_source_contract()]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit domestic Feishu notification wording.")
    parser.add_argument("--root", default=".")
    parser.add_argument("--orders-file", default="runtime/fengji_pending_orders/pending_orders.json")
    parser.add_argument("--state-file", default="runtime/fengji_pending_orders/futures_pending_state.json")
    parser.add_argument("--paper-state-file", default="runtime/fengji_futures/state_futures_v2.json")
    parser.add_argument("--radar-file", default="runtime/fengji_radar/radar.json")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    checks = run_checks()
    failures = [check for check in checks if not check.ok]
    payload = {
        "checks": [check.as_dict() for check in checks],
        "failures": len(failures),
        "runtime": runtime_snapshot(
            Path(args.root),
            orders_file=args.orders_file,
            state_file=args.state_file,
            paper_state_file=args.paper_state_file,
            radar_file=args.radar_file,
        ),
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
