from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from db.backtest_jobs import get_backtest_job
from db.models import CustomInstrumentRequest
from db.paper_watchlist import create_or_get_paper_watchlist_entry
from db.session import get_engine

SUPPORTED_CUSTOM_MARKETS = {"CRYPTO", "FUTURES", "A_STOCK", "US_STOCK"}
TERMINAL_STATUSES = {"backtested", "paper_enabled", "failed"}
CUSTOM_PLAN_LIMITS = {"standard": 3, "pro": 20}


def normalize_custom_symbol(market: str, symbol: str) -> str:
    mkt = market.strip().upper()
    sym = symbol.strip().upper().replace("-", "").replace("/", "")
    if mkt == "CRYPTO":
        if not re.fullmatch(r"[A-Z0-9_.]{2,32}", sym):
            raise ValueError("invalid symbol format")
        if not sym.endswith("USDT"):
            sym = f"{sym}USDT"
        return sym
    if mkt in {"A_STOCK", "ASTOCK"}:
        digits = re.sub(r"\D", "", sym)
        if not re.fullmatch(r"\d{1,6}", digits):
            raise ValueError("A-share symbol must be a numeric code")
        return digits.zfill(6)
    if mkt in {"FUTURES", "CN_FUTURES"}:
        if not re.fullmatch(r"[A-Z0-9_.]{1,16}", sym):
            raise ValueError("invalid futures symbol")
        return sym
    if mkt in {"US_STOCK", "USSTOCK"}:
        cleaned = sym.replace(".", "_")
        if not re.fullmatch(r"[A-Z_]{1,12}", cleaned):
            raise ValueError("invalid US stock symbol")
        return cleaned
    raise ValueError(f"unsupported market: {market}")


def normalize_custom_strategies(strategies: list[str] | None) -> list[str]:
    out = []
    for item in strategies or ["TOTAL"]:
        sid = str(item or "").strip().upper()
        if not sid:
            continue
        if sid not in out:
            out.append(sid)
    return out or ["TOTAL"]


def normalize_custom_plan(plan_id: str | None) -> str:
    return (plan_id or "free").strip().lower()


def custom_month_bounds(now: datetime | None = None) -> tuple[datetime, datetime]:
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    current = current.astimezone(timezone.utc)
    start = current.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    if start.month == 12:
        end = start.replace(year=start.year + 1, month=1)
    else:
        end = start.replace(month=start.month + 1)
    return start, end


def count_custom_requests_this_month(user_id: str, now: datetime | None = None) -> int:
    start, end = custom_month_bounds(now)
    with Session(get_engine()) as session:
        return int(
            session.scalar(
                select(func.count())
                .select_from(CustomInstrumentRequest)
                .where(
                    CustomInstrumentRequest.user_id == user_id,
                    CustomInstrumentRequest.created_at >= start,
                    CustomInstrumentRequest.created_at < end,
                )
            )
            or 0
        )


def check_custom_request_quota(user_id: str, plan_id: str | None, now: datetime | None = None) -> dict[str, int | str | bool]:
    plan = normalize_custom_plan(plan_id)
    limit = CUSTOM_PLAN_LIMITS.get(plan)
    if limit is None:
        return {
            "allowed": False,
            "plan_id": plan,
            "limit": 0,
            "used": 0,
            "remaining": 0,
        }
    used = count_custom_requests_this_month(user_id, now)
    remaining = max(limit - used, 0)
    return {
        "allowed": used < limit,
        "plan_id": plan,
        "limit": limit,
        "used": used,
        "remaining": remaining,
    }


def _request_to_dict(row: CustomInstrumentRequest, *, backtest_job: dict[str, Any] | None = None) -> dict[str, Any]:
    request_json = row.request_json or {}
    return {
        "id": row.id,
        "user_id": row.user_id,
        "plan_id": row.plan_id,
        "market": row.market,
        "symbol": row.symbol,
        "name": row.name,
        "status": row.status,
        "strategies": row.strategies_json,
        "years": int(row.years),
        "enable_paper": bool(row.enable_paper),
        "backtest_job_id": row.backtest_job_id,
        "backtest_job": backtest_job,
        "error_message": row.error_message,
        "request": request_json,
        "quota": request_json.get("quota"),
        "paper_watchlist": request_json.get("paper_watchlist"),
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
        "finished_at": row.finished_at.isoformat() if row.finished_at else None,
    }


def create_custom_instrument_request(
    *,
    market: str,
    symbol: str,
    strategies: list[str] | None,
    years: int,
    user_id: str | None = None,
    plan_id: str | None = None,
    name: str | None = None,
    enable_paper: bool = False,
    status: str = "queued",
    backtest_job_id: str | None = None,
    error_message: str | None = None,
    quota: dict[str, Any] | None = None,
    request_extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    mkt = market.strip().upper()
    if mkt not in SUPPORTED_CUSTOM_MARKETS:
        raise ValueError(f"unsupported custom instrument market: {mkt}")
    sym = normalize_custom_symbol(mkt, symbol)
    yrs = int(years)
    if yrs < 1 or yrs > 5:
        raise ValueError("years must be between 1 and 5")
    strategy_list = normalize_custom_strategies(strategies)
    now = datetime.now(timezone.utc)
    request_json = {
        "market": mkt,
        "symbol": sym,
        "strategies": strategy_list,
        "years": yrs,
        "enable_paper": bool(enable_paper),
        "mvp_scope": "custom_instrument_to_backtest_job",
    }
    if quota:
        request_json["quota"] = quota
    if request_extra:
        request_json.update(request_extra)

    row = CustomInstrumentRequest(
        id=str(uuid.uuid4()),
        user_id=user_id,
        plan_id=plan_id,
        market=mkt,
        symbol=sym,
        name=name,
        status=status,
        strategies_json=strategy_list,
        years=yrs,
        enable_paper=bool(enable_paper),
        backtest_job_id=backtest_job_id,
        error_message=error_message,
        request_json=request_json,
        updated_at=now,
        finished_at=now if status in TERMINAL_STATUSES else None,
    )
    with Session(get_engine()) as session:
        session.add(row)
        session.commit()
        session.refresh(row)
        return _request_to_dict(row)


def update_custom_instrument_request(
    request_id: str,
    *,
    status: str | None = None,
    backtest_job_id: str | None = None,
    error_message: str | None = None,
    request_patch: dict[str, Any] | None = None,
    finished: bool = False,
) -> dict[str, Any] | None:
    with Session(get_engine()) as session:
        row = session.get(CustomInstrumentRequest, request_id)
        if row is None:
            return None
        if status is not None:
            row.status = status
        if backtest_job_id is not None:
            row.backtest_job_id = backtest_job_id
        if error_message is not None:
            row.error_message = error_message[:2000]
        elif status not in {"failed"}:
            row.error_message = None
        if request_patch:
            payload = dict(row.request_json or {})
            payload.update(request_patch)
            row.request_json = payload
        row.updated_at = datetime.now(timezone.utc)
        if finished or (status in TERMINAL_STATUSES if status is not None else False):
            row.finished_at = datetime.now(timezone.utc)
        session.commit()
        session.refresh(row)
        job = get_backtest_job(row.backtest_job_id) if row.backtest_job_id else None
        return _request_to_dict(row, backtest_job=job)


def refresh_custom_request_from_backtest(row: CustomInstrumentRequest) -> None:
    if row.status in TERMINAL_STATUSES or not row.backtest_job_id:
        return
    job = get_backtest_job(row.backtest_job_id)
    if not job:
        return
    if job["status"] == "succeeded":
        if row.enable_paper:
            if not row.user_id:
                row.status = "failed"
                row.error_message = "user_id is required to enable paper watchlist"
                row.finished_at = datetime.now(timezone.utc)
            else:
                watchlist = create_or_get_paper_watchlist_entry(
                    request_id=row.id,
                    user_id=row.user_id,
                    plan_id=row.plan_id,
                    market=row.market,
                    symbol=row.symbol,
                    name=row.name,
                    strategies=list(row.strategies_json or ["TOTAL"]),
                    years=int(row.years),
                )
                payload = dict(row.request_json or {})
                payload["paper_watchlist"] = watchlist
                row.request_json = payload
                row.status = "paper_enabled"
                row.error_message = None
                row.finished_at = datetime.now(timezone.utc)
        else:
            row.status = "backtested"
            row.error_message = None
            row.finished_at = datetime.now(timezone.utc)
    elif job["status"] == "failed":
        row.status = "failed"
        row.error_message = job.get("error_message") or "backtest failed"
        row.finished_at = datetime.now(timezone.utc)
    row.updated_at = datetime.now(timezone.utc)


def get_custom_instrument_request(request_id: str) -> dict[str, Any] | None:
    with Session(get_engine()) as session:
        row = session.get(CustomInstrumentRequest, request_id)
        if row is None:
            return None
        refresh_custom_request_from_backtest(row)
        session.commit()
        session.refresh(row)
        job = get_backtest_job(row.backtest_job_id) if row.backtest_job_id else None
        return _request_to_dict(row, backtest_job=job)
