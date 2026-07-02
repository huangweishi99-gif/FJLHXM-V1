"""Batch job: scan eligible users and run per-user CRYPTO paper pipeline."""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .mode import is_shadow_mode, resolve_default_paper_account_mode, resolve_fengji_paper_mode
from .paths import PAPER_USERS_ROOT, UserPaperPaths
from .runner import run_user_paper_pipeline
from .watchlist import execution_allowed_for_plan, normalize_plan_id

JOB_STATE_FILE = PAPER_USERS_ROOT / "_execution_job_state.json"
MARKET_GROUP_EXECUTION = "per_user_execution_v1_2"


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_iso(value: str | None) -> datetime | None:
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


def load_job_state(path: Path | None = None) -> dict[str, Any]:
    file_path = path or JOB_STATE_FILE
    if not file_path.is_file():
        return {"users": {}}
    try:
        data = json.loads(file_path.read_text(encoding="utf-8"))
    except Exception:
        return {"users": {}}
    if not isinstance(data, dict):
        return {"users": {}}
    users = data.get("users")
    if not isinstance(users, dict):
        data["users"] = {}
    return data


def save_job_state(state: dict[str, Any], path: Path | None = None) -> Path:
    file_path = path or JOB_STATE_FILE
    file_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "updated_at": _utc_now().isoformat(),
        "users": dict(state.get("users") or {}),
    }
    tmp = file_path.with_suffix(".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(file_path)
    return file_path


def polling_interval_seconds(plan_id: str) -> int:
    try:
        from feature_gate import monitor_polling_interval_seconds

        return monitor_polling_interval_seconds(plan_id)
    except Exception:
        defaults = {"standard": 60, "pro": 30}
        return int(defaults.get(normalize_plan_id(plan_id), 900))


def resolve_user_plan_id(user_id: str, *, watchlist_plan: str | None = None) -> str:
    try:
        from db.auth_users import get_user_by_id

        auth = get_user_by_id(user_id)
        if auth and auth.get("plan_id"):
            return normalize_plan_id(str(auth["plan_id"]))
    except Exception:
        pass
    return normalize_plan_id(watchlist_plan)


def is_user_plan_active(user_id: str, plan_id: str) -> bool:
    try:
        from db.auth_users import get_user_by_id
        from feature_gate import is_plan_active

        auth = get_user_by_id(user_id)
        if auth:
            return is_plan_active(auth)
    except Exception:
        pass
    return execution_allowed_for_plan(plan_id)


def should_run_user(
    user_id: str,
    plan_id: str,
    state: dict[str, Any],
    *,
    now: datetime | None = None,
    force: bool = False,
) -> tuple[bool, str]:
    if force:
        return True, "forced"
    if not execution_allowed_for_plan(plan_id):
        return False, "plan_not_eligible"
    if not is_user_plan_active(user_id, plan_id):
        return False, "plan_inactive"
    moment = now or _utc_now()
    users = state.get("users") or {}
    row = users.get(user_id) if isinstance(users, dict) else None
    if not isinstance(row, dict):
        return True, "first_run"
    last_at = _parse_iso(str(row.get("last_run_at") or ""))
    if last_at is None:
        return True, "no_last_run"
    elapsed = (moment - last_at).total_seconds()
    need = polling_interval_seconds(plan_id)
    if elapsed >= need:
        return True, f"interval_elapsed={int(elapsed)}s>={need}s"
    return False, f"interval_wait={int(need - elapsed)}s"


def list_crypto_execution_candidates(*, limit_rows: int = 2000) -> list[dict[str, Any]]:
    try:
        from db.paper_watchlist import WATCHLIST_STATUS_PENDING_RUNTIME
        from sqlalchemy import select
        from sqlalchemy.orm import Session

        from db.models import PaperWatchlist
        from db.session import get_engine
    except Exception:
        return []

    by_user: dict[str, dict[str, Any]] = {}
    with Session(get_engine()) as session:
        rows = session.scalars(
            select(PaperWatchlist)
            .where(PaperWatchlist.status == WATCHLIST_STATUS_PENDING_RUNTIME)
            .order_by(PaperWatchlist.updated_at.desc())
            .limit(max(1, int(limit_rows)))
        ).all()
        for row in rows:
            market = str(row.market or "").strip().upper()
            if market not in {"", "CRYPTO", "CRYPTO_USDT"}:
                continue
            uid = str(row.user_id or "").strip()
            if not uid:
                continue
            bucket = by_user.setdefault(
                uid,
                {
                    "user_id": uid,
                    "plan_id": normalize_plan_id(row.plan_id),
                    "symbols": [],
                    "watchlist_rows": [],
                },
            )
            if row.plan_id and normalize_plan_id(row.plan_id) in {"standard", "pro"}:
                bucket["plan_id"] = normalize_plan_id(row.plan_id)
            sym = str(row.symbol or "").strip().upper()
            if sym and sym not in bucket["symbols"]:
                bucket["symbols"].append(sym)
            bucket["watchlist_rows"].append(
                {
                    "id": row.id,
                    "market": row.market,
                    "symbol": row.symbol,
                    "status": row.status,
                    "plan_id": row.plan_id,
                }
            )

    out: list[dict[str, Any]] = []
    for uid, item in by_user.items():
        plan = resolve_user_plan_id(uid, watchlist_plan=item.get("plan_id"))
        item["plan_id"] = plan
        if execution_allowed_for_plan(plan):
            out.append(item)
    return out


def default_paper_account_mode() -> str:
    return resolve_default_paper_account_mode()


def run_execution_job(
    *,
    user_id: str | None = None,
    force: bool = False,
    dry_run: bool = False,
    limit_users: int = 50,
    job_state_path: Path | None = None,
) -> dict[str, Any]:
    state = load_job_state(job_state_path)
    moment = _utc_now()
    candidates = list_crypto_execution_candidates()
    if user_id:
        uid = str(user_id).strip()
        candidates = [c for c in candidates if c.get("user_id") == uid]
        if not candidates and execution_allowed_for_plan("standard"):
            candidates = [{"user_id": uid, "plan_id": resolve_user_plan_id(uid), "symbols": [], "watchlist_rows": []}]

    results: list[dict[str, Any]] = []
    ran = 0
    skipped = 0
    for item in candidates[: max(1, int(limit_users))]:
        uid = str(item.get("user_id") or "")
        plan = normalize_plan_id(str(item.get("plan_id") or "standard"))
        ok_run, reason = should_run_user(uid, plan, state, now=moment, force=force)
        if not ok_run:
            skipped += 1
            results.append({"user_id": uid, "ok": True, "skipped": True, "reason": reason, "plan_id": plan})
            continue

        pipeline = run_user_paper_pipeline(
            user_id=uid,
            plan_id=plan,
            symbols=item.get("symbols") or None,
            watchlist_rows=item.get("watchlist_rows") or None,
            dry_run=dry_run,
        )
        shadow_report: dict[str, Any] | None = None
        if pipeline.get("ok") and not dry_run and is_shadow_mode():
            try:
                from .shadow import record_user_shadow_comparison

                shadow_report = record_user_shadow_comparison(
                    user_id=uid,
                    plan_id=plan,
                    pg_watchlist=item.get("watchlist_rows"),
                    local_watchlist_symbols=item.get("symbols"),
                )
            except Exception as exc:
                shadow_report = {"ok": False, "error": str(exc)}
        ran += 1
        users = state.setdefault("users", {})
        users[uid] = {
            "last_run_at": moment.isoformat(),
            "last_ok": bool(pipeline.get("ok")),
            "plan_id": plan,
            "reason": reason,
            "error": pipeline.get("error"),
        }
        results.append({"user_id": uid, "skipped": False, "shadow": shadow_report, **pipeline})

    if not dry_run:
        save_job_state(state, job_state_path)

    return {
        "ok": all(r.get("ok", False) or r.get("skipped") for r in results) if results else True,
        "candidates": len(candidates),
        "ran": ran,
        "skipped": skipped,
        "dry_run": dry_run,
        "fengji_paper_mode": resolve_fengji_paper_mode(),
        "default_paper_account_mode": default_paper_account_mode(),
        "results": results,
    }
