"""海外/主程序模拟盘（确认收线开仓）飞书通知：复用四类标题 + 自检。"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

import pandas as pd

from fengji_core.feishu_trade_notify import (
    format_close_done,
    format_fill_done,
    log_notify_blocked,
    risk_geometry_valid,
    validate_close_fill,
    validate_expected_close,
    NotifyCheckResult,
)
from fengji_feishu_notify import paper_trade_notify_key, send_feishu_once


def _safe_float(value: Any) -> float | None:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    if pd.isna(out):
        return None
    return out


def _row_dict(row: pd.Series | dict[str, Any]) -> dict[str, Any]:
    if isinstance(row, pd.Series):
        return row.to_dict()
    return dict(row)


def validate_paper_open_row(row: pd.Series | dict[str, Any]) -> NotifyCheckResult:
    data = _row_dict(row)
    side = int(data.get("side", 0) or 0)
    if side not in (1, -1):
        return NotifyCheckResult.fail("side 无效")
    entry = _safe_float(data.get("entry_price"))
    stop = _safe_float(data.get("initial_stop"))
    if entry is None or entry <= 0:
        return NotifyCheckResult.fail("entry_price 无效")
    side_text = "long" if side == 1 else "short"
    if not risk_geometry_valid(side_text, entry, stop):
        return NotifyCheckResult.fail("止损与入场价几何关系违背交易规则")
    strategy = str(data.get("strategy_id", "")).strip().upper()
    if not strategy:
        return NotifyCheckResult.fail("strategy_id 缺失")
    return NotifyCheckResult.pass_()


def paper_row_as_order(row: pd.Series | dict[str, Any]) -> dict[str, Any]:
    data = _row_dict(row)
    side = int(data.get("side", 0) or 0)
    entry = float(data.get("entry_price", 0.0) or 0.0)
    return {
        "symbol": data.get("symbol", ""),
        "strategy_id": data.get("strategy_id", ""),
        "timeframe": data.get("timeframe", "D1"),
        "side": "long" if side == 1 else "short",
        "trigger_price": entry,
        "stop_price": _safe_float(data.get("initial_stop")),
        "setup": str(data.get("setup", "") or "确认收线开仓"),
        "os_camp": data.get("os_camp", ""),
    }


def paper_open_position_from_row(row: pd.Series | dict[str, Any], *, trade_key: str) -> dict[str, Any]:
    data = _row_dict(row)
    stop = _safe_float(data.get("initial_stop")) or 0.0
    return {
        "trade_key": trade_key,
        "order_id": trade_key,
        "symbol": data.get("symbol", ""),
        "strategy_id": data.get("strategy_id", ""),
        "side": int(data.get("side", 0) or 0),
        "entry_time": str(data.get("entry_time", "")),
        "entry_price": float(data.get("entry_price", 0.0) or 0.0),
        "initial_stop": stop,
        "current_stop": stop,
    }


def notify_paper_open(
    *,
    claims_dir: Path,
    webhook: str,
    trade_key: str,
    symbol: str,
    row: pd.Series,
    symbol_label: str,
    now: str,
    meta: dict[str, Any],
    send_msg: Callable[[str, str], None],
    extra_open_lines: list[str] | None = None,
    skip_expected_close: bool = False,
) -> dict[str, Any] | None:
    check = validate_paper_open_row(row)
    if not check.ok:
        log_notify_blocked("paper_open", trade_key, check)
        return None

    order = paper_row_as_order(row)
    fill_price = float(row.get("entry_price", 0.0) or 0.0)
    extra = [
        "开仓方式: 确认收线开仓（非挂单触发）",
        f"数据: D1={meta.get('d1_time')} H1={meta.get('h1_time')}",
        "自检: 通过（入场价/止损几何）",
    ]
    if extra_open_lines:
        extra.extend(extra_open_lines)
    position = paper_open_position_from_row(row, trade_key=trade_key)
    include_expected = False
    if not skip_expected_close and (_safe_float(position.get("initial_stop")) or 0):
        close_check = validate_expected_close(position)
        if close_check.ok:
            include_expected = True
        else:
            log_notify_blocked("paper_expected_close", trade_key, close_check)
    send_feishu_once(
        claims_dir,
        paper_trade_notify_key("open", trade_key),
        webhook,
        format_fill_done(
            order,
            fill_price,
            symbol_label=symbol_label,
            now=now,
            audit=None,
            extra_lines=extra,
            position=position if include_expected else None,
        ),
        send_msg,
    )
    return position


def notify_paper_close(
    *,
    claims_dir: Path,
    webhook: str,
    trade_key: str,
    symbol: str,
    position: dict[str, Any],
    row: pd.Series,
    pnl: dict[str, Any],
    symbol_label: str,
    now: str,
    send_msg: Callable[[str, str], None],
    pnl_unit: str = "USDT",
    skip_stop_check: bool = False,
) -> None:
    exit_price = float(row.get("exit_price", 0.0) or 0.0)
    exit_reason = str(row.get("exit_reason", "") or "stop")
    if not skip_stop_check:
        check = validate_close_fill(position, exit_price, exit_reason=exit_reason)
        if not check.ok:
            log_notify_blocked("paper_close", trade_key, check)
            return
    elif exit_price <= 0:
        log_notify_blocked("paper_close", trade_key, NotifyCheckResult.fail("exit_price 无效"))
        return
    send_feishu_once(
        claims_dir,
        paper_trade_notify_key("close", trade_key),
        webhook,
        format_close_done(
            position,
            exit_price,
            {**pnl, "unit": pnl_unit},
            symbol_label=symbol_label,
            now=now,
            exit_reason=exit_reason,
            bar_hint=f"exit_time={row.get('exit_time', '')}",
        ),
        send_msg,
    )
