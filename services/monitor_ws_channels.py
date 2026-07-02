"""W16-WS phase 3: monitor websocket channel fingerprints and delta payloads."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Any

MONITOR_CHANNEL_ALL = frozenset({"positions", "runtime", "quotes"})


def parse_monitor_channels(raw: str | None) -> frozenset[str]:
    if not raw or not str(raw).strip():
        return MONITOR_CHANNEL_ALL
    picked = {part.strip().lower() for part in str(raw).split(",") if part.strip()}
    valid = picked & MONITOR_CHANNEL_ALL
    return frozenset(valid) if valid else MONITOR_CHANNEL_ALL


def filter_snapshot_payload(payload: dict[str, Any], channels: frozenset[str]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    if "positions" in channels:
        out["positions"] = list(payload.get("positions") or [])
    if "runtime" in channels:
        out["runtime"] = dict(payload.get("runtime") or {})
    if "quotes" in channels:
        out["quotes"] = list(payload.get("quotes") or [])
    return out


def channel_fingerprints(payload: dict[str, Any], channels: frozenset[str]) -> dict[str, str]:
    fps: dict[str, str] = {}
    for channel in sorted(channels):
        part = payload.get(channel)
        blob = json.dumps(part, sort_keys=True, ensure_ascii=False, default=str)
        fps[channel] = hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]
    return fps


def diff_changed_channels(
    previous: dict[str, str] | None,
    current: dict[str, str],
) -> list[str]:
    if not previous:
        return list(current.keys())
    return [name for name, fp in current.items() if previous.get(name) != fp]


def build_delta_message(
    *,
    snapshot: dict[str, Any],
    changed: list[str],
    channels: frozenset[str],
) -> dict[str, Any]:
    full_payload = dict(snapshot.get("payload") or {})
    delta_payload = {name: full_payload[name] for name in changed if name in full_payload and name in channels}
    return {
        "type": "monitor.delta.v1",
        "version": 1,
        "seq": snapshot.get("seq"),
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "mode": snapshot.get("mode", "read_only_monitor"),
        "user_id": snapshot.get("user_id"),
        "plan": snapshot.get("plan"),
        "channels": sorted(channels),
        "changed": changed,
        "payload": delta_payload,
        "status": dict(snapshot.get("status") or {}),
    }
