"""海外 crypto 模拟实盘监测：读取 paper_state，返回最新开仓列表（只读）。"""
from __future__ import annotations

import csv
import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEMO_PATH = ROOT / "web" / "data" / "demo_overseas_monitor.json"
PENDING_ORDER_PATHS = (
    Path(os.getenv("OVERSEAS_PENDING_ORDERS_PATH", "")).expanduser()
    if os.getenv("OVERSEAS_PENDING_ORDERS_PATH", "").strip()
    else None,
    ROOT / "runtime" / "overseas_pending_orders" / "pending_orders.csv",
    ROOT / "runtime" / "remote_overseas_pending" / "pending_orders.csv",
    ROOT / "runtime" / "fengji_pending_orders" / "pending_orders.csv",
)
PENDING_ACTIVE_STATUSES = {"ACTIVE", "READY_TRIGGERED", "TRIGGERED"}


def _parse_time(value: str) -> datetime:
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%Y/%m/%d %H:%M:%S"):
        try:
            return datetime.strptime(str(value).strip()[:19], fmt)
        except ValueError:
            continue
    return datetime.min


def _normalize_symbol(symbol: str) -> str:
    text = str(symbol or "").strip().upper().replace("-", "").replace("_", "")
    if text and not text.endswith("USDT"):
        text += "USDT"
    return text


def _crypto_display(symbol: str) -> str:
    try:
        from fengji_core.symbol_names import crypto_display

        return crypto_display(symbol)
    except Exception:
        return _normalize_symbol(symbol)


def _normalize_position(raw: dict[str, Any], symbol: str) -> dict[str, Any]:
    sym = _normalize_symbol(str(raw.get("symbol") or symbol))
    side = raw.get("direction") or raw.get("side")
    if side in {1, "1", "long", "LONG", "多", "buy"}:
        direction = "long"
    elif side in {-1, "-1", "short", "SHORT", "空", "sell"}:
        direction = "short"
    else:
        direction = str(side or "long").lower()

    entry_price = float(raw.get("entry_price") or raw.get("trigger_price") or 0)
    stop = float(
        raw.get("current_stop")
        or raw.get("initial_stop")
        or raw.get("stop_price")
        or 0
    )
    margin = raw.get("margin")
    notional = raw.get("notional")
    units = raw.get("units")
    leverage = float(raw.get("leverage") or 1)

    amount: float | None = None
    if notional is not None:
        amount = float(notional)
    elif margin is not None:
        amount = float(margin) * leverage

    raw_entry_time = str(raw.get("entry_time") or raw.get("created_at") or "")

    return {
        "position_id": str(
            raw.get("trade_key")
            or raw.get("key")
            or raw.get("order_id")
            or f"{sym}-{raw_entry_time}"
        ),
        "symbol": sym,
        "code": sym.removesuffix("USDT"),
        "display_name": _crypto_display(sym),
        "market": "CRYPTO",
        "main_contract_code": "",
        "main_contract_actual": "",
        "main_contract_display": "",
        "main_contract_label": "",
        "strategy_id": str(raw.get("strategy_id") or "TOTAL").upper(),
        "direction": direction,
        "direction_label": "做多" if direction == "long" else "做空",
        "entry_time": raw_entry_time,
        "entry_time_raw": raw_entry_time,
        "entry_price": entry_price,
        "current_stop": stop,
        "lots": None,
        "multiplier": 1,
        "amount_cny": amount,
        "setup": raw.get("setup") or "",
        "timeframe": raw.get("timeframe") or "1d",
        "trade_id": str(raw.get("trade_key") or raw.get("trade_id") or ""),
        "paper_origin": "overseas",
    }


def _is_valid_monitor_position(position: dict[str, Any]) -> bool:
    entry_time = _parse_time(str(position.get("entry_time") or ""))
    if entry_time == datetime.min:
        return False
    if entry_time.year < 2000:
        return False
    if entry_time > datetime.now() + timedelta(days=1):
        return False
    try:
        return float(position.get("entry_price") or 0) > 0
    except (TypeError, ValueError):
        return False


def _pending_order_candidates() -> list[Path]:
    seen: set[Path] = set()
    out: list[Path] = []
    for path in PENDING_ORDER_PATHS:
        if path is not None and path.is_file() and path not in seen:
            seen.add(path)
            out.append(path)
    return out


def _load_current_pending_sides() -> dict[str, dict[str, Any]]:
    current: dict[str, dict[str, Any]] = {}
    for path in _pending_order_candidates():
        try:
            with path.open("r", newline="", encoding="utf-8-sig") as fh:
                rows = list(csv.DictReader(fh))
        except Exception:
            continue
        for row in rows:
            status = str(row.get("status") or row.get("radar_status") or "").strip().upper()
            if status not in PENDING_ACTIVE_STATUSES:
                continue
            side = str(row.get("side") or "").strip().lower()
            if side not in {"long", "short"}:
                continue
            symbol = _normalize_symbol(str(row.get("symbol") or ""))
            if not symbol:
                continue
            latest = _parse_time(str(row.get("latest_time") or row.get("created_at") or ""))
            if symbol not in current or latest > current[symbol].get("latest_time", datetime.min):
                current[symbol] = {
                    "side": side,
                    "os_camp": str(row.get("os_camp") or "").strip().lower(),
                    "latest_time": latest,
                    "source": path.name,
                }
    return current


def _filter_positions_against_pending(positions: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], int]:
    current = _load_current_pending_sides()
    if not current:
        return positions, 0
    kept: list[dict[str, Any]] = []
    filtered = 0
    for position in positions:
        symbol = _normalize_symbol(str(position.get("symbol") or ""))
        pending = current.get(symbol)
        if pending is None:
            kept.append(position)
            continue
        entry_time = _parse_time(str(position.get("entry_time") or position.get("entry_time_raw") or ""))
        pending_time = pending.get("latest_time", datetime.min)
        direction = str(position.get("direction") or "").lower()
        if (
            direction in {"long", "short"}
            and pending["side"] in {"long", "short"}
            and direction != pending["side"]
            and pending_time != datetime.min
            and entry_time != datetime.min
            and pending_time.date() >= entry_time.date()
        ):
            filtered += 1
            continue
        kept.append(position)
    return kept, filtered


def _extract_from_paper_state(data: dict[str, Any]) -> list[dict[str, Any]]:
    positions: list[dict[str, Any]] = []
    invalid_count = 0
    symbols = data.get("symbols") or {}
    if isinstance(symbols, dict):
        for sym, st in symbols.items():
            if not isinstance(st, dict):
                continue
            for pos in st.get("open_positions") or []:
                if isinstance(pos, dict):
                    normalized = _normalize_position(pos, str(pos.get("symbol") or sym))
                    if _is_valid_monitor_position(normalized):
                        positions.append(normalized)
                    else:
                        invalid_count += 1
            single = st.get("open_position")
            if isinstance(single, dict):
                normalized = _normalize_position(single, str(single.get("symbol") or sym))
                if _is_valid_monitor_position(normalized):
                    positions.append(normalized)
                else:
                    invalid_count += 1
    for ev in data.get("events") or []:
        if not isinstance(ev, dict) or str(ev.get("event_type", "")).lower() != "open":
            continue
        if str(ev.get("market") or "").upper() not in {"", "CRYPTO", "CRYPTO_USDT"}:
            continue
        sym = _normalize_symbol(str(ev.get("symbol") or ""))
        if sym and not any(p["symbol"] == sym for p in positions):
            normalized = _normalize_position(ev, sym)
            if _is_valid_monitor_position(normalized):
                positions.append(normalized)
            else:
                invalid_count += 1
    positions, conflict_count = _filter_positions_against_pending(positions)
    positions.sort(key=lambda p: _parse_time(p["entry_time"]), reverse=True)
    for pos in positions:
        pos["invalid_positions_filtered"] = invalid_count
        pos["pending_conflicts_filtered"] = conflict_count
    return positions[:7]


def load_paper_state_path() -> Path | None:
    env = os.getenv("OVERSEAS_PAPER_STATE_PATH", "").strip()
    if env:
        p = Path(env)
        if p.is_file():
            return p
    for candidate in (
        ROOT / "runtime" / "overseas_paper_state.json",
        ROOT / "runtime" / "fengji_paper" / "state.json",
        ROOT / "data" / "overseas_paper_state.json",
    ):
        if candidate.is_file():
            return candidate
    return None


def load_latest_opens() -> dict[str, Any]:
    path = load_paper_state_path()
    if path is not None:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            positions = _extract_from_paper_state(data)
            return {
                "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "source": "paper_state",
                "state_path": str(path.name),
                "market_scope": "CRYPTO",
                "positions": positions,
            }
        except Exception as exc:
            return {
                "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "source": "error",
                "market_scope": "CRYPTO",
                "error": str(exc),
                "positions": [],
            }

    if DEMO_PATH.is_file():
        demo = json.loads(DEMO_PATH.read_text(encoding="utf-8"))
        demo["source"] = "demo"
        demo.setdefault("market_scope", "CRYPTO")
        return demo

    return {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "source": "empty",
        "market_scope": "CRYPTO",
        "positions": [],
    }
