"""只读 ledger 拒单明细：聚合 radar 阻断行与 pending_orders 非活跃状态（不改挂单/OS）。"""
from __future__ import annotations

import csv
import os
from datetime import datetime
from pathlib import Path
from typing import Any

from radar_snapshot import infer_radar_market, load_latest_radar

ROOT = Path(__file__).resolve().parents[1]

PENDING_ORDER_PATHS = (
    Path(os.getenv("DOMESTIC_PENDING_ORDERS_PATH", "")).expanduser()
    if os.getenv("DOMESTIC_PENDING_ORDERS_PATH", "").strip()
    else None,
    ROOT / "runtime" / "fengji_pending_orders" / "pending_orders.csv",
    ROOT / "runtime" / "remote_domestic_pending" / "pending_orders.csv",
)

PENDING_ACTIVE_STATUSES = {"ACTIVE", "READY_TRIGGERED", "TRIGGERED"}

RADAR_REJECT_PREFIXES = ("BLOCKED_",)
RADAR_REJECT_STATUSES = {
    "EXPIRED",
    "CANCELLED",
    "REJECTED",
    "AUDIT_INVALID",
    "INVALID",
}

PENDING_REJECT_STATUSES = {
    "CANCELLED",
    "REJECTED",
    "EXPIRED",
    "BLOCKED",
    "AUDIT_INVALID",
    "INVALID",
}


def _parse_time(value: str) -> datetime:
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%Y/%m/%d %H:%M:%S"):
        try:
            return datetime.strptime(str(value or "").strip()[:19], fmt)
        except ValueError:
            continue
    return datetime.min


def _pending_order_candidates() -> list[Path]:
    seen: set[Path] = set()
    out: list[Path] = []
    for path in PENDING_ORDER_PATHS:
        if path is not None and path.is_file() and path not in seen:
            seen.add(path)
            out.append(path)
    runtime = ROOT / "runtime"
    if runtime.is_dir():
        discovered = [
            path for path in runtime.rglob("pending_orders.csv")
            if path.is_file() and path not in seen and "backup" not in path.parts
        ]
        discovered.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        out.extend(discovered[:8])
    return out


def _is_radar_rejection(status: str) -> bool:
    key = str(status or "").strip().upper()
    if not key:
        return False
    if key in RADAR_REJECT_STATUSES:
        return True
    return any(key.startswith(prefix) for prefix in RADAR_REJECT_PREFIXES)


def _is_pending_rejection(status: str) -> bool:
    key = str(status or "").strip().upper()
    if not key:
        return False
    if key in PENDING_REJECT_STATUSES:
        return True
    return any(key.startswith(prefix) for prefix in RADAR_REJECT_PREFIXES)


def _normalize_ledger_item(
    *,
    source: str,
    source_path: str | None,
    symbol: str,
    strategy_id: str,
    status: str,
    reason: str,
    side: str = "",
    timeframe: str = "",
    event_time: str = "",
    market: str | None = None,
    order_id: str = "",
) -> dict[str, Any]:
    sym = str(symbol or "").strip().upper()
    mkt = str(market or infer_radar_market(sym)).strip().upper()
    return {
        "source": source,
        "source_path": source_path,
        "symbol": sym,
        "market": mkt,
        "strategy_id": str(strategy_id or "").strip().upper(),
        "timeframe": str(timeframe or "").strip(),
        "side": str(side or "").strip().lower(),
        "status": str(status or "").strip().upper(),
        "reason": str(reason or "").strip(),
        "event_time": str(event_time or "").strip(),
        "order_id": str(order_id or "").strip(),
        "kind": "radar_blocked" if source == "radar_csv" else "pending_rejected",
    }


def _rows_from_radar(limit: int) -> tuple[list[dict[str, Any]], str | None, str | None]:
    payload = load_latest_radar(limit=max(limit, 80))
    source_path = payload.get("source_path")
    source = str(payload.get("source") or "empty")
    items: list[dict[str, Any]] = []
    for row in payload.get("rows") or []:
        status = str(row.get("status") or "").upper()
        if not _is_radar_rejection(status):
            continue
        items.append(
            _normalize_ledger_item(
                source="radar_csv",
                source_path=str(source_path) if source_path else None,
                symbol=str(row.get("symbol") or ""),
                strategy_id=str(row.get("strategy_id") or ""),
                status=status,
                reason=str(row.get("reason") or status),
                side=str(row.get("side") or ""),
                timeframe=str(row.get("timeframe") or ""),
                event_time=str(row.get("latest_time") or ""),
                market=str(row.get("market") or ""),
            )
        )
    return items, source, str(source_path) if source_path else None


def _rows_from_pending(limit: int) -> tuple[list[dict[str, Any]], list[str]]:
    items: list[dict[str, Any]] = []
    paths_used: list[str] = []
    for path in _pending_order_candidates():
        try:
            with path.open("r", newline="", encoding="utf-8-sig") as fh:
                rows = list(csv.DictReader(fh))
        except Exception:
            continue
        paths_used.append(str(path))
        for row in rows:
            status = str(row.get("status") or row.get("radar_status") or "").upper()
            if status in PENDING_ACTIVE_STATUSES or not _is_pending_rejection(status):
                continue
            reason = str(row.get("reason") or row.get("setup") or status).strip()
            items.append(
                _normalize_ledger_item(
                    source="pending_orders_csv",
                    source_path=str(path),
                    symbol=str(row.get("symbol") or ""),
                    strategy_id=str(row.get("strategy_id") or ""),
                    status=status,
                    reason=reason,
                    side=str(row.get("side") or ""),
                    timeframe=str(row.get("timeframe") or ""),
                    event_time=str(row.get("latest_time") or row.get("created_at") or ""),
                    order_id=str(row.get("order_id") or ""),
                )
            )
        if len(items) >= limit:
            break
    return items[:limit], paths_used


def load_recent_ledger_rejections(*, limit: int = 50) -> dict[str, Any]:
    """读取最近拒单/阻断明细，只读展示。"""
    limit = max(1, min(int(limit), 200))
    radar_items, radar_source, radar_path = _rows_from_radar(limit)
    pending_items, pending_paths = _rows_from_pending(limit)

    merged = radar_items + pending_items
    merged.sort(
        key=lambda item: (
            _parse_time(str(item.get("event_time") or "")),
            str(item.get("symbol") or ""),
            str(item.get("strategy_id") or ""),
        ),
        reverse=True,
    )
    items = merged[:limit]

    return {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "mode": "read_only_ledger",
        "disclaimer": "拒单明细来自 radar/pending 只读快照，不修改 OS/定式/挂单",
        "sources": {
            "radar": radar_source,
            "radar_path": radar_path,
            "pending_paths": pending_paths[:4],
        },
        "count": len(items),
        "items": items,
    }
