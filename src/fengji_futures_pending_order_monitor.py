from __future__ import annotations

import argparse
import json
import math
import os
import time
from pathlib import Path
from typing import Any

import pandas as pd

from fengji_core.os_state_store import find_data_file, market_symbol, normalize_symbol as os_normalize_symbol
from fengji_feishu_notify import close_notify_key, fill_notify_key, send_feishu_once
from fengji_pending_order_monitor import (
    append_csv,
    append_jsonl,
    cancel_conflicting_orders,
    load_json,
    now_text,
    notify_claims_dir,
    order_setup_key,
    read_orders,
    safe_float,
    save_json,
    send_msg,
)


FUTURES_MULTIPLIERS = {
    "SA": 20,
    "FG": 20,
    "RB": 10,
    "PG": 20,
    "FU": 10,
    "CJ": 5,
    "OI": 10,
    "SP": 10,
    "LH": 16,
    "JD": 5,
    "SI": 5,
    "PP": 5,
    "SH": 30,
    "EB": 5,
    "NI": 1,
    "SR": 10,
    "EG": 10,
    "AO": 20,
    "JM": 60,
    "EC": 50,
    "RU": 10,
    "BR": 5,
    "SF": 5,
    "M": 10,
    "MA": 10,
    "P": 10,
    "V": 5,
    "TA": 5,
    "UR": 20,
    "CF": 5,
    "LC": 1,
    "AU": 1000,
    "AG": 15,
    "SC": 1000,
}
DEFAULT_SYMBOL_EQUITY = 100000.0


def normalize_symbol(symbol: str) -> str:
    return os_normalize_symbol(symbol)


def display_name(symbol: str) -> str:
    return normalize_symbol(symbol).replace("USDT", "")


def side_int(side: str | int) -> int:
    if isinstance(side, int):
        return 1 if side > 0 else -1
    return 1 if str(side).lower() == "long" else -1


def side_text(side: str | int) -> str:
    return "long" if side_int(side) == 1 else "short"


def active_positions(open_positions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [pos for pos in open_positions if isinstance(pos, dict) and not pos.get("closed")]


def can_open_position(
    open_positions: list[dict[str, Any]],
    strategy_id: str,
    side: int,
    max_open_positions_per_symbol: int,
    max_ds01_entries: int,
) -> tuple[bool, str]:
    positions = active_positions(open_positions)
    if len(positions) >= max_open_positions_per_symbol:
        return False, f"单品种总持仓已达上限 {max_open_positions_per_symbol}"

    for pos in positions:
        pos_side = int(pos.get("side", 0) or 0)
        if pos_side == 0:
            return False, "存在旧版未知方向持仓，等待先平仓"
        if pos_side != side:
            return False, "已有反向持仓，等待先平仓"

    strategy_id = strategy_id.upper()
    if strategy_id == "DS01":
        ds01_count = sum(
            1
            for pos in positions
            if str(pos.get("strategy_id", "")).upper() == "DS01" and int(pos.get("side", 0) or 0) == side
        )
        if ds01_count >= max_ds01_entries:
            return False, f"DS01 同向连续开仓已达 {max_ds01_entries} 次"
        return True, "DS01 允许同向连续开仓"

    same_strategy_count = sum(
        1
        for pos in positions
        if str(pos.get("strategy_id", "")).upper() == strategy_id and int(pos.get("side", 0) or 0) == side
    )
    if same_strategy_count >= 1:
        return False, f"{strategy_id} 非连续定式已有同向持仓"
    return True, f"{strategy_id} 非连续定式允许首次开仓"


def ensure_symbol_state(paper_state: dict[str, Any], symbol: str) -> dict[str, Any]:
    clean = normalize_symbol(symbol)
    paper_state.setdefault("version", 2)
    paper_state.setdefault("started_at", now_text())
    paper_state.setdefault("symbols", {})
    symbol_state = paper_state["symbols"].setdefault(clean, {})
    symbol_state.setdefault("last_bar_key", "")
    symbol_state.setdefault("initialized", True)
    symbol_state.setdefault("open_positions", [])
    symbol_state.setdefault("seen_entries", [])
    symbol_state.setdefault("closed_entries", [])
    symbol_state.setdefault("equity", DEFAULT_SYMBOL_EQUITY)
    symbol_state.setdefault("last_updated", "")
    return symbol_state


def read_latest_bar(data_dir: Path, symbol: str, timeframes: list[str]) -> dict[str, Any] | None:
    for timeframe in timeframes:
        path = find_data_file(data_dir, symbol, timeframe)
        if not path.exists():
            continue
        try:
            frame = pd.read_csv(path)
        except Exception:
            continue
        if frame.empty:
            continue
        frame.columns = [str(col).strip().lower() for col in frame.columns]
        if "date" not in frame.columns:
            if "datetime" in frame.columns:
                frame["date"] = frame["datetime"]
            else:
                frame["date"] = frame.iloc[:, 0]
        required = {"date", "open", "high", "low", "close"}
        if not required.issubset(set(frame.columns)):
            continue
        parsed_dates = pd.to_datetime(frame["date"], errors="coerce")
        frame = frame[parsed_dates <= pd.Timestamp.now() + pd.Timedelta(days=1)].copy()
        if frame.empty:
            continue
        row = frame.tail(1).iloc[0]
        try:
            return {
                "symbol": normalize_symbol(symbol),
                "timeframe": timeframe,
                "date": str(row["date"]),
                "open": float(row["open"]),
                "high": float(row["high"]),
                "low": float(row["low"]),
                "close": float(row["close"]),
            }
        except Exception:
            continue
    return None


def load_bar_snapshot(args: argparse.Namespace, symbols: set[str]) -> dict[str, dict[str, Any]]:
    timeframes = [item.strip() for item in str(args.price_timeframes).split(",") if item.strip()]
    data_dir = Path(args.data_dir)
    bars: dict[str, dict[str, Any]] = {}
    for symbol in symbols:
        bar = read_latest_bar(data_dir, symbol, timeframes)
        if bar is not None:
            bars[normalize_symbol(symbol)] = bar
    return bars


def bar_crossed(order: dict[str, Any], bar: dict[str, Any]) -> bool:
    trigger = safe_float(order.get("trigger_price"))
    if trigger is None:
        return False
    side = str(order.get("side", "")).lower()
    if side == "long":
        return float(bar["high"]) >= trigger
    if side == "short":
        return float(bar["low"]) <= trigger
    return False


def order_expired(order: dict[str, Any], now: pd.Timestamp | None = None) -> bool:
    valid_until = pd.to_datetime(order.get("valid_until", ""), errors="coerce")
    if pd.isna(valid_until):
        return False
    current = now or pd.Timestamp.now(tz="Asia/Shanghai").tz_localize(None)
    if getattr(current, "tzinfo", None) is not None:
        current = current.tz_convert("Asia/Shanghai").tz_localize(None)
    return current > valid_until


def stop_crossed(position: dict[str, Any], bar: dict[str, Any]) -> bool:
    stop = safe_float(position.get("current_stop"))
    if stop is None:
        stop = safe_float(position.get("initial_stop"))
    if stop is None:
        stop = safe_float(position.get("stop_price"))
    if stop is None or stop <= 0:
        return False
    side = int(position.get("side", 0) or 0)
    if side == 1:
        return float(bar["low"]) <= stop
    if side == -1:
        return float(bar["high"]) >= stop
    return False


def calc_futures_pnl(position: dict[str, Any], exit_price: float, args: argparse.Namespace) -> dict[str, float]:
    entry = float(position.get("entry_price", 0.0) or 0.0)
    side = int(position.get("side", 0) or 0)
    lots = int(position.get("lots", 1) or 1)
    multiplier = float(position.get("multiplier", FUTURES_MULTIPLIERS.get(display_name(str(position.get("symbol", ""))), 10)))
    fee_rate = float(args.fee_rate)
    slippage_rate = float(args.slippage_rate)
    gross = (exit_price - entry) * side * multiplier * lots if entry > 0 and side else 0.0
    costs = (entry + exit_price) * multiplier * lots * (fee_rate + slippage_rate)
    return {"gross_pnl": gross, "costs": costs, "net_pnl": gross - costs}


def format_fill(order: dict[str, Any], fill_price: float, bar: dict[str, Any], reason: str) -> str:
    direction = "买入做多" if str(order.get("side", "")).lower() == "long" else "卖出做空"
    stop = safe_float(order.get("stop_price"))
    stop_text = "无" if stop is None else f"{stop:.8g}"
    return (
        "🚨【峰极总定式01-08国内期货A股模拟挂单触发】\n"
        f"时间: {now_text()}\n"
        f"品种: {display_name(str(order.get('symbol', '')))}\n"
        f"定式: {order.get('strategy_id', '')}\n"
        f"周期: {order.get('timeframe', '')}\n"
        f"方向: {direction}\n"
        f"挂单触发价: {float(order.get('trigger_price', 0.0)):.8g}\n"
        f"模拟成交价: {fill_price:.8g}\n"
        f"初始止损: {stop_text}\n"
        f"触发K线: {bar.get('timeframe', '')} {bar.get('date', '')} high={float(bar.get('high', 0.0)):.8g} low={float(bar.get('low', 0.0)):.8g}\n"
        f"峰极阵营: {order.get('os_camp', '')}\n"
        f"依据: {order.get('setup', '')}\n"
        f"风控规则: {reason}\n"
        "模式: 只模拟触发，不真实下单"
    )


def format_stop_exit(symbol: str, position: dict[str, Any], exit_price: float, pnl: dict[str, float], bar: dict[str, Any]) -> str:
    net = float(pnl.get("net_pnl", 0.0))
    result = "盈利" if net >= 0 else "亏损"
    return (
        "✅【峰极总定式01-08国内期货A股模拟挂单平仓】\n"
        f"时间: {now_text()}\n"
        f"品种: {display_name(symbol)}\n"
        f"定式: {position.get('strategy_id', '')}\n"
        f"方向: {'多头' if int(position.get('side', 0) or 0) == 1 else '空头'}\n"
        f"入场时间: {position.get('entry_time', '')}\n"
        f"平仓价格: {exit_price:.8g}\n"
        f"平均入场: {float(position.get('entry_price', 0.0) or 0.0):.8g}\n"
        f"结果: {result} {net:.2f} 元\n"
        f"触发K线: {bar.get('timeframe', '')} {bar.get('date', '')}\n"
        "退出原因: stop\n"
        "模式: 只模拟触发，不真实下单"
    )


def update_paper_state_on_fill(
    args: argparse.Namespace,
    paper_state: dict[str, Any],
    order: dict[str, Any],
    bar: dict[str, Any],
    risk_rule: str,
) -> dict[str, Any]:
    symbol = normalize_symbol(str(order.get("symbol", "")))
    disp = display_name(symbol)
    symbol_state = ensure_symbol_state(paper_state, symbol)
    order_id = str(order.get("order_id", ""))
    setup_key = order_setup_key(order)
    strategy_id = str(order.get("strategy_id", "")).upper()
    side = side_int(str(order.get("side", "")))
    trigger = float(order.get("trigger_price", 0.0) or 0.0)
    multiplier = FUTURES_MULTIPLIERS.get(disp, 10)
    lots = int(args.lots)
    key = f"pending|{order_id}"
    stop = safe_float(order.get("stop_price")) or 0.0

    position = {
        "key": key,
        "source": "pending_order",
        "order_id": order_id,
        "setup_key": setup_key,
        "symbol": symbol,
        "strategy_id": strategy_id,
        "side": side,
        "direction": side_text(side),
        "entry_time": str(bar.get("date", now_text())),
        "entry_price": trigger,
        "trigger_price": trigger,
        "initial_stop": stop,
        "current_stop": stop,
        "stop_price": stop,
        "lots": lots,
        "multiplier": multiplier,
        "created_at": now_text(),
        "entry_bar": f"{bar.get('timeframe', '')}:{bar.get('date', '')}",
        "risk_rule": risk_rule,
        "timeframe": order.get("timeframe", ""),
        "setup": order.get("setup", ""),
    }
    symbol_state.setdefault("open_positions", []).append(position)
    symbol_state.setdefault("seen_entries", [])
    seen = [*symbol_state["seen_entries"], key, order_id]
    if setup_key:
        seen.append(setup_key)
    symbol_state["seen_entries"] = list(dict.fromkeys(str(item) for item in seen if item))[-2000:]
    symbol_state["last_updated"] = now_text()
    return position


def append_open_trade(args: argparse.Namespace, order: dict[str, Any], position: dict[str, Any], risk_rule: str) -> None:
    record = {
        "event_time": now_text(),
        "symbol": display_name(str(order.get("symbol", ""))),
        "strategy_id": str(order.get("strategy_id", "")).upper(),
        "side": "LONG" if int(position.get("side", 0) or 0) == 1 else "SHORT",
        "action": "OPEN",
        "lots": int(position.get("lots", 1) or 1),
        "entry_time": position.get("entry_time", ""),
        "entry_price": float(position.get("entry_price", 0.0) or 0.0),
        "exit_time": "",
        "exit_price": "",
        "net_pnl": "",
        "equity": "",
        "reason": risk_rule,
        "trade_key": position.get("key", ""),
        "run_id": "pending_order",
    }
    append_csv(Path(args.trade_csv), record)
    append_csv(Path(args.out_dir) / "fills.csv", {**record, "order_id": order.get("order_id", ""), "setup_key": order_setup_key(order)})


def close_position_on_stop(
    args: argparse.Namespace,
    paper_state: dict[str, Any],
    symbol: str,
    symbol_state: dict[str, Any],
    position: dict[str, Any],
    bar: dict[str, Any],
) -> dict[str, Any]:
    stop = safe_float(position.get("current_stop")) or safe_float(position.get("initial_stop")) or safe_float(position.get("stop_price")) or 0.0
    pnl = calc_futures_pnl(position, stop, args)
    equity = float(symbol_state.get("equity", DEFAULT_SYMBOL_EQUITY) or DEFAULT_SYMBOL_EQUITY) + float(pnl["net_pnl"])
    symbol_state["equity"] = equity
    position["closed"] = True
    position["closed_at"] = now_text()
    position["exit_price"] = stop
    position["exit_time"] = str(bar.get("date", now_text()))
    position["exit_reason"] = "stop"
    symbol_state.setdefault("closed_entries", []).append(str(position.get("key", "")))
    symbol_state["closed_entries"] = list(dict.fromkeys(str(item) for item in symbol_state["closed_entries"] if item))[-2000:]
    symbol_state["last_updated"] = now_text()

    record = {
        "event_time": now_text(),
        "symbol": display_name(symbol),
        "strategy_id": str(position.get("strategy_id", "")).upper(),
        "side": "LONG" if int(position.get("side", 0) or 0) == 1 else "SHORT",
        "action": "CLOSE",
        "lots": int(position.get("lots", 1) or 1),
        "entry_time": position.get("entry_time", ""),
        "entry_price": float(position.get("entry_price", 0.0) or 0.0),
        "exit_time": str(bar.get("date", now_text())),
        "exit_price": stop,
        "net_pnl": round(float(pnl["net_pnl"]), 2),
        "equity": round(equity, 2),
        "reason": "stop",
        "trade_key": position.get("key", ""),
        "run_id": "pending_order",
        "gross_pnl": round(float(pnl["gross_pnl"]), 2),
        "costs": round(float(pnl["costs"]), 2),
    }
    append_csv(Path(args.trade_csv), record)
    append_csv(Path(args.out_dir) / "closed_trades.csv", record)
    append_jsonl(Path(args.out_dir) / "events.jsonl", {"event_type": "close", **record})
    return record


def process_open_position_stops(args: argparse.Namespace, paper_state: dict[str, Any], bars: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    closed: list[dict[str, Any]] = []
    if not args.paper_state_file or args.no_paper_state_update:
        return closed
    for symbol, symbol_state in (paper_state.get("symbols") or {}).items():
        if not isinstance(symbol_state, dict):
            continue
        bar = bars.get(normalize_symbol(symbol))
        if bar is None:
            continue
        still_open: list[dict[str, Any]] = []
        for position in active_positions(symbol_state.get("open_positions", [])):
            if stop_crossed(position, bar):
                record = close_position_on_stop(args, paper_state, normalize_symbol(symbol), symbol_state, position, bar)
                closed.append(record)
                notify_key = close_notify_key(
                    display_name(normalize_symbol(symbol)),
                    str(position.get("order_id", position.get("key", ""))),
                    str(position.get("entry_time", "")),
                    str(position.get("strategy_id", "")),
                )
                if args.paper_state_file and not args.no_paper_state_update:
                    save_json(Path(args.paper_state_file), paper_state)
                send_feishu_once(
                    notify_claims_dir(args),
                    notify_key,
                    args.feishu_webhook,
                    format_stop_exit(
                        normalize_symbol(symbol),
                        position,
                        float(record["exit_price"]),
                        {"net_pnl": float(record["net_pnl"])},
                        bar,
                    ),
                    send_msg,
                )
            else:
                still_open.append(position)
        symbol_state["open_positions"] = still_open
    return closed


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
        and (not bool(getattr(args, "enforce_valid_until", False)) or not order_expired(order))
    ]
    symbols = {normalize_symbol(str(order.get("symbol", ""))) for order in active_orders}
    for symbol, symbol_state in (paper_state.get("symbols") or {}).items():
        if isinstance(symbol_state, dict) and active_positions(symbol_state.get("open_positions", [])):
            symbols.add(normalize_symbol(symbol))

    bars = load_bar_snapshot(args, symbols) if symbols else {}
    closed_records = process_open_position_stops(args, paper_state, bars)
    if closed_records and args.paper_state_file and not args.no_paper_state_update:
        save_json(Path(args.paper_state_file), paper_state)

    filled_records: list[dict[str, Any]] = []
    skipped_records: list[dict[str, Any]] = []
    for order in sorted(active_orders, key=lambda item: float(item.get("priority", 9999) or 9999)):
        order_id = str(order.get("order_id", ""))
        if order_id in filled_ids or order_id in cancelled_ids:
            continue
        symbol = normalize_symbol(str(order.get("symbol", "")))
        bar = bars.get(symbol)
        if bar is None:
            continue
        symbol_state = ensure_symbol_state(paper_state, symbol)
        side = side_int(str(order.get("side", "")))
        strategy_id = str(order.get("strategy_id", "")).upper()
        allowed, risk_rule = can_open_position(
            symbol_state.get("open_positions", []),
            strategy_id,
            side,
            int(args.max_open_positions_per_symbol),
            int(args.max_ds01_entries),
        )
        if not allowed:
            skipped_records.append({"time": now_text(), "event_type": "skip", "skip_reason": risk_rule, "bar": bar, **order})
            continue
        if not bar_crossed(order, bar):
            continue

        setup_key = order_setup_key(order)
        if strategy_id == "DS03" and setup_key:
            consumed = set(state.setdefault("consumed_ds03_setup_keys", []))
            if setup_key not in consumed:
                consumed.add(setup_key)
                state["consumed_ds03_setup_keys"] = sorted(consumed)

        filled_ids.add(order_id)
        if setup_key:
            filled_setup_keys.add(setup_key)
        state["filled_order_ids"] = sorted(filled_ids)
        state["filled_setup_keys"] = sorted(filled_setup_keys)
        fill_price = float(order.get("trigger_price", bar.get("close", 0.0)) or bar.get("close", 0.0))
        record = {
            "time": now_text(),
            "event_type": "fill",
            "fill_price": fill_price,
            "price_source": f"local_{bar.get('timeframe', '')}_bar",
            "bar_time": bar.get("date", ""),
            "bar_high": bar.get("high"),
            "bar_low": bar.get("low"),
            **order,
        }
        state.setdefault("fills", []).append(record)
        state["fills"] = state["fills"][-1000:]
        filled_records.append(record)
        if args.paper_state_file and not args.no_paper_state_update:
            position = update_paper_state_on_fill(args, paper_state, order, bar, risk_rule)
            save_json(Path(args.paper_state_file), paper_state)
            append_open_trade(args, order, position, risk_rule)
        append_jsonl(Path(args.out_dir) / "events.jsonl", record)
        send_feishu_once(
            notify_claims_dir(args),
            fill_notify_key(order_id),
            args.feishu_webhook,
            format_fill(order, fill_price, bar, risk_rule),
            send_msg,
        )

        for cancel in cancel_conflicting_orders(state, order, orders):
            cancelled_ids.add(str(cancel.get("order_id", "")))
            append_jsonl(Path(args.out_dir) / "events.jsonl", cancel)
        cancelled_ids = set(state.get("cancelled_order_ids", []))

    for record in skipped_records:
        append_jsonl(Path(args.out_dir) / "events.jsonl", record)

    state["last_check"] = now_text()
    state["last_bars"] = bars
    save_json(Path(args.state_file), state)
    return {
        "checked_orders": len(active_orders),
        "bar_count": len(bars),
        "filled": len(filled_records),
        "skipped": len(skipped_records),
        "closed": len(closed_records),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Simulate FengJi domestic futures pending-order fills from local K-line bars.")
    parser.add_argument("--orders-file", default="runtime/fengji_pending_orders/pending_orders.json")
    parser.add_argument("--out-dir", default="runtime/fengji_pending_orders")
    parser.add_argument("--state-file", default="runtime/fengji_pending_orders/futures_pending_state.json")
    parser.add_argument("--paper-state-file", default="runtime/fengji_futures/state_futures_v2.json")
    parser.add_argument("--trade-csv", default="runtime/fengji_futures/trades_futures_astock.csv")
    parser.add_argument("--data-dir", default="data")
    parser.add_argument("--price-timeframes", default="15m,1h,1d")
    parser.add_argument("--feishu-webhook", default=os.getenv("FENGJI_FEISHU_WEBHOOK", ""))
    parser.add_argument("--loop-seconds", type=int, default=5)
    parser.add_argument("--max-ds01-entries", type=int, default=3)
    parser.add_argument("--max-open-positions-per-symbol", type=int, default=3)
    parser.add_argument("--lots", type=int, default=1)
    parser.add_argument("--fee-rate", type=float, default=0.0001)
    parser.add_argument("--slippage-rate", type=float, default=0.0002)
    parser.add_argument("--enforce-valid-until", action="store_true")
    parser.add_argument("--no-paper-state-update", action="store_true")
    parser.add_argument("--notify-claims-dir", default="runtime/feishu_notify_claims")
    parser.add_argument("--once", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not args.feishu_webhook:
        from fengji_feishu_config import resolve_feishu_webhook

        project_root = Path(__file__).resolve().parents[1]
        args.feishu_webhook = resolve_feishu_webhook(project_root)
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
                f"bars={summary['bar_count']} filled={summary['filled']} "
                f"closed={summary['closed']} skipped={summary['skipped']}",
                flush=True,
            )
            if args.once:
                break
            time.sleep(max(1, int(args.loop_seconds)))
        except KeyboardInterrupt:
            break
        except Exception as exc:
            print(f"[{now_text()}] futures pending monitor error: {exc}", flush=True)
            if args.once:
                raise
            time.sleep(10)


if __name__ == "__main__":
    main()
