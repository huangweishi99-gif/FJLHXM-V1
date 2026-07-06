from __future__ import annotations

import argparse
import copy
import json
import math
import os
import time
from contextlib import nullcontext
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

import pandas as pd
import requests

from fengji_core.ds03_pending_fill import resolve_ds03_pending_fill
from fengji_core.ds08_pending_fill import (
    DEFAULT_DS08_MAX_LAG_BARS,
    check_ds08_setup_key_stale,
    resolve_ds08_pending_fill,
)
from fengji_core.runtime_stop_updater import refresh_position_stop
from fengji_core.state_lock import file_lock
from fengji_core.symbol_names import crypto_display
from fengji_core.feishu_trade_notify import (
    audit_fill_for_notify,
    format_close_done,
    format_fill_done,
    format_pending_expected,
    log_notify_blocked,
    validate_close_fill,
    validate_expected_close,
    validate_pending_order,
)
from fengji_feishu_notify import (
    close_notify_key,
    fill_notify_key,
    pending_notify_key,
    pending_semantic_notify_key,
    send_feishu_once,
)


DEFAULT_BINANCE_PRICE_URLS = [
    "https://api.binance.com/api/v3/ticker/price",
    "https://fapi.binance.com/fapi/v1/ticker/price",
]


def now_text() -> str:
    return pd.Timestamp.now(tz="Asia/Shanghai").strftime("%Y-%m-%d %H:%M:%S")


def normalize_symbol(symbol: str) -> str:
    text = str(symbol).strip().upper().replace("-", "").replace("_", "")
    return text if text.endswith("USDT") else f"{text}USDT"


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    tmp.replace(path)


def append_jsonl(path: Path, item: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(item, ensure_ascii=False, default=str) + "\n")


def append_csv(path: Path, item: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame([item]).to_csv(path, mode="a", header=not path.exists(), index=False, encoding="utf-8-sig")


def safe_float(value: Any) -> float | None:
    try:
        out = float(value)
    except Exception:
        return None
    if math.isnan(out):
        return None
    return out


def send_msg(webhook: str, text: str) -> None:
    if not webhook:
        print(text)
        return
    payload = {"msg_type": "text", "content": {"text": text}}
    try:
        requests.post(webhook, headers={"Content-Type": "application/json"}, data=json.dumps(payload), timeout=8)
    except Exception as exc:
        print(f"Feishu send failed: {exc}")


def read_orders(path: Path) -> list[dict[str, Any]]:
    payload = load_json(path, [])
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    return []


def read_mock_prices(path: Path) -> dict[str, float]:
    if not path.exists():
        raise FileNotFoundError(f"price file not found: {path}")
    if path.suffix.lower() == ".json":
        payload = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(payload, dict):
            return {normalize_symbol(k): float(v) for k, v in payload.items()}
    frame = pd.read_csv(path)
    columns = {str(col).lower(): col for col in frame.columns}
    symbol_col = columns.get("symbol")
    price_col = columns.get("price") or columns.get("last_price") or columns.get("current_price")
    if symbol_col is None or price_col is None:
        raise ValueError("price csv must contain symbol and price columns")
    return {normalize_symbol(row[symbol_col]): float(row[price_col]) for _, row in frame.iterrows()}


def fetch_binance_prices(symbols: set[str], timeout: float, urls: list[str] | None = None) -> dict[str, float]:
    prices: dict[str, float] = {}
    wanted = {normalize_symbol(symbol) for symbol in symbols}
    for url in urls or DEFAULT_BINANCE_PRICE_URLS:
        try:
            resp = requests.get(url, timeout=timeout)
            resp.raise_for_status()
            payload = resp.json()
        except Exception as exc:
            print(f"Price source failed: {url} {exc}")
            continue

        items = payload if isinstance(payload, list) else [payload]
        for item in items:
            if not isinstance(item, dict):
                continue
            symbol = normalize_symbol(str(item.get("symbol", "")))
            if symbol in wanted:
                price = safe_float(item.get("price"))
                if price is not None:
                    prices[symbol] = float(price)
        if wanted.issubset(prices.keys()):
            break
    return prices


OKX_PRICE_ONLY = frozenset({"HYPEUSDT", "ATHUSDT"})


def okx_inst_id(symbol: str) -> str:
    sym = normalize_symbol(symbol)
    return f"{sym[:-4]}-USDT"


def fetch_okx_prices(symbols: set[str], timeout: float) -> dict[str, float]:
    prices: dict[str, float] = {}
    for symbol in symbols:
        clean = normalize_symbol(symbol)
        if clean not in OKX_PRICE_ONLY:
            continue
        try:
            resp = requests.get(
                "https://www.okx.com/api/v5/market/ticker",
                params={"instId": okx_inst_id(clean)},
                timeout=timeout,
            )
            resp.raise_for_status()
            payload = resp.json()
            rows = payload.get("data") if isinstance(payload, dict) else None
            if not rows:
                continue
            price = safe_float(rows[0].get("last"))
            if price is not None:
                prices[clean] = float(price)
        except Exception as exc:
            print(f"OKX price failed: {clean} {exc}")
    return prices


def load_price_snapshot(args: argparse.Namespace, symbols: set[str]) -> dict[str, float]:
    if args.price_file:
        return read_mock_prices(Path(args.price_file))
    prices = fetch_binance_prices(symbols, timeout=float(args.timeout))
    missing_okx = {
        normalize_symbol(symbol)
        for symbol in symbols
        if normalize_symbol(symbol) in OKX_PRICE_ONLY and normalize_symbol(symbol) not in prices
    }
    if missing_okx:
        prices.update(fetch_okx_prices(missing_okx, timeout=float(args.timeout)))
    return prices


def triggered(order: dict[str, Any], price: float) -> bool:
    side = str(order.get("side", "")).lower()
    trigger = safe_float(order.get("trigger_price"))
    if trigger is None:
        return False
    if side == "long":
        return price >= trigger
    if side == "short":
        return price <= trigger
    return False


def order_setup_key(order: dict[str, Any]) -> str:
    return str(order.get("setup_key", "") or "").strip()


def order_expired(order: dict[str, Any], now: pd.Timestamp | None = None) -> bool:
    valid_until = pd.to_datetime(order.get("valid_until", ""), errors="coerce")
    if pd.isna(valid_until):
        return False
    current = now or pd.Timestamp.now(tz="Asia/Shanghai")
    if getattr(current, "tzinfo", None) is not None:
        current = current.tz_convert("Asia/Shanghai").tz_localize(None)
    if getattr(valid_until, "tzinfo", None) is not None:
        valid_until = valid_until.tz_convert("Asia/Shanghai").tz_localize(None)
    return current > valid_until


def notify_claims_dir(args: argparse.Namespace) -> Path:
    return Path(getattr(args, "notify_claims_dir", "runtime/feishu_notify_claims"))


def _position_from_paper(paper_state: dict[str, Any], symbol: str) -> dict[str, Any] | None:
    symbol_state = (paper_state.get("symbols") or {}).get(normalize_symbol(symbol)) or {}
    position = symbol_state.get("open_position")
    return position if isinstance(position, dict) else None


def legacy_pending_symbol_strategy_notified(
    notified_order_ids: set[str], order: dict[str, Any]
) -> bool:
    """Migrate pre-semantic dedup: same symbol+strategy already pushed via legacy order_id keys."""
    symbol = normalize_symbol(str(order.get("symbol", "")))
    strategy = str(order.get("strategy_id", "")).strip().upper()
    if not symbol or not strategy:
        return False
    prefix = f"{symbol}-{strategy}-"
    return any(str(order_id).startswith(prefix) for order_id in notified_order_ids)


def bootstrap_pending_semantic_keys(
    state: dict[str, Any], orders: list[dict[str, Any]]
) -> None:
    """One-shot migration: map legacy order_id/setup_key notifications to semantic keys."""
    notified = set(state.setdefault("notified_pending_order_ids", []))
    notified_setup = set(state.setdefault("notified_pending_setup_keys", []))
    notified_semantic = set(state.setdefault("notified_pending_semantic_keys", []))
    for order in orders:
        semantic_key = pending_semantic_notify_key(order)
        if semantic_key in notified_semantic:
            continue
        order_id = str(order.get("order_id", ""))
        setup_key = order_setup_key(order)
        if order_id and order_id in notified:
            notified_semantic.add(semantic_key)
        elif legacy_pending_symbol_strategy_notified(notified, order):
            notified_semantic.add(semantic_key)
        elif setup_key and setup_key in notified_setup:
            notified_semantic.add(semantic_key)
    state["notified_pending_semantic_keys"] = sorted(notified_semantic)


def notify_new_pending_orders(
    args: argparse.Namespace,
    state: dict[str, Any],
    active_orders: list[dict[str, Any]],
    *,
    symbol_label_fn: Callable[[str], str] | None = None,
) -> None:
    label_fn = symbol_label_fn or crypto_display
    bootstrap_pending_semantic_keys(state, active_orders)
    notified = set(state.setdefault("notified_pending_order_ids", []))
    notified_setup = set(state.setdefault("notified_pending_setup_keys", []))
    notified_semantic = set(state.setdefault("notified_pending_semantic_keys", []))
    for order in active_orders:
        order_id = str(order.get("order_id", ""))
        setup_key = order_setup_key(order)
        semantic_key = pending_semantic_notify_key(order)
        if order_id and order_id in notified:
            continue
        if semantic_key in notified_semantic:
            continue
        if setup_key and setup_key in notified_setup:
            continue
        check = validate_pending_order(order)
        if not check.ok:
            log_notify_blocked("pending", order_id, check)
            continue
        symbol = normalize_symbol(str(order.get("symbol", "")))
        notify_key = semantic_key
        sent = send_feishu_once(
            notify_claims_dir(args),
            notify_key,
            args.feishu_webhook,
            format_pending_expected(order, symbol_label=label_fn(symbol), now=now_text()),
            send_msg,
        )
        if sent:
            if order_id:
                notified.add(order_id)
            if setup_key:
                notified_setup.add(setup_key)
            notified_semantic.add(semantic_key)
    state["notified_pending_order_ids"] = sorted(notified)
    state["notified_pending_setup_keys"] = sorted(notified_setup)
    state["notified_pending_semantic_keys"] = sorted(notified_semantic)


def notify_fill_and_expected_close(
    args: argparse.Namespace,
    order: dict[str, Any],
    fill_price: float,
    record: dict[str, Any],
    paper_state: dict[str, Any],
    *,
    market: str = "crypto",
    symbol_label_fn: Callable[[str], str] | None = None,
    position: dict[str, Any] | None = None,
    extra_fill_lines: list[str] | None = None,
) -> None:
    label_fn = symbol_label_fn or crypto_display
    order_id = str(order.get("order_id", ""))
    symbol = normalize_symbol(str(order.get("symbol", "")))
    data_dir = Path(getattr(args, "data_dir", "data"))
    audit, check = audit_fill_for_notify(record, data_dir=data_dir, market=market)
    if not check.ok:
        log_notify_blocked("fill", order_id, check)
        return
    if position is None:
        position = _position_from_paper(paper_state, symbol)
    include_expected = False
    if position:
        close_check = validate_expected_close(position)
        if not close_check.ok:
            log_notify_blocked("expected_close", order_id, close_check)
        else:
            include_expected = True
    send_feishu_once(
        notify_claims_dir(args),
        fill_notify_key(order_id),
        args.feishu_webhook,
        format_fill_done(
            order,
            fill_price,
            symbol_label=label_fn(symbol),
            now=now_text(),
            audit=audit,
            extra_lines=extra_fill_lines,
            position=position if include_expected else None,
        ),
        send_msg,
    )


def notify_close_fill(
    args: argparse.Namespace,
    symbol: str,
    position: dict[str, Any],
    exit_price: float,
    pnl: dict[str, Any],
    *,
    exit_reason: str = "stop",
    symbol_label_fn: Callable[[str], str] | None = None,
    bar_hint: str = "",
) -> None:
    label_fn = symbol_label_fn or crypto_display
    order_id = str(position.get("order_id", ""))
    check = validate_close_fill(position, float(exit_price), exit_reason=exit_reason)
    if not check.ok:
        log_notify_blocked("close", order_id, check)
        return
    clean = normalize_symbol(symbol)
    send_feishu_once(
        notify_claims_dir(args),
        close_notify_key(
            clean,
            order_id,
            str(position.get("entry_time", "")),
            str(position.get("strategy_id", "")),
        ),
        args.feishu_webhook,
        format_close_done(
            position,
            float(exit_price),
            {**pnl, "unit": pnl.get("unit", "USDT")},
            symbol_label=label_fn(clean),
            now=now_text(),
            exit_reason=exit_reason,
            bar_hint=bar_hint,
        ),
        send_msg,
    )


def should_skip_for_position(order: dict[str, Any], paper_state: dict[str, Any], max_ds01_entries: int) -> tuple[bool, str]:
    symbol = normalize_symbol(str(order.get("symbol", "")))
    symbol_state = (paper_state.get("symbols") or {}).get(symbol) or {}
    open_position = symbol_state.get("open_position")
    if not open_position:
        return False, ""

    order_side = str(order.get("side", "")).lower()
    position_side = "long" if int(open_position.get("side", 0) or 0) == 1 else "short"
    strategy = str(order.get("strategy_id", "")).upper()
    position_strategy = str(open_position.get("strategy_id", "")).upper()
    if strategy == "DS01" and position_strategy == "DS01" and order_side == position_side:
        entries = int(open_position.get("entries", 0) or len(open_position.get("legs", [])) or 1)
        if entries < max_ds01_entries:
            return False, ""
    return True, "symbol already has an open position"


def ensure_paper_symbol_state(paper_state: dict[str, Any], symbol: str, args: argparse.Namespace) -> dict[str, Any]:
    clean = normalize_symbol(symbol)
    paper_state.setdefault("version", 1)
    paper_state.setdefault("started_at", now_text())
    paper_state.setdefault("symbols", {})
    paper_state.setdefault("events", [])
    paper_state.setdefault("closed_trades", [])
    symbol_state = paper_state["symbols"].setdefault(clean, {})
    symbol_state.setdefault("last_bar_key", "")
    symbol_state.setdefault("initialized", True)
    symbol_state.setdefault("seen_entries", [])
    symbol_state.setdefault("closed_entries", [])
    symbol_state.setdefault("closed_trades", [])
    symbol_state.setdefault("events", [])
    symbol_state["initial_cash"] = float(getattr(args, "initial_cash", 1000.0))
    symbol_state.setdefault("realized_pnl", 0.0)
    symbol_state["equity"] = float(symbol_state["initial_cash"]) + float(symbol_state.get("realized_pnl", 0.0))
    return symbol_state


def side_int(side: str) -> int:
    return 1 if str(side).lower() == "long" else -1


def weighted_average(legs: list[dict[str, Any]]) -> float:
    weight_sum = sum(float(leg.get("margin", 0.0) or 0.0) for leg in legs)
    if weight_sum <= 0:
        return float(legs[-1].get("entry_price", 0.0) or 0.0)
    return sum(float(leg.get("entry_price", 0.0) or 0.0) * float(leg.get("margin", 0.0) or 0.0) for leg in legs) / weight_sum


def update_paper_state_on_fill(args: argparse.Namespace, paper_state: dict[str, Any], fill: dict[str, Any]) -> dict[str, Any]:
    symbol = normalize_symbol(str(fill.get("symbol", "")))
    symbol_state = ensure_paper_symbol_state(paper_state, symbol, args)
    strategy = str(fill.get("strategy_id", "")).upper()
    side_text = str(fill.get("side", "")).lower()
    direction = "long" if side_text == "long" else "short"
    entry_price = float(fill.get("fill_price", fill.get("trigger_price", 0.0)) or 0.0)
    margin = float(getattr(args, "margin_per_trade", 200.0))
    leverage = float(getattr(args, "leverage", 2.0))
    order_id = str(fill.get("order_id", ""))
    leg = {
        "order_id": order_id,
        "symbol": symbol,
        "strategy_id": strategy,
        "side": side_int(side_text),
        "direction": direction,
        "entry_time": str(fill.get("time", now_text())),
        "entry_price": entry_price,
        "trigger_price": float(fill.get("trigger_price", entry_price) or entry_price),
        "initial_stop": safe_float(fill.get("stop_price")) or 0.0,
        "margin": margin,
        "leverage": leverage,
        "notional": margin * leverage,
        "timeframe": fill.get("timeframe", ""),
        "setup": fill.get("setup", ""),
    }

    open_position = symbol_state.get("open_position")
    if (
        open_position
        and strategy == "DS01"
        and str(open_position.get("strategy_id", "")).upper() == "DS01"
        and int(open_position.get("side", 0) or 0) == leg["side"]
    ):
        legs = list(open_position.get("legs", [])) + [leg]
        total_margin = sum(float(item.get("margin", 0.0) or 0.0) for item in legs)
        open_position["legs"] = legs
        open_position["entries"] = len(legs)
        open_position["entry_price"] = weighted_average(legs)
        open_position["margin"] = total_margin
        open_position["notional"] = total_margin * leverage
        open_position["latest_order_id"] = order_id
        open_position["initial_stop"] = leg["initial_stop"]
        open_position["current_stop"] = leg["initial_stop"]
    else:
        open_position = {
            "source": "pending_order",
            "trade_key": f"pending|{order_id}",
            "order_id": order_id,
            "symbol": symbol,
            "strategy_id": strategy,
            "side": leg["side"],
            "direction": direction,
            "entry_time": leg["entry_time"],
            "entry_price": entry_price,
            "initial_stop": leg["initial_stop"],
            "current_stop": leg["initial_stop"],
            "units": 1,
            "entries": 1,
            "legs": [leg],
            "margin": margin,
            "leverage": leverage,
            "notional": margin * leverage,
            "virtual_initial_cash": float(getattr(args, "initial_cash", 1000.0)),
        }
    symbol_state["open_position"] = open_position
    symbol_state.setdefault("seen_entries", [])
    symbol_state["seen_entries"] = list(dict.fromkeys([*symbol_state["seen_entries"], f"pending|{order_id}", order_id]))[-500:]

    event = {
        "time": fill.get("time", now_text()),
        "event_type": "open",
        "source": "pending_order",
        "market": "CRYPTO",
        "symbol": symbol,
        "strategy_id": strategy,
        "direction": direction,
        "entry_price": entry_price,
        "initial_stop": leg["initial_stop"],
        "margin": margin,
        "virtual_initial_cash": float(getattr(args, "initial_cash", 1000.0)),
        "order_id": order_id,
    }
    paper_state.setdefault("events", []).append(event)
    paper_state["events"] = paper_state["events"][-800:]
    symbol_state.setdefault("events", []).append(event)
    symbol_state["events"] = symbol_state["events"][-300:]
    return open_position


def open_position_symbols(paper_state: dict[str, Any]) -> set[str]:
    symbols: set[str] = set()
    for symbol, symbol_state in (paper_state.get("symbols") or {}).items():
        if isinstance(symbol_state, dict) and symbol_state.get("open_position"):
            symbols.add(normalize_symbol(symbol))
    return symbols


def stop_triggered(position: dict[str, Any], price: float) -> bool:
    stop = safe_float(position.get("current_stop")) or safe_float(position.get("initial_stop"))
    if stop is None or stop <= 0:
        return False
    side = int(position.get("side", 0) or 0)
    if side == 1:
        return price <= stop
    if side == -1:
        return price >= stop
    return False


@dataclass
class PlannedStopExit:
    symbol: str
    order_id: str
    exit_price: float
    exit_reason: str
    exit_bar: dict[str, Any] | None = None


@dataclass
class PlannedFill:
    order: dict[str, Any]
    fill_price: float
    price_source: str
    ds03_meta: dict[str, Any] = field(default_factory=dict)
    ds08_meta: dict[str, Any] = field(default_factory=dict)
    consume_ds03_setup_key: bool = False


@dataclass
class PlannedCancel:
    order: dict[str, Any]
    cancel_reason: str
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class PlannedSkip:
    order: dict[str, Any]
    skip_reason: str
    last_price: float


def precompute_stop_exit_plans(
    args: argparse.Namespace,
    paper_snapshot: dict[str, Any],
    prices: dict[str, float],
    precomputed_stops: dict[str, dict[str, Any]],
) -> list[PlannedStopExit]:
    from fengji_core.stop_bar_monitor import (
        read_stop_bar_for_position,
        stop_bar_after_entry,
        stop_crossed,
        stop_exit_fill,
        stop_timeframe_for_position,
    )

    plans: list[PlannedStopExit] = []
    for symbol, symbol_state in (paper_snapshot.get("symbols") or {}).items():
        if not isinstance(symbol_state, dict):
            continue
        position = symbol_state.get("open_position")
        if not position:
            continue
        clean = normalize_symbol(symbol)
        pos_copy = copy.deepcopy(position)
        hint = precomputed_stops.get(clean)
        if hint and hint.get("current_stop") is not None:
            pos_copy["current_stop"] = hint["current_stop"]
        stop_bar = None
        exit_price: float | None = None
        exit_reason = "stop"
        if stop_timeframe_for_position(pos_copy):
            stop_bar = read_stop_bar_for_position(args, clean, pos_copy)
            if stop_bar is None or not stop_bar_after_entry(pos_copy, stop_bar):
                continue
            if not stop_crossed(pos_copy, stop_bar):
                continue
            exit_price, exit_reason = stop_exit_fill(pos_copy, stop_bar)
        else:
            price = prices.get(clean)
            if price is None or not stop_triggered(pos_copy, float(price)):
                continue
            exit_price = float(price)
        plans.append(
            PlannedStopExit(
                symbol=clean,
                order_id=str(position.get("order_id", "")),
                exit_price=float(exit_price),
                exit_reason=str(exit_reason),
                exit_bar=stop_bar,
            )
        )
    return plans


def apply_stop_exit_plans(
    args: argparse.Namespace,
    paper_state: dict[str, Any],
    plans: list[PlannedStopExit],
) -> tuple[list[dict[str, Any]], list[tuple[dict[str, Any], dict[str, Any], float, str]]]:
    closed: list[dict[str, Any]] = []
    notify_queue: list[tuple[dict[str, Any], dict[str, Any], float, str]] = []
    for plan in plans:
        symbol_state = (paper_state.get("symbols") or {}).get(plan.symbol)
        if not isinstance(symbol_state, dict):
            continue
        position = symbol_state.get("open_position")
        if not position:
            continue
        if str(position.get("order_id", "")) != plan.order_id:
            continue
        position_snapshot = copy.deepcopy(position)
        record = close_position_on_stop(
            args,
            paper_state,
            plan.symbol,
            symbol_state,
            plan.exit_price,
            exit_reason=plan.exit_reason,
            exit_bar=plan.exit_bar,
        )
        if record:
            closed.append(record)
            notify_queue.append((record, position_snapshot, plan.exit_price, plan.exit_reason))
    return closed, notify_queue


def calc_position_pnl(position: dict[str, Any], exit_price: float, args: argparse.Namespace) -> dict[str, Any]:
    entry = float(position.get("entry_price", 0.0) or 0.0)
    side = int(position.get("side", 0) or 0)
    margin = float(position.get("margin", 0.0) or getattr(args, "margin_per_trade", 200.0))
    leverage = float(position.get("leverage", 0.0) or getattr(args, "leverage", 2.0))
    notional = float(position.get("notional", 0.0) or margin * leverage)
    fee_rate = float(getattr(args, "fee_rate", 0.0005))
    slippage_rate = float(getattr(args, "slippage_rate", 0.0003))
    if entry <= 0 or side == 0:
        gross = 0.0
    else:
        gross = notional * side * (exit_price - entry) / entry
    costs = notional * (fee_rate + slippage_rate) * 2
    return {
        "gross_pnl": gross,
        "costs": costs,
        "net_pnl": gross - costs,
        "notional": notional,
        "margin": margin,
    }


def close_position_on_stop(
    args: argparse.Namespace,
    paper_state: dict[str, Any],
    symbol: str,
    symbol_state: dict[str, Any],
    exit_price: float,
    *,
    exit_reason: str = "stop",
    exit_bar: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    position = symbol_state.get("open_position")
    if not position:
        return None
    pnl = calc_position_pnl(position, exit_price, args)
    net = float(pnl["net_pnl"])
    initial_cash = float(symbol_state.get("initial_cash", getattr(args, "initial_cash", 1000.0)) or 1000.0)
    symbol_state["realized_pnl"] = float(symbol_state.get("realized_pnl", 0.0) or 0.0) + net
    symbol_state["equity"] = initial_cash + float(symbol_state["realized_pnl"])
    record = {
        "closed_at": now_text(),
        "source": "pending_order",
        "symbol": normalize_symbol(symbol),
        "strategy_id": position.get("strategy_id", ""),
        "direction": position.get("direction", ""),
        "side": int(position.get("side", 0) or 0),
        "entry_time": position.get("entry_time", ""),
        "exit_time": now_text(),
        "entry_price": float(position.get("entry_price", 0.0) or 0.0),
        "exit_price": float(exit_price),
        "initial_stop": safe_float(position.get("initial_stop")) or 0.0,
        "exit_reason": exit_reason,
        "entries": int(position.get("entries", 1) or 1),
        "margin": float(pnl["margin"]),
        "leverage": float(position.get("leverage", getattr(args, "leverage", 2.0)) or 2.0),
        "notional": float(pnl["notional"]),
        "gross_pnl": float(pnl["gross_pnl"]),
        "costs": float(pnl["costs"]),
        "net_pnl": net,
        "return_on_symbol_cash": net / initial_cash if initial_cash else 0.0,
        "equity_after": float(symbol_state["equity"]),
        "order_id": position.get("order_id", ""),
    }
    symbol_state.setdefault("closed_trades", []).append(record)
    symbol_state["closed_trades"] = symbol_state["closed_trades"][-200:]
    paper_state.setdefault("closed_trades", []).append(record)
    paper_state["closed_trades"] = paper_state["closed_trades"][-1000:]
    event = {
        "time": now_text(),
        "event_type": "close",
        "source": "pending_order",
        "market": "CRYPTO",
        "symbol": normalize_symbol(symbol),
        "strategy_id": position.get("strategy_id", ""),
        "net_pnl": net,
        "equity_after": float(symbol_state["equity"]),
        "exit_reason": exit_reason,
    }
    if exit_bar:
        event["exit_bar_timeframe"] = str(exit_bar.get("timeframe", ""))
        event["exit_bar_time"] = str(exit_bar.get("date", ""))
    paper_state.setdefault("events", []).append(event)
    paper_state["events"] = paper_state["events"][-800:]
    symbol_state.setdefault("events", []).append(event)
    symbol_state["events"] = symbol_state["events"][-300:]
    symbol_state["open_position"] = None
    return record


def precompute_open_position_stops(args: argparse.Namespace, paper_snapshot: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Lock-free stop refresh preview keyed by symbol (order_id + current_stop)."""
    out: dict[str, dict[str, Any]] = {}
    if not args.paper_state_file or args.no_paper_state_update:
        return out
    data_dir = Path(getattr(args, "data_dir", "data"))
    os_state_dir = getattr(args, "os_state_dir", "runtime/fengji_os_state")
    for symbol, symbol_state in (paper_snapshot.get("symbols") or {}).items():
        if not isinstance(symbol_state, dict):
            continue
        position = symbol_state.get("open_position")
        if not position:
            continue
        clean = normalize_symbol(symbol)
        pos_copy = copy.deepcopy(position)
        refresh_position_stop(
            pos_copy,
            symbol=clean,
            data_dir=data_dir,
            os_state_dir=os_state_dir,
        )
        out[clean] = {
            "order_id": str(position.get("order_id", "")),
            "current_stop": pos_copy.get("current_stop"),
        }
    return out


def apply_precomputed_stops(paper_state: dict[str, Any], precomputed: dict[str, dict[str, Any]]) -> None:
    for symbol, symbol_state in (paper_state.get("symbols") or {}).items():
        if not isinstance(symbol_state, dict):
            continue
        position = symbol_state.get("open_position")
        if not position:
            continue
        hint = precomputed.get(normalize_symbol(symbol))
        if not hint:
            continue
        if str(position.get("order_id", "")) != str(hint.get("order_id", "")):
            continue
        if hint.get("current_stop") is not None:
            position["current_stop"] = hint["current_stop"]


def process_open_position_stops(
    args: argparse.Namespace,
    paper_state: dict[str, Any],
    prices: dict[str, float],
    *,
    skip_refresh: bool = False,
) -> list[dict[str, Any]]:
    """Legacy path; process_once uses precompute_stop_exit_plans + apply_stop_exit_plans."""
    precomputed = precompute_open_position_stops(args, paper_state) if not skip_refresh else {}
    if skip_refresh:
        for symbol, symbol_state in (paper_state.get("symbols") or {}).items():
            if not isinstance(symbol_state, dict):
                continue
            position = symbol_state.get("open_position")
            if not position:
                continue
            clean = normalize_symbol(symbol)
            precomputed[clean] = {"order_id": str(position.get("order_id", "")), "current_stop": position.get("current_stop")}
    plans = precompute_stop_exit_plans(args, paper_state, prices, precomputed)
    closed, close_notify = apply_stop_exit_plans(args, paper_state, plans)
    if closed and args.paper_state_file and not args.no_paper_state_update:
        save_json(Path(args.paper_state_file), paper_state)
    for record, position, exit_price, exit_reason in close_notify:
        append_csv(Path(args.out_dir) / "closed_trades.csv", record)
        append_jsonl(Path(args.out_dir) / "events.jsonl", {"event_type": "close", **record})
        notify_close_fill(args, record["symbol"], position, exit_price, record, exit_reason=exit_reason)
    return closed


def plan_fill_actions(
    args: argparse.Namespace,
    active_orders: list[dict[str, Any]],
    orders: list[dict[str, Any]],
    prices: dict[str, float],
    paper_snapshot: dict[str, Any],
    filled_ids: set[str],
    cancelled_ids: set[str],
    filled_setup_keys: set[str],
    cancelled_setup_keys: set[str],
) -> tuple[list[PlannedFill], list[PlannedCancel], list[PlannedSkip]]:
    fills: list[PlannedFill] = []
    cancels: list[PlannedCancel] = []
    skips: list[PlannedSkip] = []

    for order in sorted(active_orders, key=lambda item: float(item.get("priority", 9999) or 9999)):
        order_id = str(order.get("order_id", ""))
        if order_id in filled_ids or order_id in cancelled_ids:
            continue
        symbol = normalize_symbol(str(order.get("symbol", "")))
        price = prices.get(symbol)
        if price is None:
            continue
        skip, skip_reason = should_skip_for_position(order, paper_snapshot, int(args.max_ds01_entries))
        if skip:
            skips.append(PlannedSkip(order=order, skip_reason=str(skip_reason), last_price=float(price)))
            continue

        strategy = str(order.get("strategy_id", "")).upper()
        ds03_meta: dict[str, Any] = {}
        ds08_meta: dict[str, Any] = {}
        working_order = order
        if strategy == "DS08":
            stale_ds08 = check_ds08_setup_key_stale(
                order,
                symbol,
                Path(getattr(args, "data_dir", "data")),
                getattr(args, "os_state_dir", "runtime/fengji_os_state"),
            )
            if stale_ds08 and stale_ds08.get("stale"):
                cancels.append(
                    PlannedCancel(
                        order=order,
                        cancel_reason=str(stale_ds08.get("reason", "ds08_setup_key_stale")),
                        extra={k: v for k, v in stale_ds08.items() if k != "stale"},
                    )
                )
                continue
            if not triggered(order, price):
                continue
            ds08_ctx = try_fill_ds08_order(args, order, symbol, price)
            if ds08_ctx is None:
                continue
            if ds08_ctx.get("stale"):
                cancels.append(
                    PlannedCancel(
                        order=order,
                        cancel_reason=str(ds08_ctx.get("reason", "ds08_activation_bar_missed")),
                        extra={k: v for k, v in ds08_ctx.items() if k not in {"stale", "reason"}},
                    )
                )
                continue
            fill_price = float(ds08_ctx["fill_price"])
            price_source = str(ds08_ctx.get("price_source", "ds08_entry_fill"))
            ds08_meta = {
                "activation_bar_idx": ds08_ctx.get("activation_bar_idx"),
                "activation_bar_time": ds08_ctx.get("activation_bar_time"),
                "entry_ref": ds08_ctx.get("entry_ref"),
            }
            if ds08_ctx.get("initial_stop") is not None:
                working_order = {**order, "stop_price": ds08_ctx["initial_stop"]}
        else:
            fill_price = float(price)
            price_source = "mock" if args.price_file else "binance"

        consume_ds03 = False
        if strategy == "DS03":
            ds03_ctx = try_fill_ds03_order(args, order, symbol, price)
            if ds03_ctx is None:
                continue
            if ds03_ctx.get("stale"):
                cancels.append(
                    PlannedCancel(
                        order=order,
                        cancel_reason=str(ds03_ctx.get("reason", "ds03_attack_bar_missed")),
                        extra={
                            "missed_attack_bar_idx": ds03_ctx.get("missed_attack_bar_idx"),
                            "missed_attack_bar_time": ds03_ctx.get("missed_attack_bar_time"),
                        },
                    )
                )
                continue
            fill_price = float(ds03_ctx["fill_price"])
            price_source = str(ds03_ctx.get("price_source", "ds03_attack_bar"))
            ds03_meta = {
                "attack_bar_idx": ds03_ctx.get("attack_bar_idx"),
                "attack_bar_time": ds03_ctx.get("attack_bar_time"),
                "peak_key": ds03_ctx.get("peak_key"),
                "trigger_source": ds03_ctx.get("trigger_source"),
            }
            if ds03_ctx.get("initial_stop") is not None:
                working_order = {**order, "stop_price": ds03_ctx["initial_stop"]}
            consume_ds03 = bool(order_setup_key(order))
        elif strategy != "DS08" and not triggered(order, price):
            continue

        fills.append(
            PlannedFill(
                order=working_order,
                fill_price=fill_price,
                price_source=price_source,
                ds03_meta=ds03_meta,
                ds08_meta=ds08_meta,
                consume_ds03_setup_key=consume_ds03,
            )
        )
    return fills, cancels, skips


def apply_fill_plans(
    args: argparse.Namespace,
    state: dict[str, Any],
    paper_state: dict[str, Any],
    orders: list[dict[str, Any]],
    plans: list[PlannedFill],
    cancel_plans: list[PlannedCancel],
    *,
    filled_ids: set[str],
    cancelled_ids: set[str],
    filled_setup_keys: set[str],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    filled_records: list[dict[str, Any]] = []
    skipped_records: list[dict[str, Any]] = []
    notify_queue: list[tuple[dict[str, Any], dict[str, Any], float, dict[str, Any]]] = []

    for plan in cancel_plans:
        order_id = str(plan.order.get("order_id", ""))
        if order_id in filled_ids or order_id in cancelled_ids:
            continue
        cancel = cancel_stale_order(state, plan.order, cancel_reason=plan.cancel_reason, extra=plan.extra or None)
        cancelled_ids.add(order_id)
        skipped_records.append(cancel)

    for plan in plans:
        order = plan.order
        order_id = str(order.get("order_id", ""))
        if order_id in filled_ids or order_id in cancelled_ids:
            continue
        symbol = normalize_symbol(str(order.get("symbol", "")))
        skip, skip_reason = should_skip_for_position(order, paper_state, int(args.max_ds01_entries))
        if skip:
            skipped_records.append(
                {
                    "time": now_text(),
                    "event_type": "skip",
                    "skip_reason": skip_reason,
                    "last_price": plan.fill_price,
                    **order,
                }
            )
            continue

        if plan.consume_ds03_setup_key:
            setup_key = order_setup_key(order)
            if setup_key:
                consumed = set(state.setdefault("consumed_ds03_setup_keys", []))
                consumed.add(setup_key)
                state["consumed_ds03_setup_keys"] = sorted(consumed)

        record = {
            "time": now_text(),
            "event_type": "fill",
            "fill_price": plan.fill_price,
            "price_source": plan.price_source,
            **plan.ds03_meta,
            **plan.ds08_meta,
            **order,
        }
        filled_ids.add(order_id)
        setup_key = order_setup_key(order)
        if setup_key:
            filled_setup_keys.add(setup_key)
        state.setdefault("filled_order_ids", [])
        state.setdefault("filled_setup_keys", [])
        state.setdefault("fills", [])
        state["filled_order_ids"] = sorted(filled_ids)
        state["filled_setup_keys"] = sorted(filled_setup_keys)
        state["fills"].append(record)
        state["fills"] = state["fills"][-1000:]
        filled_records.append(record)
        if args.paper_state_file and not args.no_paper_state_update:
            update_paper_state_on_fill(args, paper_state, record)
        for cancel in cancel_conflicting_orders(state, order, orders):
            cancelled_ids.add(str(cancel.get("order_id", "")))
            skipped_records.append(cancel)
        notify_queue.append((order, record, plan.fill_price, copy.deepcopy(paper_state)))

    cancelled_ids.update(set(state.get("cancelled_order_ids", [])))
    return filled_records, skipped_records, notify_queue


def cancel_conflicting_orders(state: dict[str, Any], filled: dict[str, Any], orders: list[dict[str, Any]]) -> list[dict[str, Any]]:
    filled_id = str(filled.get("order_id", ""))
    symbol = normalize_symbol(str(filled.get("symbol", "")))
    side = str(filled.get("side", "")).lower()
    strategy = str(filled.get("strategy_id", "")).upper()
    cancelled: list[dict[str, Any]] = []
    cancelled_ids = set(state.setdefault("cancelled_order_ids", []))
    cancelled_setup_keys = set(state.setdefault("cancelled_setup_keys", []))
    filled_ids = set(state.setdefault("filled_order_ids", []))

    for order in orders:
        order_id = str(order.get("order_id", ""))
        if not order_id or order_id == filled_id or order_id in cancelled_ids or order_id in filled_ids:
            continue
        if normalize_symbol(str(order.get("symbol", ""))) != symbol:
            continue
        order_side = str(order.get("side", "")).lower()
        order_strategy = str(order.get("strategy_id", "")).upper()
        should_cancel = order_side != side
        if strategy != "DS01":
            should_cancel = True
        elif order_strategy != "DS01":
            should_cancel = True
        if should_cancel:
            cancelled_ids.add(order_id)
            setup_key = order_setup_key(order)
            if setup_key:
                cancelled_setup_keys.add(setup_key)
            cancelled.append(
                {
                    **order,
                    "time": now_text(),
                    "event_type": "cancel",
                    "cancel_reason": "conflict_after_fill",
                    "filled_order_id": filled_id,
                }
            )
    state["cancelled_order_ids"] = sorted(cancelled_ids)
    state["cancelled_setup_keys"] = sorted(cancelled_setup_keys)
    return cancelled


def process_once(args: argparse.Namespace, state: dict[str, Any]) -> dict[str, Any]:
    orders = read_orders(Path(args.orders_file))
    # 锁外快照仅用于「发现需要取价的品种」；真正的状态读改写在锁内重载。
    discovery_snapshot = load_json(Path(args.paper_state_file), {}) if args.paper_state_file else {}
    filled_ids = set(state.get("filled_order_ids", []))
    cancelled_ids = set(state.get("cancelled_order_ids", []))
    filled_setup_keys = set(state.get("filled_setup_keys", []))
    cancelled_setup_keys = set(state.get("cancelled_setup_keys", []))
    active_orders = [
        order
        for order in orders
        if str(order.get("status", "")).upper() in {"ACTIVE", "READY_TRIGGERED"}
        and str(order.get("order_id", "")) not in filled_ids
        and str(order.get("order_id", "")) not in cancelled_ids
        and (not order_setup_key(order) or order_setup_key(order) not in filled_setup_keys)
        and (not order_setup_key(order) or order_setup_key(order) not in cancelled_setup_keys)
        and not order_expired(order)
    ]
    symbols = {normalize_symbol(str(order.get("symbol", ""))) for order in active_orders}
    symbols.update(open_position_symbols(discovery_snapshot))
    prices = load_price_snapshot(args, symbols) if symbols else {}

    notify_new_pending_orders(args, state, active_orders)

    paper_updates = bool(args.paper_state_file) and not args.no_paper_state_update
    precomputed_stops: dict[str, dict[str, Any]] = {}
    stop_exit_plans: list[PlannedStopExit] = []
    if paper_updates:
        planning_snapshot = load_json(Path(args.paper_state_file), {})
        precomputed_stops = precompute_open_position_stops(args, planning_snapshot)
        stop_exit_plans = precompute_stop_exit_plans(args, planning_snapshot, prices, precomputed_stops)

    planned_fills, planned_cancels, planned_skips = plan_fill_actions(
        args,
        active_orders,
        orders,
        prices,
        discovery_snapshot,
        filled_ids,
        cancelled_ids,
        filled_setup_keys,
        cancelled_setup_keys,
    )

    closed_records: list[dict[str, Any]] = []
    filled_records: list[dict[str, Any]] = []
    skipped_records: list[dict[str, Any]] = []
    close_notify_queue: list[tuple[dict[str, Any], dict[str, Any], float, str]] = []
    fill_notify_queue: list[tuple[dict[str, Any], dict[str, Any], float, dict[str, Any]]] = []

    if paper_updates:
        lock_cm = file_lock(Path(args.paper_state_file))
    else:
        lock_cm = nullcontext()
    with lock_cm:
        paper_state = load_json(Path(args.paper_state_file), {}) if paper_updates else discovery_snapshot
        if precomputed_stops:
            apply_precomputed_stops(paper_state, precomputed_stops)
        closed_records, close_notify_queue = apply_stop_exit_plans(args, paper_state, stop_exit_plans)
        filled_records, skipped_in_lock, fill_notify_queue = apply_fill_plans(
            args,
            state,
            paper_state,
            orders,
            planned_fills,
            planned_cancels,
            filled_ids=filled_ids,
            cancelled_ids=cancelled_ids,
            filled_setup_keys=filled_setup_keys,
        )
        skipped_records.extend(skipped_in_lock)
        if paper_updates and (closed_records or filled_records):
            save_json(Path(args.paper_state_file), paper_state)

    for skip in planned_skips:
        skipped_records.append(
            {
                "time": now_text(),
                "event_type": "skip",
                "skip_reason": skip.skip_reason,
                "last_price": skip.last_price,
                **skip.order,
            }
        )

    for record, position, exit_price, exit_reason in close_notify_queue:
        append_csv(Path(args.out_dir) / "closed_trades.csv", record)
        append_jsonl(Path(args.out_dir) / "events.jsonl", {"event_type": "close", **record})
        notify_close_fill(args, record["symbol"], position, exit_price, record, exit_reason=exit_reason)

    for order, record, fill_price, paper_snapshot in fill_notify_queue:
        append_csv(Path(args.out_dir) / "fills.csv", record)
        append_jsonl(Path(args.out_dir) / "events.jsonl", record)
        notify_fill_and_expected_close(args, order, fill_price, record, paper_snapshot)

    for record in skipped_records:
        append_jsonl(Path(args.out_dir) / "events.jsonl", record)

    state["last_check"] = now_text()
    state["last_prices"] = prices
    save_json(Path(args.state_file), state)
    return {
        "checked_orders": len(active_orders),
        "price_count": len(prices),
        "filled": len(filled_records),
        "skipped": len(skipped_records),
        "closed": len(closed_records),
    }


def cancel_stale_order(
    state: dict[str, Any],
    order: dict[str, Any],
    *,
    cancel_reason: str,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    order_id = str(order.get("order_id", ""))
    cancelled_ids = set(state.setdefault("cancelled_order_ids", []))
    cancelled_setup_keys = set(state.setdefault("cancelled_setup_keys", []))
    if order_id:
        cancelled_ids.add(order_id)
    setup_key = order_setup_key(order)
    if setup_key:
        cancelled_setup_keys.add(setup_key)
    state["cancelled_order_ids"] = sorted(cancelled_ids)
    state["cancelled_setup_keys"] = sorted(cancelled_setup_keys)
    payload = {
        **order,
        "time": now_text(),
        "event_type": "cancel",
        "cancel_reason": cancel_reason,
    }
    if extra:
        payload.update(extra)
    return payload


def try_fill_ds08_order(
    args: argparse.Namespace,
    order: dict[str, Any],
    symbol: str,
    live_price: float,
) -> dict[str, Any] | None:
    data_dir = Path(getattr(args, "data_dir", "data"))
    os_state_dir = getattr(args, "os_state_dir", "runtime/fengji_os_state")
    max_lag = int(getattr(args, "ds08_max_lag_bars", DEFAULT_DS08_MAX_LAG_BARS) or DEFAULT_DS08_MAX_LAG_BARS)
    return resolve_ds08_pending_fill(
        order,
        symbol,
        data_dir,
        os_state_dir,
        live_price=live_price,
        max_lag_bars=max_lag,
    )


def try_fill_ds03_order(
    args: argparse.Namespace,
    order: dict[str, Any],
    symbol: str,
    live_price: float,
) -> dict[str, Any] | None:
    data_dir = Path(getattr(args, "data_dir", "data"))
    os_state_dir = getattr(args, "os_state_dir", "runtime/fengji_os_state")
    return resolve_ds03_pending_fill(
        order,
        symbol,
        data_dir,
        os_state_dir,
        live_price=live_price,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Simulate FengJi pending-order trigger fills from live crypto prices.")
    parser.add_argument("--orders-file", default="runtime/fengji_pending_orders/pending_orders.json")
    parser.add_argument("--out-dir", default="runtime/fengji_pending_orders")
    parser.add_argument("--state-file", default="runtime/fengji_pending_orders/state.json")
    parser.add_argument("--paper-state-file", default="runtime/fengji_paper/state.json")
    parser.add_argument("--feishu-webhook", default=os.getenv("FEISHU_WEBHOOK", ""))
    parser.add_argument("--loop-seconds", type=int, default=5)
    parser.add_argument(
        "--ds08-max-lag-bars",
        type=int,
        default=DEFAULT_DS08_MAX_LAG_BARS,
        help="DS08 H1 激活棍后允许模拟成交的最大滞后 K 数（默认 1）",
    )
    parser.add_argument("--timeout", type=float, default=8.0)
    parser.add_argument("--price-file", default="", help="Optional JSON/CSV price snapshot for tests.")
    parser.add_argument("--max-ds01-entries", type=int, default=3)
    parser.add_argument("--initial-cash", type=float, default=1000.0)
    parser.add_argument("--margin-per-trade", type=float, default=200.0)
    parser.add_argument("--leverage", type=float, default=2.0)
    parser.add_argument("--fee-rate", type=float, default=0.0005)
    parser.add_argument("--slippage-rate", type=float, default=0.0003)
    parser.add_argument("--no-paper-state-update", action="store_true")
    parser.add_argument("--notify-claims-dir", default="runtime/feishu_notify_claims")
    parser.add_argument("--data-dir", default="data", help="OHLCV CSV 根目录（用于动态止损刷新）")
    parser.add_argument("--os-state-dir", default="runtime/fengji_os_state", help="OS state 目录（用于增量计算）")
    parser.add_argument("--once", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    Path(args.out_dir).mkdir(parents=True, exist_ok=True)
    state = load_json(
        Path(args.state_file),
        {
            "version": 1,
            "started_at": now_text(),
            "filled_order_ids": [],
            "cancelled_order_ids": [],
            "filled_setup_keys": [],
            "cancelled_setup_keys": [],
            "fills": [],
        },
    )
    while True:
        try:
            summary = process_once(args, state)
            print(
                f"[{now_text()}] checked={summary['checked_orders']} "
                f"prices={summary['price_count']} filled={summary['filled']} "
                f"closed={summary.get('closed', 0)} skipped={summary['skipped']}"
            )
            if args.once:
                break
            time.sleep(max(1, int(args.loop_seconds)))
        except KeyboardInterrupt:
            break
        except Exception as exc:
            print(f"[{now_text()}] pending monitor error: {exc}")
            if args.once:
                raise
            time.sleep(10)


if __name__ == "__main__":
    main()
