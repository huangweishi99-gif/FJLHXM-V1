from __future__ import annotations

import argparse
import json
import math
import os
import time
from pathlib import Path
from typing import Any

import pandas as pd
import requests

from fengji_feishu_notify import close_notify_key, fill_notify_key, send_feishu_once


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


def load_price_snapshot(args: argparse.Namespace, symbols: set[str]) -> dict[str, float]:
    if args.price_file:
        return read_mock_prices(Path(args.price_file))
    return fetch_binance_prices(symbols, timeout=float(args.timeout))


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


def format_fill(order: dict[str, Any], fill_price: float) -> str:
    direction = "买入做多" if str(order.get("side", "")).lower() == "long" else "卖出做空"
    stop = safe_float(order.get("stop_price"))
    stop_text = "无" if stop is None else f"{stop:.8g}"
    return (
        "🚨【峰极总定式 模拟挂单触发】\n"
        f"时间: {now_text()}\n"
        f"币种: {order.get('symbol', '')}\n"
        f"定式: {order.get('strategy_id', '')}\n"
        f"周期: {order.get('timeframe', '')}\n"
        f"方向: {direction}\n"
        f"触发价: {float(order.get('trigger_price', 0.0)):.8g}\n"
        f"最新价: {fill_price:.8g}\n"
        f"初始止损: {stop_text}\n"
        f"峰极阵营: {order.get('os_camp', '')}\n"
        f"依据: {order.get('setup', '')}\n"
        "模式: 只模拟触发，不真实下单"
    )


def format_stop_exit(symbol: str, position: dict[str, Any], exit_price: float, pnl: dict[str, Any]) -> str:
    net = float(pnl.get("net_pnl", 0.0))
    result = "盈利" if net >= 0 else "亏损"
    return (
        "✅【峰极总定式 模拟挂单平仓】\n"
        f"时间: {now_text()}\n"
        f"币种: {symbol}\n"
        f"定式: {position.get('strategy_id', '')}\n"
        f"方向: {'多头' if int(position.get('side', 0) or 0) == 1 else '空头'}\n"
        f"入场时间: {position.get('entry_time', '')}\n"
        f"平仓价格: {exit_price:.8g}\n"
        f"平均入场: {float(position.get('entry_price', 0.0) or 0.0):.8g}\n"
        f"结果: {result} {net:.2f} USDT\n"
        "退出原因: stop\n"
        "模式: 只模拟触发，不真实下单"
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
        "exit_reason": "stop",
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
        "exit_reason": "stop",
    }
    paper_state.setdefault("events", []).append(event)
    paper_state["events"] = paper_state["events"][-800:]
    symbol_state.setdefault("events", []).append(event)
    symbol_state["events"] = symbol_state["events"][-300:]
    symbol_state["open_position"] = None
    return record


def notify_claims_dir(args: argparse.Namespace) -> Path:
    return Path(getattr(args, "notify_claims_dir", "runtime/feishu_notify_claims"))


def process_open_position_stops(args: argparse.Namespace, paper_state: dict[str, Any], prices: dict[str, float]) -> list[dict[str, Any]]:
    closed: list[dict[str, Any]] = []
    if not args.paper_state_file or args.no_paper_state_update:
        return closed
    for symbol, symbol_state in (paper_state.get("symbols") or {}).items():
        if not isinstance(symbol_state, dict):
            continue
        position = symbol_state.get("open_position")
        if not position:
            continue
        clean = normalize_symbol(symbol)
        price = prices.get(clean)
        if price is None or not stop_triggered(position, float(price)):
            continue
        record = close_position_on_stop(args, paper_state, clean, symbol_state, float(price))
        if record:
            closed.append(record)
            if args.paper_state_file and not args.no_paper_state_update:
                save_json(Path(args.paper_state_file), paper_state)
            append_csv(Path(args.out_dir) / "closed_trades.csv", record)
            append_jsonl(Path(args.out_dir) / "events.jsonl", {"event_type": "close", **record})
            notify_key = close_notify_key(
                clean,
                str(position.get("order_id", "")),
                str(position.get("entry_time", record.get("entry_time", ""))),
                str(position.get("strategy_id", "")),
            )
            send_feishu_once(
                notify_claims_dir(args),
                notify_key,
                args.feishu_webhook,
                format_stop_exit(clean, position, float(price), record),
                send_msg,
            )
    return closed


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
    paper_state = load_json(Path(args.paper_state_file), {}) if args.paper_state_file else {}
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
    symbols.update(open_position_symbols(paper_state))
    prices = load_price_snapshot(args, symbols) if symbols else {}
    closed_records = process_open_position_stops(args, paper_state, prices)
    if closed_records and args.paper_state_file and not args.no_paper_state_update:
        save_json(Path(args.paper_state_file), paper_state)
    filled_records: list[dict[str, Any]] = []
    skipped_records: list[dict[str, Any]] = []

    for order in sorted(active_orders, key=lambda item: float(item.get("priority", 9999) or 9999)):
        order_id = str(order.get("order_id", ""))
        if order_id in filled_ids or order_id in cancelled_ids:
            continue
        symbol = normalize_symbol(str(order.get("symbol", "")))
        price = prices.get(symbol)
        if price is None:
            continue
        skip, skip_reason = should_skip_for_position(order, paper_state, int(args.max_ds01_entries))
        if skip:
            skipped_records.append({"time": now_text(), "event_type": "skip", "skip_reason": skip_reason, "last_price": price, **order})
            continue
        if not triggered(order, price):
            continue

        setup_key = order_setup_key(order)
        if str(order.get("strategy_id", "")).upper() == "DS03" and setup_key:
            consumed = set(state.setdefault("consumed_ds03_setup_keys", []))
            if setup_key not in consumed:
                consumed.add(setup_key)
                state["consumed_ds03_setup_keys"] = sorted(consumed)

        record = {
            "time": now_text(),
            "event_type": "fill",
            "fill_price": float(price),
            "price_source": "mock" if args.price_file else "binance",
            **order,
        }
        state.setdefault("filled_order_ids", [])
        state.setdefault("filled_setup_keys", [])
        state.setdefault("fills", [])
        filled_ids.add(order_id)
        setup_key = order_setup_key(order)
        if setup_key:
            filled_setup_keys.add(setup_key)
        state["filled_order_ids"] = sorted(filled_ids)
        state["filled_setup_keys"] = sorted(filled_setup_keys)
        state["fills"].append(record)
        state["fills"] = state["fills"][-1000:]
        filled_records.append(record)
        if args.paper_state_file and not args.no_paper_state_update:
            update_paper_state_on_fill(args, paper_state, record)
            save_json(Path(args.paper_state_file), paper_state)
        append_csv(Path(args.out_dir) / "fills.csv", record)
        append_jsonl(Path(args.out_dir) / "events.jsonl", record)
        send_feishu_once(
            notify_claims_dir(args),
            fill_notify_key(order_id),
            args.feishu_webhook,
            format_fill(order, float(price)),
            send_msg,
        )

        for cancel in cancel_conflicting_orders(state, order, orders):
            cancelled_ids.add(str(cancel.get("order_id", "")))
            append_jsonl(Path(args.out_dir) / "events.jsonl", cancel)
        cancelled_ids = set(state.get("cancelled_order_ids", []))

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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Simulate FengJi pending-order trigger fills from live crypto prices.")
    parser.add_argument("--orders-file", default="runtime/fengji_pending_orders/pending_orders.json")
    parser.add_argument("--out-dir", default="runtime/fengji_pending_orders")
    parser.add_argument("--state-file", default="runtime/fengji_pending_orders/state.json")
    parser.add_argument("--paper-state-file", default="runtime/fengji_paper/state.json")
    parser.add_argument("--feishu-webhook", default=os.getenv("FEISHU_WEBHOOK", ""))
    parser.add_argument("--loop-seconds", type=int, default=5)
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
