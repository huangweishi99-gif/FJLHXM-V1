"""飞书通知去重：同一开仓/平仓事件只推送一次（多进程/多轮询安全）。"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
from typing import Callable


def fill_notify_key(order_id: str) -> str:
    return f"fill|{str(order_id).strip()}"


def close_notify_key(symbol: str, order_id: str, entry_time: str, strategy_id: str = "") -> str:
    return (
        f"close|{str(symbol).strip().upper()}|{str(strategy_id).strip().upper()}|"
        f"{str(order_id).strip()}|{str(entry_time).strip()}"
    )


def paper_trade_notify_key(event: str, trade_key: str) -> str:
    return f"paper|{event}|{str(trade_key).strip()}"


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
