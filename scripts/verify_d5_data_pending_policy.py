#!/usr/bin/env python3
"""D5 验收：天勤凭证无代码默认 · 挂单撤销规则文档 · 雷达频率文档。"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def fail(msg: str) -> None:
    print(f"D5_VERIFY_FAIL: {msg}")
    sys.exit(1)


def check_tq_no_hardcoded_defaults() -> None:
    dm = ROOT / "data_manager_futures.py"
    text = dm.read_text(encoding="utf-8")
    if "require_tq_credentials" not in text:
        fail(f"{dm.name} 缺少 require_tq_credentials()")
    if re.search(
        r'getenv\s*\(\s*["\']TQ_(PHONE|PASS)["\']\s*,\s*["\'][^"\']+["\']',
        text,
    ):
        fail(f"{dm.name} 仍含 TQ_PHONE/TQ_PASS 的非空 getenv 默认值")


def check_docs() -> None:
    radar = ROOT / "docs" / "RADAR_REFRESH_SCHEDULE.md"
    cancel = ROOT / "docs" / "PENDING_ORDER_CANCEL_RULES.md"
    if not radar.is_file():
        fail("缺少 docs/RADAR_REFRESH_SCHEDULE.md")
    if not cancel.is_file():
        fail("缺少 docs/PENDING_ORDER_CANCEL_RULES.md")
    radar_text = radar.read_text(encoding="utf-8")
    if "900" not in radar_text:
        fail("RADAR_REFRESH_SCHEDULE.md 未记录海外生产 loop-seconds=900")
    if "600" not in radar_text:
        fail("RADAR_REFRESH_SCHEDULE.md 未记录国内 watchdog loop-seconds=600")


def check_cancel_rules_import() -> None:
    sys.path.insert(0, str(ROOT / "src"))
    from fengji_pending_order_monitor import cancel_conflicting_orders  # noqa: F401

    state: dict = {"cancelled_order_ids": [], "filled_order_ids": []}
    filled = {"order_id": "f1", "symbol": "BTCUSDT", "side": "long", "strategy_id": "DS03"}
    orders = [
        {"order_id": "f1", "symbol": "BTCUSDT", "side": "long", "strategy_id": "DS03"},
        {"order_id": "o1", "symbol": "BTCUSDT", "side": "short", "strategy_id": "DS01"},
        {"order_id": "o2", "symbol": "BTCUSDT", "side": "long", "strategy_id": "DS01"},
    ]
    cancelled = cancel_conflicting_orders(state, filled, orders)
    ids = {c["order_id"] for c in cancelled}
    if ids != {"o1", "o2"}:
        fail(f"DS03 成交应撤同品种其余单，实际 cancelled={ids}")


def main() -> None:
    check_tq_no_hardcoded_defaults()
    check_docs()
    check_cancel_rules_import()
    print("D5_VERIFY_OK")


if __name__ == "__main__":
    main()
