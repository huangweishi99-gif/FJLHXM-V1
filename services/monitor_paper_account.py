"""每用户 paper 账户摘要（只读）：V1.1 PG 账户 + scoped 投影或 per-user execution（Phase 2）。"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from monitor_domestic import load_latest_opens, load_paper_state_path
from monitor_overseas import load_latest_opens as load_overseas_latest_opens

ROOT = Path(__file__).resolve().parents[1]
PAPER_ACCOUNTS_DIR = ROOT / "runtime" / "paper_accounts"
DEFAULT_INITIAL_CASH = 100_000.0
MARKET_GROUP_EXECUTION = "per_user_execution_v1_2"


def _normalize_symbol(symbol: str) -> str:
    text = str(symbol or "").strip().upper().replace("-", "").replace("_", "")
    if text and not text.endswith("USDT") and not text.isdigit():
        text += "USDT"
    return text


def _symbol_keys(symbol: str, market: str) -> set[str]:
    sym = _normalize_symbol(symbol)
    mkt = str(market or "").strip().upper()
    keys = {sym, sym.replace("USDT", ""), str(symbol or "").strip().upper()}
    if mkt == "A_STOCK":
        code = sym.zfill(6) if sym.isdigit() else sym
        keys.add(code)
    return {k for k in keys if k}


def _account_store_path(user_id: str) -> Path:
    safe = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in str(user_id or "anonymous"))
    return PAPER_ACCOUNTS_DIR / f"{safe}.json"


def _load_or_create_account_meta(user_id: str) -> dict[str, Any]:
    path = _account_store_path(user_id)
    now = datetime.now(timezone.utc).isoformat()
    if path.is_file():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
        except Exception:
            pass
    meta = {
        "user_id": user_id,
        "initial_cash": DEFAULT_INITIAL_CASH,
        "created_at": now,
        "updated_at": now,
        "mode": "per_user_readonly_v1",
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    return meta


def _scoped_symbols(
    *,
    pg_watchlist: list[dict[str, Any]],
    local_watchlist_symbols: list[str] | None,
) -> set[str]:
    keys: set[str] = set()
    for row in pg_watchlist:
        keys.update(_symbol_keys(str(row.get("symbol") or ""), str(row.get("market") or "")))
    for sym in local_watchlist_symbols or []:
        keys.update(_symbol_keys(sym, ""))
    return keys


def _position_in_scope(position: dict[str, Any], scoped_keys: set[str]) -> bool:
    return bool(
        _symbol_keys(str(position.get("symbol") or ""), str(position.get("market") or "")).intersection(
            scoped_keys
        )
    )


def _merge_monitor_opens() -> dict[str, Any]:
    domestic = load_latest_opens()
    overseas = load_overseas_latest_opens()
    positions = [
        *(domestic.get("positions") or []),
        *(overseas.get("positions") or []),
    ]
    return {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "source": "merged_paper_state",
        "domestic_source": domestic.get("source"),
        "overseas_source": overseas.get("source"),
        "positions": positions,
    }


def _equity_from_paper_state(scoped_keys: set[str]) -> tuple[float | None, float | None, int]:
    path = load_paper_state_path()
    if path is None or not scoped_keys:
        return None, None, 0
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None, None, 0

    scoped_equity = 0.0
    scoped_count = 0
    symbols = data.get("symbols") or {}
    if isinstance(symbols, dict):
        for sym, st in symbols.items():
            if not isinstance(st, dict):
                continue
            sym_keys = _symbol_keys(str(sym), "FUTURES")
            if not sym_keys.intersection(scoped_keys):
                continue
            scoped_count += 1
            try:
                scoped_equity += float(st.get("equity") or 0.0)
            except (TypeError, ValueError):
                pass

    reference_equity: float | None = None
    try:
        if isinstance(data.get("equity"), (int, float)):
            reference_equity = float(data["equity"])
    except (TypeError, ValueError):
        reference_equity = None
    if reference_equity is None and scoped_count:
        reference_equity = scoped_equity

    return scoped_equity if scoped_count else None, reference_equity, scoped_count


def _default_paper_account_mode() -> str:
    try:
        from paper_execution.mode import resolve_default_paper_account_mode

        return resolve_default_paper_account_mode()
    except Exception:
        return str(os.getenv("FENGJI_PAPER_ACCOUNT_MODE", "scoped") or "scoped").strip().lower()


def _resolve_paper_account_mode(*, paper_mode: str | None, plan_id: str) -> str:
    mode = str(paper_mode or "auto").strip().lower()
    if mode == "auto":
        mode = _default_paper_account_mode()
    if mode not in {"scoped", "execution"}:
        mode = "scoped"
    if mode == "execution":
        try:
            from paper_execution.watchlist import execution_allowed_for_plan

            if not execution_allowed_for_plan(plan_id):
                return "scoped"
        except Exception:
            return "scoped"
    return mode


def _user_execution_paths(user_id: str) -> Any:
    from paper_execution.paths import UserPaperPaths

    return UserPaperPaths(user_id=user_id)


def _equity_from_user_execution_state(user_id: str) -> tuple[float | None, float | None, int, list[dict[str, Any]]]:
    try:
        from paper_execution.runner import load_user_open_positions
    except Exception:
        return None, None, 0, []

    paths = _user_execution_paths(user_id)
    if not paths.paper_state_json.is_file():
        return None, None, 0, []

    try:
        data = json.loads(paths.paper_state_json.read_text(encoding="utf-8"))
    except Exception:
        return None, None, 0, []

    positions = load_user_open_positions(paths)
    top_equity = data.get("equity")
    reference_equity: float | None = None
    if isinstance(top_equity, (int, float)):
        reference_equity = float(top_equity)

    scoped_equity = 0.0
    scoped_count = 0
    symbols = data.get("symbols") or {}
    if isinstance(symbols, dict):
        for _sym, st in symbols.items():
            if not isinstance(st, dict):
                continue
            scoped_count += 1
            try:
                scoped_equity += float(st.get("equity") or 0.0)
            except (TypeError, ValueError):
                pass

    if reference_equity is None and scoped_count:
        reference_equity = scoped_equity

    equity = reference_equity if reference_equity is not None else None
    preview: list[dict[str, Any]] = []
    for pos in positions:
        preview.append(
            {
                "symbol": pos.get("symbol"),
                "market": "CRYPTO",
                "strategy_id": pos.get("strategy_id"),
                "direction": pos.get("direction") or pos.get("side"),
                "entry_price": pos.get("entry_price") or pos.get("trigger_price"),
                "source": "per_user_execution",
            }
        )
    return equity, reference_equity, len(positions), preview


def _persist_pg_account(
    *,
    user_id: str,
    initial_cash: float,
    equity: float,
    cash: float,
    scoped_positions: list[dict[str, Any]],
    scoped_symbol_count: int,
    plan_id: str,
    opens: dict[str, Any],
    market_group: str = "scoped_shared_v1_1",
    ledger_event_type: str = "scoped_projection",
) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    try:
        from db.paper_accounts import (
            get_or_create_paper_account,
            list_recent_ledger,
            update_paper_account_snapshot,
        )
    except Exception:
        return None, []

    try:
        account = get_or_create_paper_account(
            user_id,
            initial_cash=initial_cash,
            metadata={"plan_id": plan_id, "legacy_json": True},
            market_group=market_group,
        )
        snapshot_meta = {
            "open_positions": len(scoped_positions),
            "scoped_symbol_count": scoped_symbol_count,
            "domestic_source": opens.get("domestic_source"),
            "overseas_source": opens.get("overseas_source"),
            "projection": market_group,
        }
        account = update_paper_account_snapshot(
            user_id,
            equity=equity,
            cash=cash,
            metadata=snapshot_meta,
            ledger_event={
                "event_type": ledger_event_type,
                "metadata": {
                    "open_positions": len(scoped_positions),
                    "domestic_positions_total": len(opens.get("positions") or []),
                },
            },
        )
        ledger = list_recent_ledger(user_id, limit=5)
        return account, ledger
    except Exception:
        return None, []


def build_user_paper_account_summary(
    *,
    user_id: str,
    plan_id: str = "free",
    local_watchlist_count: int | None = None,
    local_watchlist_symbols: list[str] | None = None,
    pg_watchlist: list[dict[str, Any]] | None = None,
    paper_mode: str | None = None,
) -> dict[str, Any]:
    """构建用户 paper 账户只读摘要。"""
    uid = str(user_id or "").strip()
    if not uid:
        return {
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "mode": "read_only_paper_account",
            "authenticated": False,
            "disclaimer": "登录后可查看个人观察账户摘要；不向交易所发单",
            "initial_cash": DEFAULT_INITIAL_CASH,
            "equity": None,
            "cash": None,
        }

    plan = str(plan_id or "free")
    account_view = _resolve_paper_account_mode(paper_mode=paper_mode, plan_id=plan)
    meta = _load_or_create_account_meta(uid)
    initial_cash = float(meta.get("initial_cash") or DEFAULT_INITIAL_CASH)
    rows = list(pg_watchlist or [])
    runtime_pending = sum(1 for row in rows if str(row.get("status") or "") == "pending_runtime")
    runtime_paused = sum(1 for row in rows if str(row.get("status") or "") == "paused")
    local_count = int(local_watchlist_count) if local_watchlist_count is not None else None

    opens = _merge_monitor_opens()
    if account_view == "execution":
        exec_equity, exec_reference, open_count, exec_positions = _equity_from_user_execution_state(uid)
        equity = exec_equity if exec_equity is not None else initial_cash
        cash = float(equity)
        scoped_symbol_count = len(exec_positions)
        scoped_positions = exec_positions
        market_group = MARKET_GROUP_EXECUTION
        ledger_event_type = "execution_snapshot"
        account_mode = "per_user_execution_v1_2"
        disclaimer = (
            "V1.1 每用户独立 CRYPTO 模拟撮合（JSON state）；Shadow 期可通过 paper_mode=execution 查看；"
            "不向交易所发单"
        )
    else:
        scoped_keys = _scoped_symbols(pg_watchlist=rows, local_watchlist_symbols=local_watchlist_symbols)
        scoped_equity, reference_equity, scoped_symbol_count = _equity_from_paper_state(scoped_keys)
        scoped_positions = [pos for pos in opens.get("positions") or [] if _position_in_scope(pos, scoped_keys)]
        equity = scoped_equity if scoped_equity is not None else initial_cash
        cash = max(initial_cash, equity - sum(float(p.get("amount_cny") or 0) for p in scoped_positions))
        market_group = "scoped_shared_v1_1"
        ledger_event_type = "scoped_projection"
        account_mode = "per_user_pg_v1_1"
        exec_reference = reference_equity
        disclaimer = (
            "V1.1 每用户 PG 账户 + 自选品种 scoped 投影（domestic+overseas 共享运行态）；"
            "非独立信号撮合，不向交易所发单"
        )

    pg_account: dict[str, Any] | None = None
    ledger_preview: list[dict[str, Any]] = []
    shadow_blocks_execution_persist = False
    if account_view == "execution":
        try:
            from paper_execution.mode import is_shadow_mode

            shadow_blocks_execution_persist = is_shadow_mode()
        except Exception:
            shadow_blocks_execution_persist = False

    if shadow_blocks_execution_persist:
        try:
            from db.paper_accounts import get_paper_account, list_recent_ledger

            pg_account = get_paper_account(uid)
            ledger_preview = list_recent_ledger(uid, limit=5)
        except Exception:
            pg_account, ledger_preview = None, []
    else:
        pg_account, ledger_preview = _persist_pg_account(
            user_id=uid,
            initial_cash=initial_cash,
            equity=equity,
            cash=cash,
            scoped_positions=scoped_positions,
            scoped_symbol_count=scoped_symbol_count,
            plan_id=plan,
            opens=opens,
            market_group=market_group,
            ledger_event_type=ledger_event_type,
        )
    storage_backend = "pg" if pg_account else "json_fallback"
    if not pg_account:
        account_mode = "per_user_readonly_v1" if account_view == "scoped" else "per_user_execution_readonly_v1_2"

    payload = {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "mode": "read_only_paper_account",
        "account_mode": account_mode,
        "paper_account_view": account_view,
        "storage_backend": storage_backend,
        "authenticated": True,
        "user_id": uid,
        "plan_id": plan,
        "initial_cash": initial_cash,
        "equity": round(equity, 2),
        "cash": round(cash, 2),
        "scoped_symbol_count": scoped_symbol_count,
        "open_positions": len(scoped_positions),
        "positions_preview": scoped_positions[:5],
        "watchlist": {
            "pg_total": len(rows),
            "pg_runtime_pending": runtime_pending,
            "pg_runtime_paused": runtime_paused,
            "local_count": local_count,
        },
        "shared_reference": {
            "domestic_equity": exec_reference if account_view == "execution" else None,
            "domestic_positions_total": len(opens.get("positions") or []),
            "paper_state_source": opens.get("source"),
            "domestic_source": opens.get("domestic_source"),
            "overseas_source": opens.get("overseas_source"),
        },
        "pg_account": pg_account,
        "ledger_preview": ledger_preview,
        "disclaimer": disclaimer,
    }
    if account_view == "scoped":
        scoped_equity, reference_equity, _ = _equity_from_paper_state(
            _scoped_symbols(pg_watchlist=rows, local_watchlist_symbols=local_watchlist_symbols)
        )
        payload["shared_reference"]["domestic_equity"] = reference_equity

    try:
        from paper_execution.mode import is_shadow_mode, paper_mode_summary, resolve_fengji_paper_mode

        payload["paper_mode_global"] = resolve_fengji_paper_mode()
        payload["paper_mode_config"] = paper_mode_summary()
        if is_shadow_mode() and plan in {"standard", "pro"}:
            from paper_execution.shadow import load_user_shadow_report

            shadow = load_user_shadow_report(uid)
            if shadow:
                payload["shadow_comparison"] = {
                    "generated_at": shadow.get("generated_at"),
                    "delta": shadow.get("delta"),
                    "scoped_open": (shadow.get("scoped") or {}).get("open_positions"),
                    "execution_open": (shadow.get("execution") or {}).get("open_positions"),
                }
    except Exception:
        pass
    return payload


def build_user_execution_positions_payload(*, user_id: str, limit: int = 50) -> dict[str, Any]:
    uid = str(user_id or "").strip()
    items: list[dict[str, Any]] = []
    source = "json"
    try:
        from db.paper_user_execution import list_user_open_positions

        items = list_user_open_positions(uid, limit=limit)
        if items:
            source = "pg"
    except Exception:
        items = []
    if not items:
        try:
            from paper_execution.runner import load_user_open_positions

            paths = _user_execution_paths(uid)
            for pos in load_user_open_positions(paths):
                items.append(
                    {
                        "symbol": pos.get("symbol"),
                        "market": "CRYPTO",
                        "strategy_id": pos.get("strategy_id"),
                        "side": pos.get("direction") or pos.get("side"),
                        "entry_price": pos.get("entry_price") or pos.get("trigger_price"),
                        "current_stop": pos.get("current_stop") or pos.get("stop_price"),
                        "metadata": pos,
                    }
                )
            source = "json"
        except Exception:
            items = []
    return {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "user_id": uid,
        "mode": "read_only_paper_account",
        "source": source,
        "count": len(items),
        "items": items[:limit],
    }


def build_user_execution_pending_payload(*, user_id: str, limit: int = 50) -> dict[str, Any]:
    uid = str(user_id or "").strip()
    items: list[dict[str, Any]] = []
    source = "json"
    try:
        from db.paper_user_execution import list_user_pending_orders

        items = list_user_pending_orders(uid, limit=limit)
        if items:
            source = "pg"
    except Exception:
        items = []
    if not items:
        paths = _user_execution_paths(uid)
        if paths.pending_orders_json.is_file():
            try:
                raw = json.loads(paths.pending_orders_json.read_text(encoding="utf-8"))
                from db.paper_user_execution import parse_pending_orders_from_json

                items = parse_pending_orders_from_json(raw)
                source = "json"
            except Exception:
                items = []
    return {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "user_id": uid,
        "mode": "read_only_paper_account",
        "source": source,
        "count": len(items),
        "items": items[:limit],
    }
