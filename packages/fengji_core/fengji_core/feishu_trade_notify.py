"""飞书挂单/成交/平仓通知：四类标题 + 发送前自检（不违背交易规则才推送）。"""
from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

import pandas as pd

from fengji_core.fill_supervision import (
    FillAuditResult,
    apply_radar_ohlcv_tail,
    audit_fill_record,
    build_os_detail_frame,
    infer_record_timeframe,
    load_d1_csv,
    pending_price_fill_ok,
    resolve_ohlcv_csv,
)


def _safe_float(value: Any) -> float | None:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(out):
        return None
    return out


def _side_is_long(side: str | int) -> bool:
    if isinstance(side, int):
        return side > 0
    return str(side).strip().lower() == "long"


def _direction_text(side: str | int) -> str:
    return "买入做多" if _side_is_long(side) else "卖出做空"


def _position_side_text(side: str | int) -> str:
    return "多头" if _side_is_long(side) else "空头"


def risk_geometry_valid(side: str, trigger: float, stop: float | None) -> bool:
    if stop is None:
        return True
    if _side_is_long(side):
        return stop < trigger
    return stop > trigger


def format_camp_with_timeframe(order: dict[str, Any]) -> str:
    camp = str(order.get("os_camp", "") or "").strip()
    timeframe = str(order.get("timeframe", "") or "").strip()
    if not camp:
        return ""
    if "=" in camp or not timeframe:
        return camp
    return f"{timeframe}={camp}"


@dataclass
class NotifyCheckResult:
    ok: bool
    issues: list[str]

    @classmethod
    def pass_(cls) -> NotifyCheckResult:
        return cls(ok=True, issues=[])

    @classmethod
    def fail(cls, *issues: str) -> NotifyCheckResult:
        return cls(ok=False, issues=[item for item in issues if item])


def validate_pending_order(order: dict[str, Any]) -> NotifyCheckResult:
    """预计挂单：触发价/止损几何、方向、定式等基础规则。"""
    issues: list[str] = []
    side = str(order.get("side", "")).lower()
    if side not in {"long", "short"}:
        issues.append("side 无效")
    trigger = _safe_float(order.get("trigger_price"))
    if trigger is None or trigger <= 0:
        issues.append("trigger_price 无效")
    stop = _safe_float(order.get("stop_price"))
    if trigger is not None and not risk_geometry_valid(side, trigger, stop):
        issues.append("止损与触发价几何关系违背交易规则")
    strategy = str(order.get("strategy_id", "")).strip().upper()
    if not strategy:
        issues.append("strategy_id 缺失")
    symbol = str(order.get("symbol", "")).strip()
    if not symbol:
        issues.append("symbol 缺失")
    status = str(order.get("status", "")).upper()
    if status not in {"ACTIVE", "READY_TRIGGERED"}:
        issues.append(f"status={status} 不可推送预计挂单")
    return NotifyCheckResult(ok=not issues, issues=issues)


def _basic_fill_checks(record: dict[str, Any]) -> NotifyCheckResult:
    issues: list[str] = []
    side = str(record.get("side", "")).lower()
    if side not in {"long", "short"}:
        issues.append("side 无效")
    trigger = _safe_float(record.get("trigger_price"))
    fill_price = _safe_float(record.get("fill_price"))
    if fill_price is None or fill_price <= 0:
        issues.append("fill_price 无效")
    stop = _safe_float(record.get("stop_price"))
    if trigger is not None and fill_price is not None:
        side_int = 1 if _side_is_long(side) else -1
        if not pending_price_fill_ok(side_int, trigger, fill_price):
            issues.append("成交价未满足挂单触发价规则")
    if trigger is not None and not risk_geometry_valid(side, trigger, stop):
        issues.append("止损与触发价几何关系违背交易规则")
    return NotifyCheckResult(ok=not issues, issues=issues)


def audit_fill_for_notify(
    record: dict[str, Any],
    *,
    data_dir: Path,
    market: str,
    gap: int = 3,
) -> tuple[FillAuditResult | None, NotifyCheckResult]:
    """成交后 fill_supervision 复核 + 基础规则检查。"""
    basic = _basic_fill_checks(record)
    if not basic.ok:
        return None, basic

    symbol = str(record.get("symbol", "")).strip()
    if not symbol:
        return None, NotifyCheckResult.fail("symbol 缺失")

    tf = infer_record_timeframe(record)
    csv_path = resolve_ohlcv_csv(data_dir, symbol, tf, market=market)
    if csv_path is None:
        return None, NotifyCheckResult.fail(f"缺少 {tf} K 线数据，无法完成成交自检")

    raw = apply_radar_ohlcv_tail(load_d1_csv(csv_path), tf)
    os_df, engine = build_os_detail_frame(raw, gap=gap)
    d1_os_df = None
    strategy = str(record.get("strategy_id", record.get("strategy", ""))).upper()
    if strategy == "DS07":
        d1_csv = resolve_ohlcv_csv(data_dir, symbol, "1d", market=market)
        if d1_csv is not None:
            raw_d1 = apply_radar_ohlcv_tail(load_d1_csv(d1_csv), "1d")
            d1_os_df, _ = build_os_detail_frame(raw_d1, gap=gap)
    audit = audit_fill_record(record, os_df, engine, d1_os_df=d1_os_df, market=market)

    if audit.verdict == "valid":
        return audit, NotifyCheckResult.pass_()
    if audit.verdict == "skipped":
        return audit, basic
    if audit.verdict == "invalid":
        return audit, NotifyCheckResult.fail(*audit.issues)
    return audit, NotifyCheckResult.fail(*audit.issues or ["needs-data"])


def validate_expected_close(position: dict[str, Any]) -> NotifyCheckResult:
    """预计平仓价 = 当前动态止损；须相对入场价方向正确。"""
    issues: list[str] = []
    entry = _safe_float(position.get("entry_price"))
    stop = _safe_float(position.get("current_stop")) or _safe_float(position.get("initial_stop"))
    side = int(position.get("side", 0) or 0)
    if entry is None or entry <= 0:
        issues.append("entry_price 无效")
    if stop is None or stop <= 0:
        issues.append("预计平仓价(止损) 无效")
    elif side == 1 and entry is not None and stop >= entry:
        issues.append("多头预计平仓价应低于入场价")
    elif side == -1 and entry is not None and stop <= entry:
        issues.append("空头预计平仓价应高于入场价")
    return NotifyCheckResult(ok=not issues, issues=issues)


def validate_close_fill(position: dict[str, Any], exit_price: float, exit_reason: str = "") -> NotifyCheckResult:
    issues: list[str] = []
    entry = _safe_float(position.get("entry_price"))
    stop = _safe_float(position.get("current_stop")) or _safe_float(position.get("initial_stop"))
    side = int(position.get("side", 0) or 0)
    exit_px = _safe_float(exit_price)
    if exit_px is None or exit_px <= 0:
        issues.append("平仓成交价无效")
    if entry is None or entry <= 0:
        issues.append("entry_price 无效")
    if stop is None or stop <= 0:
        issues.append("止损价缺失，无法核对平仓规则")
    elif side == 1 and exit_px is not None:
        if exit_reason == "gap_stop" and exit_px > stop:
            issues.append("多头 gap_stop 成交价应不高于止损")
        elif exit_reason != "gap_stop" and abs(exit_px - stop) > max(1e-6, abs(stop) * 0.002):
            issues.append("多头平仓价与止损价偏差过大")
    elif side == -1 and exit_px is not None:
        if exit_reason == "gap_stop" and exit_px < stop:
            issues.append("空头 gap_stop 成交价应不低于止损")
        elif exit_reason != "gap_stop" and abs(exit_px - stop) > max(1e-6, abs(stop) * 0.002):
            issues.append("空头平仓价与止损价偏差过大")
    return NotifyCheckResult(ok=not issues, issues=issues)


def _title_pending(side: str | int) -> str:
    return "预计挂单买入价格" if _side_is_long(side) else "预计挂单卖出价格"


def _title_fill(side: str | int) -> str:
    return "挂单买入价格已成交" if _side_is_long(side) else "挂单卖出价格已成交"


def _fill_status_text(side: str | int) -> str:
    return "已买入" if _side_is_long(side) else "已卖出"


def _close_status_text(side: str | int) -> str:
    return "已卖出平仓" if _side_is_long(side) else "已买入平仓"


def format_pending_expected(order: dict[str, Any], *, symbol_label: str, now: str) -> str:
    side = str(order.get("side", "")).lower()
    stop = _safe_float(order.get("stop_price"))
    stop_text = "无" if stop is None else f"{stop:.8g}"
    price_label = _title_pending(side)
    return (
        f"📋【已挂单 · {price_label}】\n"
        f"消息类型: 已挂单 + {price_label}\n"
        f"时间: {now}\n"
        f"品种: {symbol_label}\n"
        f"定式: {order.get('strategy_id', '')}\n"
        f"周期: {order.get('timeframe', '')}\n"
        "状态: 已挂单\n"
        f"方向: {_direction_text(side)}\n"
        f"{price_label}: {float(order.get('trigger_price', 0.0)):.8g}\n"
        f"预计初始止损: {stop_text}\n"
        f"现价: {float(order.get('current_price', 0.0)):.8g}\n"
        f"距触发: {float(order.get('distance_pct', 0.0)) * 100:.2f}%\n"
        f"峰极阵营: {format_camp_with_timeframe(order)}\n"
        f"依据: {order.get('setup', '')}\n"
        f"有效期至: {order.get('valid_until', '')}\n"
        "自检: 通过（触发价/止损几何/状态）\n"
        "模式: 只模拟挂单，不真实下单"
    )


def format_fill_done(
    order: dict[str, Any],
    fill_price: float,
    *,
    symbol_label: str,
    now: str,
    audit: FillAuditResult | None = None,
    extra_lines: list[str] | None = None,
    position: dict[str, Any] | None = None,
) -> str:
    side = str(order.get("side", "")).lower()
    stop = _safe_float(order.get("stop_price"))
    stop_text = "无" if stop is None else f"{stop:.8g}"
    pending_label = _title_pending(side)
    fill_label = _title_fill(side)
    audit_line = "自检: 通过（成交规则复核 valid）"
    if audit is not None:
        if audit.verdict == "skipped":
            audit_line = f"自检: 通过（{audit.strategy_id} 基础规则；监督项 skipped）"
        elif audit.verdict == "valid":
            audit_line = "自检: 通过（fill_supervision valid）"
    fill_status = _fill_status_text(side)
    title = f"🟢【{fill_status} · {fill_label} · 含预计平仓】" if position is not None else f"🟢【{fill_status} · {fill_label}】"
    msg_type = f"消息类型: {fill_status} + {fill_label} + 预计挂单平仓价格" if position is not None else f"消息类型: {fill_status} + {fill_label}"
    lines = [
        title,
        msg_type,
        f"时间: {now}",
        f"品种: {symbol_label}",
        f"定式: {order.get('strategy_id', '')}",
        f"周期: {order.get('timeframe', '')}",
        f"状态: {fill_status}",
        f"方向: {_direction_text(side)}",
        f"{pending_label}: {float(order.get('trigger_price', 0.0)):.8g}",
        f"{fill_label}: {fill_price:.8g}",
        f"初始止损: {stop_text}",
        f"峰极阵营: {format_camp_with_timeframe(order)}",
        f"依据: {order.get('setup', '')}",
        audit_line,
        "模式: 只模拟触发，不真实下单",
    ]
    if extra_lines:
        insert_at = next(i for i, line in enumerate(lines) if line.startswith(f"{fill_label}:"))
        lines[insert_at:insert_at] = extra_lines
    if position is not None:
        exp_stop = _safe_float(position.get("current_stop")) or _safe_float(position.get("initial_stop"))
        exp_stop_text = "无" if exp_stop is None else f"{exp_stop:.8g}"
        insert_at = next(i for i, line in enumerate(lines) if line.startswith("初始止损:")) + 1
        lines[insert_at:insert_at] = [
            f"预计挂单平仓价格: {exp_stop_text}",
            "说明: 以上为当前动态止损价，持仓期间会随 OS 更新",
        ]
        if audit is not None and audit.verdict == "skipped":
            lines[-2] = f"自检: 通过（{audit.strategy_id} 基础规则 + 预计平仓价方向；监督项 skipped）"
        elif audit is not None and audit.verdict == "valid":
            lines[-2] = "自检: 通过（fill_supervision valid + 预计平仓价方向）"
        else:
            lines[-2] = "自检: 通过（成交规则 + 预计平仓价方向）"
    return "\n".join(lines) + "\n"


def format_close_expected(
    position: dict[str, Any],
    *,
    symbol_label: str,
    now: str,
) -> str:
    side = int(position.get("side", 0) or 0)
    stop = _safe_float(position.get("current_stop")) or _safe_float(position.get("initial_stop"))
    stop_text = "无" if stop is None else f"{stop:.8g}"
    return (
        "📌【预计挂单平仓价格】\n"
        "消息类型: 预计挂单平仓价格\n"
        f"时间: {now}\n"
        f"品种: {symbol_label}\n"
        f"定式: {position.get('strategy_id', '')}\n"
        f"方向: {_position_side_text(side)}\n"
        f"入场时间: {position.get('entry_time', '')}\n"
        f"入场价格: {float(position.get('entry_price', 0.0) or 0.0):.8g}\n"
        f"预计挂单平仓价格: {stop_text}\n"
        "说明: 以上为当前动态止损价，持仓期间会随 OS 更新\n"
        "自检: 通过（止损相对入场价方向正确）\n"
        "模式: 只模拟触发，不真实下单"
    )


def format_close_done(
    position: dict[str, Any],
    exit_price: float,
    pnl: dict[str, Any],
    *,
    symbol_label: str,
    now: str,
    exit_reason: str = "stop",
    bar_hint: str = "",
) -> str:
    net = float(pnl.get("net_pnl", 0.0))
    result = "盈利" if net >= 0 else "亏损"
    unit = str(pnl.get("unit", "USDT"))
    side = int(position.get("side", 0) or 0)
    close_status = _close_status_text(side)
    lines = [
        f"✅【{close_status} · 平仓价格已成交】",
        f"消息类型: {close_status} + 平仓价格已成交",
        f"时间: {now}",
        f"品种: {symbol_label}",
        f"定式: {position.get('strategy_id', '')}",
        f"状态: {close_status}",
        f"方向: {_position_side_text(side)}",
        f"入场时间: {position.get('entry_time', '')}",
        f"入场价格: {float(position.get('entry_price', 0.0) or 0.0):.8g}",
        f"预计挂单平仓价格: {(_safe_float(position.get('current_stop')) or _safe_float(position.get('initial_stop')) or 0.0):.8g}",
        f"平仓价格已成交: {exit_price:.8g}",
        f"结果: {result} {net:.2f} {unit}",
        f"退出原因: {exit_reason}",
    ]
    if bar_hint:
        lines.append(f"触发K线: {bar_hint}")
    lines.extend(["自检: 通过（平仓价与止损规则一致）", "模式: 只模拟触发，不真实下单"])
    return "\n".join(lines) + "\n"


def log_notify_blocked(event: str, order_id: str, check: NotifyCheckResult, *, logger: Callable[[str], None] | None = None) -> None:
    text = f"[feishu_notify_blocked] event={event} order_id={order_id} issues={'; '.join(check.issues)}"
    if logger:
        logger(text)
    else:
        print(text)
