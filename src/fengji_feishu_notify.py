"""飞书通知去重：同一开仓/平仓事件只推送一次（多进程/多轮询安全）。"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
from typing import Callable


def fill_notify_key(order_id: str) -> str:
    return f"fill|{str(order_id).strip()}"


def pending_notify_key(order_id: str) -> str:
    return f"pending|{str(order_id).strip()}"


def pending_setup_notify_key(setup_key: str) -> str:
    """Semantic dedup for radar-refreshed orders that keep the same structure but new order_id."""
    return f"pending_setup|{str(setup_key).strip()}"


def _pending_side_token(side: object) -> str:
    text = str(side or "").strip().lower()
    if text in {"1", "long"}:
        return "long"
    if text in {"-1", "short"}:
        return "short"
    return text


def _pending_price_token(value: object) -> str:
    if value is None or value == "":
        return ""
    return f"{float(value):.10g}"


def pending_semantic_notify_key(order: dict) -> str:
    """Stable dedup across order_id / setup_key churn when structure and prices are unchanged."""
    symbol = str(order.get("symbol", "")).strip().upper()
    strategy = str(order.get("strategy_id", "")).strip().upper()
    timeframe = str(order.get("timeframe", "")).strip().upper()
    side = _pending_side_token(order.get("side"))
    trigger = _pending_price_token(order.get("trigger_price"))
    stop = _pending_price_token(order.get("stop_price"))
    return f"pending_semantic|{symbol}|{strategy}|{timeframe}|{side}|{trigger}|{stop}"


def expected_close_notify_key(order_id: str) -> str:
    return f"expected_close|{str(order_id).strip()}"


def close_notify_key(symbol: str, order_id: str, entry_time: str, strategy_id: str = "") -> str:
    return (
        f"close|{str(symbol).strip().upper()}|{str(strategy_id).strip().upper()}|"
        f"{str(order_id).strip()}|{str(entry_time).strip()}"
    )


def paper_trade_notify_key(event: str, trade_key: str) -> str:
    return f"paper|{event}|{str(trade_key).strip()}"


def system_notify_key(scope: str, event: str) -> str:
    return f"system|{str(scope).strip()}|{str(event).strip()}"


def default_feishu_claims_dir(project_root: Path | None = None) -> Path:
    """与挂单监控共用 runtime/feishu_notify_claims，跨进程统一去重。"""
    root = project_root if project_root is not None else Path.cwd()
    return (root / "runtime" / "feishu_notify_claims").resolve()


def _claim_file(claims_dir: Path, event_key: str) -> Path:
    digest = hashlib.sha256(event_key.encode("utf-8")).hexdigest()
    return claims_dir / f"{digest}.claim"


def should_send_feishu(claims_dir: Path, event_key: str) -> bool:
    """跨进程原子占位：仅第一个成功创建 claim 文件的调用方应发送。"""
    claims_dir.mkdir(parents=True, exist_ok=True)
    path = _claim_file(claims_dir, event_key)
    flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY
    try:
        fd = os.open(str(path), flags)
    except FileExistsError:
        return False
    try:
        os.write(fd, event_key.encode("utf-8"))
    finally:
        os.close(fd)
    return True


def send_feishu_once(
    claims_dir: Path,
    event_key: str,
    webhook: str,
    text: str,
    send_msg: Callable[[str, str], None],
) -> bool:
    if not should_send_feishu(claims_dir, event_key):
        return False
    send_msg(webhook, text)
    return True
