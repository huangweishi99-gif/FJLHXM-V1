"""Sync per-user JSON execution state to PostgreSQL (Phase 3)."""
from __future__ import annotations

from typing import Any

from .paths import UserPaperPaths


def sync_user_paths_to_pg(paths: UserPaperPaths) -> dict[str, Any]:
    try:
        from db.paper_user_execution import sync_user_execution_to_pg
    except Exception as exc:
        return {"ok": False, "error": f"pg_unavailable:{exc}"}

    try:
        return sync_user_execution_to_pg(
            paths.user_id,
            paper_state_path=paths.paper_state_json,
            pending_orders_path=paths.pending_orders_json,
        )
    except Exception as exc:
        return {"ok": False, "error": str(exc)}
