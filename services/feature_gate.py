"""W17-prod Feature Gate — server-side subscription limits (aligned with web/js/config.js)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from auth_service import normalize_plan

PLAN_TRIAL_DAYS = 7

PLAN_YEARS: dict[str, tuple[int, ...]] = {
    "free": (1,),
    "standard": (1, 3),
    "pro": (1, 3, 5),
}

PLAN_STRATEGIES: dict[str, frozenset[str]] = {
    "free": frozenset({"DS01", "DS02", "DS03"}),
    "standard": frozenset(
        {"DS01", "DS02", "DS03", "DS04", "DS05", "DS06", "DS07", "DS08", "DS09"}
    ),
    "pro": frozenset(
        {"TOTAL", "DS01", "DS02", "DS03", "DS04", "DS05", "DS06", "DS07", "DS08", "DS09"}
    ),
}

PLAN_WATCHLIST_LIMITS: dict[str, int] = {
    "free": 3,
    "standard": 20,
    "pro": 50,
}

PLAN_MONITOR_POLL_SECONDS: dict[str, int] = {
    "free": 900,
    "standard": 60,
    "pro": 30,
}


class FeatureGateError(ValueError):
    pass


def parse_iso_datetime(value: str | None) -> datetime | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def plan_expires_at_dt(auth_user: dict) -> datetime | None:
    explicit = parse_iso_datetime(str(auth_user.get("plan_expires_at") or ""))
    if explicit is not None:
        return explicit
    if normalize_plan(auth_user.get("plan_id")) != "free":
        return None
    created = parse_iso_datetime(str(auth_user.get("created_at") or ""))
    if created is None:
        return None
    return created + timedelta(days=PLAN_TRIAL_DAYS)


def is_plan_active(auth_user: dict | None, *, now: datetime | None = None) -> bool:
    if not auth_user:
        return True
    expires = plan_expires_at_dt(auth_user)
    if expires is None:
        return True
    moment = now or datetime.now(timezone.utc)
    return moment <= expires


def ensure_plan_active(auth_user: dict | None) -> None:
    if not auth_user:
        return
    if is_plan_active(auth_user):
        return
    plan = normalize_plan(auth_user.get("plan_id"))
    raise FeatureGateError(f"plan '{plan}' subscription expired; renew or upgrade to continue")


def effective_plan(*, auth_user: dict | None, client_plan: str | None = None) -> str:
    """JWT user plan wins. Without JWT, gated routes always treat as free (ignore client plan)."""
    if auth_user:
        return normalize_plan(auth_user.get("plan_id"))
    return "free"


def ensure_years_allowed(plan: str, years: int) -> None:
    allowed = PLAN_YEARS.get(normalize_plan(plan), PLAN_YEARS["free"])
    yrs = int(years)
    if yrs not in allowed:
        raise FeatureGateError(f"plan '{plan}' does not allow {yrs}-year backtest; allowed: {list(allowed)}")


def ensure_strategy_allowed(plan: str, strategy_id: str) -> None:
    key = normalize_plan(plan)
    sid = str(strategy_id or "TOTAL").upper()
    allowed = PLAN_STRATEGIES.get(key, PLAN_STRATEGIES["free"])
    if sid not in allowed:
        raise FeatureGateError(f"plan '{key}' does not allow strategy '{sid}'")


def monitor_polling_interval_seconds(plan: str) -> int:
    return int(PLAN_MONITOR_POLL_SECONDS.get(normalize_plan(plan), PLAN_MONITOR_POLL_SECONDS["free"]))
