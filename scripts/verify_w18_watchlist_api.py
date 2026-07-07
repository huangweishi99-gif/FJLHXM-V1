from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
SERVICES = ROOT / "services"
if str(SERVICES) not in sys.path:
    sys.path.insert(0, str(SERVICES))

from db.custom_instruments import CUSTOM_PLAN_LIMITS, check_custom_request_quota, normalize_custom_plan  # noqa: E402
from watchlist_runtime_file_cache import runtime_cache_age_seconds  # noqa: E402


def verify_quota_alignment() -> list[str]:
    errors: list[str] = []
    if normalize_custom_plan("STANDARD") != "standard":
        errors.append("normalize_custom_plan standard mismatch")
    if CUSTOM_PLAN_LIMITS.get("standard") != 3 or CUSTOM_PLAN_LIMITS.get("pro") != 20:
        errors.append("CUSTOM_PLAN_LIMITS unexpected values")
    with __import__("unittest.mock").patch(
        "db.custom_instruments.count_custom_requests_this_month",
        return_value=3,
    ):
        quota = check_custom_request_quota(user_id="w18-verify-user", plan_id="standard")
    if quota.get("allowed") is not False or int(quota.get("used") or 0) != 3:
        errors.append(f"quota_exceeded check failed: {quota}")
    free_quota = check_custom_request_quota(user_id="w18-verify-user", plan_id="free")
    if free_quota.get("allowed") is not False:
        errors.append(f"free plan must be blocked: {free_quota}")
    return errors


def verify_runtime_cache_age() -> list[str]:
    errors: list[str] = []
    payload = {"generated_at": "2026-07-06T06:00:00+00:00"}
    age = runtime_cache_age_seconds(payload, now=__import__("datetime").datetime.fromisoformat("2026-07-06T06:05:00+00:00"))
    if age is None or abs(age - 300.0) > 0.1:
        errors.append(f"runtime_cache_age_seconds expected ~300 got {age}")
    return errors


def verify_api_runtime_shape() -> list[str]:
    from services.api.main import _build_paper_watchlist_runtime_response  # noqa: E402
    from unittest.mock import patch

    errors: list[str] = []
    cached = {
        "status_filter": "pending_runtime",
        "runtime_binding": "file_cache_signal_preview",
        "generated_at": "2026-07-06T06:00:00+00:00",
        "items": [{"watchlist_id": "w1", "runtime_status": "ready"}],
    }
    with patch("services.api.main.load_watchlist_runtime_cache", return_value=cached):
        resp = _build_paper_watchlist_runtime_response(
            user="demo-user",
            status="pending_runtime",
            limit=10,
            prefer_runtime_cache=True,
            runtime_cache_max_age_seconds=600,
        )
    cache_meta = resp.get("runtime_cache") or {}
    if cache_meta.get("status") not in {"hit", "hit_stale"}:
        errors.append(f"runtime_cache.status unexpected: {cache_meta}")
    if resp.get("mode") != "read_only_observation":
        errors.append("mode must stay read_only_observation")
    if not resp.get("items"):
        errors.append("items empty on cache hit")
    return errors


def verify_pg_optional() -> list[str]:
    errors: list[str] = []
    try:
        from db.paper_watchlist import list_distinct_watchlist_user_ids  # noqa: E402

        users = list_distinct_watchlist_user_ids(status="pending_runtime", limit_users=5)
        print(f"W18_PG_OK pending_runtime_users={len(users)}")
    except Exception as exc:  # noqa: BLE001
        print(f"W18_PG_SKIP database unavailable: {type(exc).__name__}")
    return errors


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="W18 watchlist quota/runtime API alignment smoke.")
    parser.add_argument("--with-pg", action="store_true", help="Also probe paper_watchlist via PG when available.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    checks = [
        ("quota", verify_quota_alignment),
        ("runtime_cache_age", verify_runtime_cache_age),
        ("api_runtime_shape", verify_api_runtime_shape),
    ]
    if args.with_pg:
        checks.append(("pg", verify_pg_optional))

    failed: list[str] = []
    for name, fn in checks:
        errs = fn()
        if errs:
            failed.extend(f"{name}:{item}" for item in errs)
        else:
            print(f"W18_CHECK_OK {name}")

    if failed:
        for item in failed:
            print(f"W18_CHECK_FAIL {item}", file=sys.stderr)
        return 1

    print("W18_VERIFY_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
