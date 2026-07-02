from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from db.models import BacktestJob
from db.session import get_engine

TERMINAL_STATUSES = {"succeeded", "failed"}
RUNNING_STATUSES = {"queued", "running"}


def build_backtest_cache_key(*, market: str, symbol: str, strategy_id: str, years: int) -> str:
    raw = f"{market.upper()}|{symbol.upper()}|{strategy_id.upper()}|{int(years)}"
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
    return f"backtest:{raw}:{digest}"


def _job_to_dict(job: BacktestJob) -> dict[str, Any]:
    return {
        "id": job.id,
        "user_id": job.user_id,
        "market": job.market,
        "symbol": job.symbol,
        "strategy_id": job.strategy_id,
        "years": int(job.years),
        "status": job.status,
        "cache_key": job.cache_key,
        "params": job.params_json,
        "result": job.result_json,
        "error_message": job.error_message,
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "started_at": job.started_at.isoformat() if job.started_at else None,
        "finished_at": job.finished_at.isoformat() if job.finished_at else None,
    }


def create_backtest_job(
    *,
    market: str,
    symbol: str,
    strategy_id: str,
    years: int,
    user_id: str | None = None,
) -> dict[str, Any]:
    mkt = market.upper()
    sym = symbol.upper()
    sid = strategy_id.upper()
    yrs = int(years)
    cache_key = build_backtest_cache_key(market=mkt, symbol=sym, strategy_id=sid, years=yrs)
    params = {"market": mkt, "symbol": sym, "strategy_id": sid, "years": yrs}

    with Session(get_engine()) as session:
        cached = session.scalar(
            select(BacktestJob)
            .where(
                BacktestJob.cache_key == cache_key,
                BacktestJob.status == "succeeded",
            )
            .order_by(BacktestJob.finished_at.desc().nullslast())
            .limit(1)
        )
        if cached is not None:
            job = BacktestJob(
                id=str(uuid.uuid4()),
                user_id=user_id,
                market=mkt,
                symbol=sym,
                strategy_id=sid,
                years=yrs,
                status="succeeded",
                cache_key=cache_key,
                params_json=params,
                result_json=cached.result_json,
                error_message=None,
                started_at=datetime.now(timezone.utc),
                finished_at=datetime.now(timezone.utc),
            )
        else:
            job = BacktestJob(
                id=str(uuid.uuid4()),
                user_id=user_id,
                market=mkt,
                symbol=sym,
                strategy_id=sid,
                years=yrs,
                status="queued",
                cache_key=cache_key,
                params_json=params,
            )
        session.add(job)
        session.commit()
        session.refresh(job)
        return _job_to_dict(job)


def get_backtest_job(job_id: str) -> dict[str, Any] | None:
    with Session(get_engine()) as session:
        job = session.get(BacktestJob, job_id)
        return _job_to_dict(job) if job else None


def mark_backtest_job_running(job_id: str) -> dict[str, Any] | None:
    with Session(get_engine()) as session:
        job = session.get(BacktestJob, job_id)
        if job is None:
            return None
        if job.status in TERMINAL_STATUSES:
            return _job_to_dict(job)
        job.status = "running"
        job.started_at = datetime.now(timezone.utc)
        job.error_message = None
        session.commit()
        session.refresh(job)
        return _job_to_dict(job)


def mark_backtest_job_succeeded(job_id: str, result: dict[str, Any]) -> dict[str, Any] | None:
    with Session(get_engine()) as session:
        job = session.get(BacktestJob, job_id)
        if job is None:
            return None
        job.status = "succeeded"
        job.result_json = result
        job.error_message = None
        job.finished_at = datetime.now(timezone.utc)
        session.commit()
        session.refresh(job)
        return _job_to_dict(job)


def mark_backtest_job_failed(job_id: str, error_message: str) -> dict[str, Any] | None:
    with Session(get_engine()) as session:
        job = session.get(BacktestJob, job_id)
        if job is None:
            return None
        job.status = "failed"
        job.error_message = error_message[:2000]
        job.finished_at = datetime.now(timezone.utc)
        session.commit()
        session.refresh(job)
        return _job_to_dict(job)
