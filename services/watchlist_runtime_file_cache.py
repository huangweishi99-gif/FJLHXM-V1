from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RUNTIME_CACHE_DIR = ROOT / "runtime" / "watchlist_runtime_cache"


def _safe_user_id(user_id: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", user_id.strip())
    return safe[:80] or "anonymous"


def runtime_cache_path(user_id: str, cache_dir: Path | None = None) -> Path:
    base = cache_dir or Path(os.getenv("FENGJI_WATCHLIST_RUNTIME_CACHE_DIR", DEFAULT_RUNTIME_CACHE_DIR))
    return base / f"{_safe_user_id(user_id)}.json"


def load_watchlist_runtime_cache(user_id: str, cache_dir: Path | None = None) -> dict[str, Any] | None:
    path = runtime_cache_path(user_id, cache_dir)
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    payload["_cache_file"] = str(path)
    return payload


def runtime_cache_age_seconds(payload: dict[str, Any], now: datetime | None = None) -> float | None:
    raw = payload.get("generated_at")
    if not raw:
        return None
    try:
        generated = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except ValueError:
        return None
    if generated.tzinfo is None:
        generated = generated.replace(tzinfo=timezone.utc)
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    return max((current.astimezone(timezone.utc) - generated.astimezone(timezone.utc)).total_seconds(), 0.0)


def save_watchlist_runtime_cache(
    user_id: str,
    payload: dict[str, Any],
    cache_dir: Path | None = None,
) -> Path:
    path = runtime_cache_path(user_id, cache_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)
    return path
