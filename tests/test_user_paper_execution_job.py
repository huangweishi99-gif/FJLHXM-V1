from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from services.paper_execution.job import (
    load_job_state,
    polling_interval_seconds,
    run_execution_job,
    save_job_state,
    should_run_user,
)


def test_polling_interval_standard_pro() -> None:
    assert polling_interval_seconds("standard") == 60
    assert polling_interval_seconds("pro") == 30


def test_should_run_user_respects_interval(tmp_path: Path) -> None:
    state_path = tmp_path / "job_state.json"
    now = datetime(2026, 6, 16, 12, 0, 0, tzinfo=timezone.utc)
    state = {
        "users": {
            "u1": {"last_run_at": (now - timedelta(seconds=30)).isoformat(), "plan_id": "standard"},
        }
    }
    save_job_state(state, state_path)
    loaded = load_job_state(state_path)
    ok, reason = should_run_user("u1", "standard", loaded, now=now)
    assert ok is False
    assert "interval_wait" in reason

    ok2, _ = should_run_user("u1", "standard", loaded, now=now, force=True)
    assert ok2 is True


def test_run_execution_job_dry_run_single_user(tmp_path: Path, monkeypatch) -> None:
    state_path = tmp_path / "job_state.json"

    def fake_pipeline(**kwargs):
        return {"ok": True, "user_id": kwargs["user_id"], "symbols": ["BTCUSDT"]}

    monkeypatch.setattr("services.paper_execution.job.run_user_paper_pipeline", fake_pipeline)
    monkeypatch.setattr(
        "services.paper_execution.job.list_crypto_execution_candidates",
        lambda **_: [],
    )

    report = run_execution_job(
        user_id="demo-user",
        force=True,
        dry_run=False,
        job_state_path=state_path,
    )
    assert report["ran"] == 1
    assert report["results"][0]["ok"] is True
    saved = json.loads(state_path.read_text(encoding="utf-8"))
    assert "demo-user" in saved["users"]
