"""V1.1 Phase 4: global paper mode (scoped / shadow / per_user_execution)."""
from __future__ import annotations

import os

PAPER_MODE_SCOPED = "scoped_shared"
PAPER_MODE_SHADOW = "shadow"
PAPER_MODE_EXECUTION = "per_user_execution"

_VALID_MODES = {PAPER_MODE_SCOPED, PAPER_MODE_SHADOW, PAPER_MODE_EXECUTION}


def resolve_fengji_paper_mode() -> str:
    raw = str(os.getenv("FENGJI_PAPER_MODE", PAPER_MODE_SHADOW) or PAPER_MODE_SHADOW).strip().lower()
    if raw in {"scoped", "scoped_shared", "scoped_shared_v1_1"}:
        return PAPER_MODE_SCOPED
    if raw in {"execution", "per_user", "per_user_execution", "per_user_execution_v1_2"}:
        return PAPER_MODE_EXECUTION
    if raw == "shadow":
        return PAPER_MODE_SHADOW
    return PAPER_MODE_SHADOW if raw not in _VALID_MODES else raw


def is_shadow_mode() -> bool:
    return resolve_fengji_paper_mode() == PAPER_MODE_SHADOW


def is_per_user_execution_mode() -> bool:
    return resolve_fengji_paper_mode() == PAPER_MODE_EXECUTION


def is_scoped_only_mode() -> bool:
    return resolve_fengji_paper_mode() == PAPER_MODE_SCOPED


def resolve_default_paper_account_mode() -> str:
    """UI/API auto mode: execution only after cutover unless explicitly overridden."""
    explicit = str(os.getenv("FENGJI_PAPER_ACCOUNT_MODE", "") or "").strip().lower()
    if explicit in {"scoped", "execution"}:
        return explicit
    if is_per_user_execution_mode():
        return "execution"
    return "scoped"


def paper_mode_summary() -> dict[str, str]:
    mode = resolve_fengji_paper_mode()
    ui_default = resolve_default_paper_account_mode()
    return {
        "fengji_paper_mode": mode,
        "default_paper_account_view": ui_default,
        "shadow_active": str(is_shadow_mode()).lower(),
        "cutover_active": str(is_per_user_execution_mode()).lower(),
    }
