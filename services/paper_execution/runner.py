"""CLI/subprocess wrappers for per-user CRYPTO paper execution."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .paths import ROOT, UserPaperPaths
from .watchlist import execution_allowed_for_plan, load_user_crypto_symbols

SRC = ROOT / "src"
DEFAULT_ENV_PATH = "src;packages/fengji_core;services"
DEFAULT_STEP_TIMEOUT_SECONDS = 45


@dataclass
class StepResult:
    step: str
    ok: bool
    returncode: int = 0
    command: list[str] = field(default_factory=list)
    detail: dict[str, Any] = field(default_factory=dict)
    stderr_tail: str = ""


def _python_env() -> dict[str, str]:
    env = os.environ.copy()
    existing = env.get("PYTHONPATH", "")
    parts = [p for p in [DEFAULT_ENV_PATH, existing] if p]
    env["PYTHONPATH"] = ";".join(parts)
    env.setdefault("FENGJI_MARKET", "crypto")
    return env


def _step_timeout_seconds(env_name: str) -> int:
    raw = str(os.getenv(env_name, "")).strip()
    if not raw:
        return DEFAULT_STEP_TIMEOUT_SECONDS
    try:
        return max(1, int(float(raw)))
    except ValueError:
        return DEFAULT_STEP_TIMEOUT_SECONDS


def _run_step(command: list[str], *, dry_run: bool = False, timeout_seconds: int | None = None) -> StepResult:
    step = Path(command[1]).name if len(command) > 1 else "unknown"
    if dry_run:
        return StepResult(step=step, ok=True, command=command, detail={"dry_run": True})
    timeout = int(timeout_seconds or DEFAULT_STEP_TIMEOUT_SECONDS)
    try:
        proc = subprocess.run(
            command,
            cwd=str(ROOT),
            env=_python_env(),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        stderr = exc.stderr or ""
        if isinstance(stderr, bytes):
            stderr = stderr.decode("utf-8", errors="replace")
        return StepResult(
            step=step,
            ok=False,
            returncode=124,
            command=command,
            detail={"error": "timeout", "timeout_seconds": timeout},
            stderr_tail=str(stderr)[-2000:],
        )
    stderr_tail = (proc.stderr or "")[-2000:]
    return StepResult(
        step=step,
        ok=proc.returncode == 0,
        returncode=proc.returncode,
        command=command,
        detail={"stdout_lines": len((proc.stdout or "").splitlines()), "timeout_seconds": timeout},
        stderr_tail=stderr_tail,
    )


def resolve_user_symbols(
    user_id: str,
    *,
    symbols: list[str] | None = None,
    local_symbols: list[str] | None = None,
    watchlist_rows: list[dict[str, Any]] | None = None,
) -> list[str]:
    if symbols:
        from .watchlist import normalize_crypto_symbol

        out: list[str] = []
        seen: set[str] = set()
        for raw in symbols:
            sym = normalize_crypto_symbol(raw)
            if sym and sym not in seen:
                seen.add(sym)
                out.append(sym)
        return out
    return load_user_crypto_symbols(
        user_id,
        local_symbols=local_symbols,
        watchlist_rows=watchlist_rows,
        include_pg=watchlist_rows is None,
    )


def run_user_paper_radar_once(
    paths: UserPaperPaths,
    symbols: list[str],
    *,
    data_dir: str = "data",
    os_state_dir: str = "runtime/fengji_os_state",
    dry_run: bool = False,
) -> StepResult:
    if not symbols:
        return StepResult(step="fengji_total_radar.py", ok=False, detail={"error": "no_symbols"})
    paths.ensure_dirs()
    cmd = [
        sys.executable,
        str(SRC / "fengji_total_radar.py"),
        "--market",
        "crypto",
        "--data-dir",
        data_dir,
        "--symbols",
        ",".join(symbols),
        "--out-dir",
        str(paths.radar_dir),
        "--os-state-dir",
        os_state_dir,
    ]
    return _run_step(cmd, dry_run=dry_run, timeout_seconds=_step_timeout_seconds("FENGJI_PAPER_RADAR_TIMEOUT"))


def run_user_paper_pending_once(
    paths: UserPaperPaths,
    *,
    max_distance_pct: float = 0.08,
    dry_run: bool = False,
) -> StepResult:
    paths.ensure_dirs()
    cmd = [
        sys.executable,
        str(SRC / "fengji_pending_orders.py"),
        "--radar",
        str(paths.radar_json),
        "--out-dir",
        str(paths.pending_dir),
        "--max-distance-pct",
        str(max_distance_pct),
        "--monitor-state",
        str(paths.monitor_state_json),
    ]
    return _run_step(cmd, dry_run=dry_run, timeout_seconds=_step_timeout_seconds("FENGJI_PAPER_PENDING_TIMEOUT"))


def run_user_paper_monitor_once(
    paths: UserPaperPaths,
    *,
    data_dir: str = "data",
    os_state_dir: str = "runtime/fengji_os_state",
    price_file: str = "",
    dry_run: bool = False,
) -> StepResult:
    paths.ensure_dirs()
    cmd = [
        sys.executable,
        str(SRC / "fengji_pending_order_monitor.py"),
        "--once",
        "--orders-file",
        str(paths.pending_orders_json),
        "--out-dir",
        str(paths.pending_dir),
        "--state-file",
        str(paths.monitor_state_json),
        "--paper-state-file",
        str(paths.paper_state_json),
        "--data-dir",
        data_dir,
        "--os-state-dir",
        os_state_dir,
        "--feishu-webhook",
        "",
    ]
    if price_file:
        cmd.extend(["--price-file", price_file])
    return _run_step(cmd, dry_run=dry_run, timeout_seconds=_step_timeout_seconds("FENGJI_PAPER_MONITOR_TIMEOUT"))


def run_user_paper_pipeline(
    *,
    user_id: str,
    plan_id: str = "standard",
    symbols: list[str] | None = None,
    local_symbols: list[str] | None = None,
    watchlist_rows: list[dict[str, Any]] | None = None,
    root_dir: Path | None = None,
    steps: tuple[str, ...] = ("radar", "pending", "monitor"),
    dry_run: bool = False,
) -> dict[str, Any]:
    if not execution_allowed_for_plan(plan_id):
        return {
            "ok": False,
            "error": "plan_not_eligible",
            "plan_id": plan_id,
            "detail": "独立撮合仅 standard/pro；免费档仍用 scoped 投影",
        }

    resolved = resolve_user_symbols(
        user_id,
        symbols=symbols,
        local_symbols=local_symbols,
        watchlist_rows=watchlist_rows,
    )
    paths = UserPaperPaths(user_id=user_id, root_dir=root_dir or paths_default_root())
    paths.ensure_dirs()
    meta = paths.touch_meta(plan_id=plan_id, symbols=resolved)

    results: list[StepResult] = []
    ok = True
    if not resolved:
        return {
            "ok": False,
            "error": "no_watchlist_symbols",
            "user_id": user_id,
            "paths": str(paths.base_dir),
            "meta": meta,
        }

    step_fns = {
        "radar": lambda: run_user_paper_radar_once(paths, resolved, dry_run=dry_run),
        "pending": lambda: run_user_paper_pending_once(paths, dry_run=dry_run),
        "monitor": lambda: run_user_paper_monitor_once(paths, dry_run=dry_run),
    }
    for name in steps:
        if name not in step_fns:
            continue
        result = step_fns[name]()
        results.append(result)
        if not result.ok:
            ok = False
            break

    pg_sync: dict[str, Any] | None = None
    if ok and not dry_run and "monitor" in steps:
        try:
            from .sync_pg import sync_user_paths_to_pg

            pg_sync = sync_user_paths_to_pg(paths)
        except Exception as exc:
            pg_sync = {"ok": False, "error": str(exc)}

    return {
        "ok": ok,
        "user_id": user_id,
        "plan_id": plan_id,
        "symbols": resolved,
        "paths": {
            "base": str(paths.base_dir),
            "paper_state": str(paths.paper_state_json),
            "pending_orders": str(paths.pending_orders_json),
        },
        "meta": meta,
        "pg_sync": pg_sync,
        "steps": [
            {
                "step": r.step,
                "ok": r.ok,
                "returncode": r.returncode,
                "command": r.command,
                "detail": r.detail,
                "stderr_tail": r.stderr_tail,
            }
            for r in results
        ],
    }


def paths_default_root() -> Path:
    from .paths import PAPER_USERS_ROOT

    return PAPER_USERS_ROOT


def load_user_open_positions(paths: UserPaperPaths) -> list[dict[str, Any]]:
    if not paths.paper_state_json.is_file():
        return []
    try:
        data = json.loads(paths.paper_state_json.read_text(encoding="utf-8"))
    except Exception:
        return []
    positions: list[dict[str, Any]] = []
    symbols = data.get("symbols") or {}
    if not isinstance(symbols, dict):
        return positions
    for sym, st in symbols.items():
        if not isinstance(st, dict):
            continue
        open_pos = st.get("open_position")
        if isinstance(open_pos, dict) and open_pos:
            row = dict(open_pos)
            row.setdefault("symbol", sym)
            positions.append(row)
        for item in st.get("open_positions") or []:
            if isinstance(item, dict):
                row = dict(item)
                row.setdefault("symbol", sym)
                positions.append(row)
    return positions
