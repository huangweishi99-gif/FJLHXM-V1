"""Resolve per-user CRYPTO symbols and plan gates for independent paper execution."""
from __future__ import annotations

from typing import Any

EXECUTION_ENABLED_PLANS = frozenset({"standard", "pro"})


def normalize_crypto_symbol(symbol: str) -> str:
    text = str(symbol or "").strip().upper().replace("-", "").replace("_", "").replace("/", "")
    if not text:
        return ""
    return text if text.endswith("USDT") else f"{text}USDT"


def normalize_plan_id(plan_id: str | None) -> str:
    return str(plan_id or "free").strip().lower()


def execution_allowed_for_plan(plan_id: str | None) -> bool:
    return normalize_plan_id(plan_id) in EXECUTION_ENABLED_PLANS


def _symbols_from_watchlist_rows(rows: list[dict[str, Any]]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for row in rows:
        market = str(row.get("market") or "").strip().upper()
        if market not in {"CRYPTO", "CRYPTO_USDT", ""}:
            if market and market != "CRYPTO":
                continue
        status = str(row.get("status") or "").strip().lower()
        if status in {"cancelled", "paused"}:
            continue
        sym = normalize_crypto_symbol(str(row.get("symbol") or ""))
        if not sym or sym in seen:
            continue
        seen.add(sym)
        out.append(sym)
    return out


def load_user_crypto_symbols(
    user_id: str,
    *,
    local_symbols: list[str] | None = None,
    watchlist_rows: list[dict[str, Any]] | None = None,
    include_pg: bool = True,
) -> list[str]:
    """Merge PG paper_watchlist (CRYPTO) + optional local symbol list."""
    rows: list[dict[str, Any]] = list(watchlist_rows or [])
    if include_pg and user_id.strip():
        try:
            from db.paper_watchlist import WATCHLIST_STATUS_PENDING_RUNTIME, list_paper_watchlist

            pg_rows = list_paper_watchlist(user_id=user_id, status=WATCHLIST_STATUS_PENDING_RUNTIME)
            rows.extend(pg_rows)
        except Exception:
            pass

    symbols = _symbols_from_watchlist_rows(rows)
    seen = set(symbols)
    for raw in local_symbols or []:
        sym = normalize_crypto_symbol(raw)
        if sym and sym not in seen:
            seen.add(sym)
            symbols.append(sym)
    return symbols
