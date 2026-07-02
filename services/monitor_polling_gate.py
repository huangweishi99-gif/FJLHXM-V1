"""W17-prod: server-side monitor REST polling interval enforcement by subscription plan."""
from __future__ import annotations

import time
from typing import Any

from feature_gate import monitor_polling_interval_seconds, normalize_plan

MONITOR_POLL_BURST_SECONDS = 15
_MONITOR_POLL_STATE: dict[str, dict[str, float]] = {}


def reset_monitor_polling_state_for_tests() -> None:
    _MONITOR_POLL_STATE.clear()


def enforce_monitor_polling(*, user_key: str, plan: str, now: float | None = None) -> dict[str, Any]:
    """Gate monitor REST polling. Allows a short burst window per allowed refresh tick."""
    key = str(user_key or "").strip() or "anonymous"
    normalized_plan = normalize_plan(plan)
    min_interval = monitor_polling_interval_seconds(normalized_plan)
    moment = float(now if now is not None else time.time())
    state = _MONITOR_POLL_STATE.get(key) or {"gate_at": 0.0, "burst_until": 0.0}

    if moment <= state["burst_until"]:
        policy = {
            "allowed": True,
            "plan": normalized_plan,
            "min_interval_seconds": min_interval,
            "mode": "polling_burst",
            "retry_after_seconds": 0,
        }
        _MONITOR_POLL_STATE[key] = state
        return policy

    elapsed = moment - state["gate_at"]
    if state["gate_at"] > 0 and elapsed < min_interval:
        retry_after = max(min_interval - elapsed, 1.0)
        return {
            "allowed": False,
            "plan": normalized_plan,
            "min_interval_seconds": min_interval,
            "mode": "polling",
            "retry_after_seconds": retry_after,
        }

    state["gate_at"] = moment
    state["burst_until"] = moment + MONITOR_POLL_BURST_SECONDS
    _MONITOR_POLL_STATE[key] = state
    return {
        "allowed": True,
        "plan": normalized_plan,
        "min_interval_seconds": min_interval,
        "mode": "polling",
        "retry_after_seconds": 0,
    }


def attach_monitor_policy(payload: dict[str, Any], policy: dict[str, Any]) -> dict[str, Any]:
    body = dict(payload)
    body["monitor_policy"] = {
        "plan": policy.get("plan"),
        "min_interval_seconds": policy.get("min_interval_seconds"),
        "mode": policy.get("mode"),
    }
    return body
