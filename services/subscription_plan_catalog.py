"""Paid subscription list prices (personal WeChat QR; no merchant API)."""
from __future__ import annotations

from typing import Any

# Align with web/js/config.js PRICING_TIER_META · FJLHXM-V1 §4.6
PLAN_PRICING: dict[str, dict[str, Any]] = {
    "standard": {
        "amount_yuan": 99,
        "amount_fen": 9900,
        "display": "¥99",
        "display_with_period": "¥99/月",
    },
    "pro": {
        "amount_yuan": 299,
        "amount_fen": 29900,
        "display": "¥299",
        "display_with_period": "¥299/月",
    },
}


def plan_pricing(plan_id: str) -> dict[str, Any] | None:
    return PLAN_PRICING.get(str(plan_id or "").strip().lower())


def pricing_catalog() -> dict[str, dict[str, Any]]:
    return dict(PLAN_PRICING)
