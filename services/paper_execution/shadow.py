"""V1.1 Phase 4: shadow comparison between scoped projection and per-user execution."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .paths import PAPER_USERS_ROOT, UserPaperPaths
from .watchlist import normalize_crypto_symbol

SHADOW_REPORTS_DIR = PAPER_USERS_ROOT / "_shadow"
CRYPTO_MARKETS = {"CRYPTO", "CRYPTO_USDT", ""}


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_json(path: Path) -> dict[str, Any] | list[Any] | None:
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, (dict, list)) else None
    except Exception:
        return None


def _symbol_key(symbol: str) -> str:
    return normalize_crypto_symbol(symbol) or str(symbol or "").strip().upper()


def _scoped_crypto_positions(
    opens: dict[str, Any],
    scoped_keys: set[str],
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for pos in opens.get("positions") or []:
        if not isinstance(pos, dict):
            continue
        market = str(pos.get("market") or "").strip().upper()
        if market and market not in CRYPTO_MARKETS:
            continue
        sym = _symbol_key(str(pos.get("symbol") or ""))
        if not sym:
            continue
        keys = {sym, sym.replace("USDT", "")}
        if not keys.intersection(scoped_keys):
            continue
        out.append(pos)
    return out


def _count_bad_audits_from_radar(radar: dict[str, Any] | list[Any] | None) -> int:
    if radar is None:
        return 0
    items: list[Any]
    if isinstance(radar, list):
        items = radar
    elif isinstance(radar, dict):
        items = list(radar.get("rows") or radar.get("signals") or radar.get("items") or [])
    else:
        return 0
    count = 0
    for row in items:
        if not isinstance(row, dict):
            continue
        audit = row.get("audit") or row.get("os_audit") or {}
        if isinstance(audit, dict) and audit.get("valid") is False:
            count += 1
        elif row.get("bad_audit") or row.get("invalid_audit"):
            count += 1
    return count


def _count_stops_from_monitor_state(state: dict[str, Any] | None) -> int:
    if not isinstance(state, dict):
        return 0
    total = 0
    for sym_state in (state.get("symbols") or {}).values():
        if not isinstance(sym_state, dict):
            continue
        for key in ("closed_positions", "stop_exits", "exits"):
            block = sym_state.get(key)
            if isinstance(block, list):
                total += len(block)
            elif isinstance(block, dict):
                total += len(block)
        history = sym_state.get("history") or sym_state.get("events") or []
        if isinstance(history, list):
            total += sum(
                1
                for item in history
                if isinstance(item, dict) and str(item.get("event") or item.get("type") or "").lower() in {"stop", "stop_exit", "gap_stop"}
            )
    return total


def _execution_fill_proxy(paths: UserPaperPaths, monitor_state: dict[str, Any] | None) -> int:
    if isinstance(monitor_state, dict):
        fills = monitor_state.get("fill_count")
        if isinstance(fills, int):
            return fills
        total = 0
        for sym_state in (monitor_state.get("symbols") or {}).values():
            if isinstance(sym_state, dict):
                seen = sym_state.get("seen_entries") or []
                if isinstance(seen, list):
                    total += sum(1 for x in seen if isinstance(x, str) and "fill" in x.lower())
        if total:
            return total
    events = paths.events_jsonl
    if events.is_file():
        try:
            return sum(1 for line in events.read_text(encoding="utf-8").splitlines() if '"fill"' in line.lower())
        except Exception:
            pass
    return 0


def collect_scoped_snapshot(
    *,
    user_id: str,
    pg_watchlist: list[dict[str, Any]] | None = None,
    local_watchlist_symbols: list[str] | None = None,
    opens: dict[str, Any] | None = None,
    initial_cash: float = 100_000.0,
) -> dict[str, Any]:
    from monitor_paper_account import (
        DEFAULT_INITIAL_CASH,
        _equity_from_paper_state,
        _merge_monitor_opens,
        _scoped_symbols,
    )

    rows = list(pg_watchlist or [])
    scoped_keys = _scoped_symbols(pg_watchlist=rows, local_watchlist_symbols=local_watchlist_symbols)
    merged = opens if opens is not None else _merge_monitor_opens()
    crypto_positions = _scoped_crypto_positions(merged, scoped_keys)
    scoped_equity, reference_equity, scoped_symbol_count = _equity_from_paper_state(scoped_keys)
    cash_base = float(initial_cash or DEFAULT_INITIAL_CASH)
    equity = scoped_equity if scoped_equity is not None else cash_base
    symbols = sorted({_symbol_key(str(p.get("symbol") or "")) for p in crypto_positions if p.get("symbol")})
    return {
        "user_id": user_id,
        "view": "scoped",
        "equity": round(float(equity), 2),
        "reference_equity": round(float(reference_equity), 2) if reference_equity is not None else None,
        "open_positions": len(crypto_positions),
        "all_markets_open_positions": len(merged.get("positions") or []),
        "scoped_symbol_count": scoped_symbol_count,
        "symbols": symbols,
        "positions_preview": crypto_positions[:5],
    }


def collect_execution_snapshot(*, user_id: str, paths: UserPaperPaths | None = None) -> dict[str, Any]:
    from paper_execution.runner import load_user_open_positions

    user_paths = paths or UserPaperPaths(user_id=user_id)
    paper_state = _load_json(user_paths.paper_state_json)
    if not isinstance(paper_state, dict):
        paper_state = {}
    monitor_state_raw = _load_json(user_paths.monitor_state_json)
    monitor_state = monitor_state_raw if isinstance(monitor_state_raw, dict) else None
    pending_raw = _load_json(user_paths.pending_orders_json)
    pending_items: list[dict[str, Any]] = []
    if isinstance(pending_raw, list):
        pending_items = [x for x in pending_raw if isinstance(x, dict)]
    elif isinstance(pending_raw, dict):
        pending_items = [x for x in (pending_raw.get("orders") or pending_raw.get("items") or []) if isinstance(x, dict)]

    positions = load_user_open_positions(user_paths)
    equity = paper_state.get("equity")
    equity_f = float(equity) if isinstance(equity, (int, float)) else None
    symbols = sorted({_symbol_key(str(p.get("symbol") or "")) for p in positions if p.get("symbol")})
    return {
        "user_id": user_id,
        "view": "execution",
        "equity": round(float(equity_f), 2) if equity_f is not None else None,
        "open_positions": len(positions),
        "pending_orders": len(pending_items),
        "symbols": symbols,
        "fill_count_proxy": _execution_fill_proxy(user_paths, monitor_state),
        "stop_count_proxy": _count_stops_from_monitor_state(monitor_state),
        "bad_audits": _count_bad_audits_from_radar(_load_json(user_paths.radar_json)),
        "positions_preview": positions[:5],
    }


def compare_shadow_snapshots(
    scoped: dict[str, Any],
    execution: dict[str, Any],
) -> dict[str, Any]:
    scoped_syms = set(scoped.get("symbols") or [])
    exec_syms = set(execution.get("symbols") or [])
    overlap = sorted(scoped_syms.intersection(exec_syms))
    scoped_equity = scoped.get("equity")
    exec_equity = execution.get("equity")
    equity_gap: float | None = None
    if isinstance(scoped_equity, (int, float)) and isinstance(exec_equity, (int, float)):
        equity_gap = round(float(exec_equity) - float(scoped_equity), 2)
    return {
        "equity_gap": equity_gap,
        "open_count_gap": int(execution.get("open_positions") or 0) - int(scoped.get("open_positions") or 0),
        "pending_orders": int(execution.get("pending_orders") or 0),
        "symbol_overlap": len(overlap),
        "overlap_symbols": overlap,
        "execution_only_symbols": sorted(exec_syms - scoped_syms),
        "scoped_only_symbols": sorted(scoped_syms - exec_syms),
        "fill_count": int(execution.get("fill_count_proxy") or 0),
        "stop_count": int(execution.get("stop_count_proxy") or 0),
        "bad_audits": int(execution.get("bad_audits") or 0),
    }


def shadow_report_path(user_id: str) -> Path:
    safe = UserPaperPaths(user_id=user_id).safe_id
    return SHADOW_REPORTS_DIR / f"{safe}.json"


def save_shadow_report(report: dict[str, Any]) -> Path:
    SHADOW_REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    uid = str(report.get("user_id") or "")
    path = shadow_report_path(uid)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)
    return path


def load_user_shadow_report(user_id: str) -> dict[str, Any] | None:
    path = shadow_report_path(user_id)
    if not path.is_file():
        return None
    data = _load_json(path)
    return data if isinstance(data, dict) else None


def record_user_shadow_comparison(
    *,
    user_id: str,
    plan_id: str = "standard",
    pg_watchlist: list[dict[str, Any]] | None = None,
    local_watchlist_symbols: list[str] | None = None,
    opens: dict[str, Any] | None = None,
    persist_ledger: bool = True,
) -> dict[str, Any]:
    from paper_execution.mode import resolve_fengji_paper_mode

    uid = str(user_id or "").strip()
    if not uid:
        return {"ok": False, "error": "user_id required"}

    scoped = collect_scoped_snapshot(
        user_id=uid,
        pg_watchlist=pg_watchlist,
        local_watchlist_symbols=local_watchlist_symbols,
        opens=opens,
    )
    execution = collect_execution_snapshot(user_id=uid)
    delta = compare_shadow_snapshots(scoped, execution)
    report = {
        "ok": True,
        "generated_at": _utc_now_iso(),
        "user_id": uid,
        "plan_id": plan_id,
        "paper_mode": resolve_fengji_paper_mode(),
        "scoped": scoped,
        "execution": execution,
        "delta": delta,
    }
    save_shadow_report(report)

    if persist_ledger:
        try:
            from db.paper_accounts import append_paper_ledger_event, get_or_create_paper_account

            get_or_create_paper_account(uid, metadata={"plan_id": plan_id, "shadow": True})
            append_paper_ledger_event(
                uid,
                event_type="shadow_compare",
                metadata={
                    "scoped_open": scoped.get("open_positions"),
                    "execution_open": execution.get("open_positions"),
                    "equity_gap": delta.get("equity_gap"),
                    "fill_count": delta.get("fill_count"),
                    "stop_count": delta.get("stop_count"),
                    "bad_audits": delta.get("bad_audits"),
                    "paper_mode": report["paper_mode"],
                },
            )
            append_paper_ledger_event(
                uid,
                event_type="shadow_execution_snapshot",
                amount=execution.get("equity"),
                metadata={
                    "open_positions": execution.get("open_positions"),
                    "pending_orders": execution.get("pending_orders"),
                    "symbols": execution.get("symbols"),
                },
            )
        except Exception as exc:
            report["ledger_error"] = str(exc)

    return report


def list_shadow_reports(*, limit: int = 100) -> list[dict[str, Any]]:
    if not SHADOW_REPORTS_DIR.is_dir():
        return []
    paths = sorted(SHADOW_REPORTS_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    out: list[dict[str, Any]] = []
    for path in paths[: max(1, int(limit))]:
        data = _load_json(path)
        if isinstance(data, dict):
            out.append(
                {
                    "user_id": data.get("user_id"),
                    "generated_at": data.get("generated_at"),
                    "equity_gap": (data.get("delta") or {}).get("equity_gap"),
                    "open_count_gap": (data.get("delta") or {}).get("open_count_gap"),
                    "fill_count": (data.get("delta") or {}).get("fill_count"),
                    "stop_count": (data.get("delta") or {}).get("stop_count"),
                    "bad_audits": (data.get("delta") or {}).get("bad_audits"),
                    "path": str(path),
                }
            )
    return out
