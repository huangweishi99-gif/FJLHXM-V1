"""W16-WS phase 2: monitor websocket metrics and audit logging (read-only, no secrets)."""
from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime
from pathlib import Path
from threading import Lock
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_AUDIT_LOG = ROOT / "runtime" / "logs" / "monitor_ws_audit.jsonl"
_RING_MAX = 50

_lock = Lock()
_lifetime_connects = 0
_lifetime_disconnects = 0
_lifetime_auth_rejects = 0
_lifetime_limit_rejects = 0
_lifetime_snapshots_sent = 0
_lifetime_heartbeats_sent = 0
_lifetime_deltas_sent = 0
_recent_events: list[dict[str, Any]] = []


def audit_log_path() -> Path:
    custom = str(os.getenv("MONITOR_WS_AUDIT_LOG", "")).strip()
    return Path(custom) if custom else DEFAULT_AUDIT_LOG


def _append_audit(entry: dict[str, Any]) -> None:
    path = audit_log_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, ensure_ascii=False, default=str) + "\n")


def _push_recent(entry: dict[str, Any]) -> None:
    _recent_events.append(entry)
    if len(_recent_events) > _RING_MAX:
        del _recent_events[: len(_recent_events) - _RING_MAX]


def record_event(event: str, **fields: Any) -> None:
    global _lifetime_connects, _lifetime_disconnects, _lifetime_auth_rejects
    global _lifetime_limit_rejects, _lifetime_snapshots_sent, _lifetime_heartbeats_sent, _lifetime_deltas_sent

    entry = {
        "ts": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "event": event,
        **{k: v for k, v in fields.items() if v is not None and k not in {"password", "token", "secret"}},
    }
    with _lock:
        if event == "connected":
            _lifetime_connects += 1
        elif event == "disconnected":
            _lifetime_disconnects += 1
        elif event == "auth_rejected":
            _lifetime_auth_rejects += 1
        elif event == "limit_exceeded":
            _lifetime_limit_rejects += 1
        elif event == "snapshot_sent":
            _lifetime_snapshots_sent += 1
        elif event == "heartbeat_sent":
            _lifetime_heartbeats_sent += 1
        elif event == "delta_sent":
            _lifetime_deltas_sent += 1
        _push_recent(entry)
    try:
        _append_audit(entry)
    except OSError:
        pass


def snapshot_payload_fingerprint(snapshot: dict[str, Any]) -> str:
    payload = snapshot.get("payload")
    blob = json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]


def build_heartbeat_message(
    *,
    user_id: str,
    plan: str,
    seq: int,
    since_last_change_seconds: float,
) -> dict[str, Any]:
    return {
        "type": "monitor.heartbeat.v1",
        "version": 1,
        "seq": seq,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "mode": "read_only_monitor",
        "user_id": user_id,
        "plan": plan,
        "status": {"ok": True, "fallback_polling_allowed": True},
        "since_last_change_seconds": round(max(0.0, since_last_change_seconds), 3),
    }


def get_stats(active_connections: dict[str, int], *, max_per_user: int) -> dict[str, Any]:
    with _lock:
        lifetime = {
            "connects": _lifetime_connects,
            "disconnects": _lifetime_disconnects,
            "auth_rejects": _lifetime_auth_rejects,
            "limit_rejects": _lifetime_limit_rejects,
            "snapshots_sent": _lifetime_snapshots_sent,
            "heartbeats_sent": _lifetime_heartbeats_sent,
            "deltas_sent": _lifetime_deltas_sent,
        }
        recent = list(_recent_events[-10:])
    active_total = sum(int(v) for v in active_connections.values())
    return {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "active_connections_by_user": dict(active_connections),
        "active_total": active_total,
        "max_connections_per_user": max_per_user,
        "lifetime": lifetime,
        "recent_events": recent,
        "audit_log": str(audit_log_path()),
    }


def reset_stats_for_tests() -> None:
    global _lifetime_connects, _lifetime_disconnects, _lifetime_auth_rejects
    global _lifetime_limit_rejects, _lifetime_snapshots_sent, _lifetime_heartbeats_sent, _lifetime_deltas_sent
    with _lock:
        _lifetime_connects = 0
        _lifetime_disconnects = 0
        _lifetime_auth_rejects = 0
        _lifetime_limit_rejects = 0
        _lifetime_snapshots_sent = 0
        _lifetime_heartbeats_sent = 0
        _lifetime_deltas_sent = 0
        _recent_events.clear()
