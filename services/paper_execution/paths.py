"""Per-user paper execution filesystem layout (JSON, Phase 1 CRYPTO)."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
PAPER_USERS_ROOT = ROOT / "runtime" / "paper_users"
PHASE1_MARKET = "CRYPTO"


def safe_user_id(user_id: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(user_id or "").strip())
    return safe[:80] or "anonymous"


@dataclass(frozen=True)
class UserPaperPaths:
    user_id: str
    market: str = PHASE1_MARKET
    root_dir: Path = field(default_factory=lambda: PAPER_USERS_ROOT)

    @property
    def safe_id(self) -> str:
        return safe_user_id(self.user_id)

    @property
    def base_dir(self) -> Path:
        return self.root_dir / self.safe_id / self.market.lower()

    @property
    def radar_dir(self) -> Path:
        return self.base_dir / "radar"

    @property
    def pending_dir(self) -> Path:
        return self.base_dir / "pending"

    @property
    def radar_json(self) -> Path:
        return self.radar_dir / "radar.json"

    @property
    def pending_orders_json(self) -> Path:
        return self.pending_dir / "pending_orders.json"

    @property
    def monitor_state_json(self) -> Path:
        return self.pending_dir / "state.json"

    @property
    def paper_state_json(self) -> Path:
        return self.base_dir / "paper_state.json"

    @property
    def events_jsonl(self) -> Path:
        return self.base_dir / "events.jsonl"

    @property
    def meta_json(self) -> Path:
        return self.base_dir / "meta.json"

    def ensure_dirs(self) -> None:
        self.radar_dir.mkdir(parents=True, exist_ok=True)
        self.pending_dir.mkdir(parents=True, exist_ok=True)

    def touch_meta(self, *, plan_id: str, symbols: list[str]) -> dict[str, Any]:
        self.ensure_dirs()
        now = datetime.now(timezone.utc).isoformat()
        payload: dict[str, Any] = {
            "user_id": self.user_id,
            "safe_user_id": self.safe_id,
            "market": self.market,
            "plan_id": plan_id,
            "execution_mode": "per_user_execution_v1_2",
            "storage": "json",
            "symbols": symbols,
            "updated_at": now,
        }
        if self.meta_json.is_file():
            try:
                existing = json.loads(self.meta_json.read_text(encoding="utf-8"))
                if isinstance(existing, dict):
                    payload["created_at"] = existing.get("created_at") or now
            except Exception:
                payload["created_at"] = now
        else:
            payload["created_at"] = now
        self.meta_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return payload

    def is_outside_shared_runtime(self, path: Path) -> bool:
        """True when path is under this user's tree, not shared paper_state."""
        try:
            path.resolve().relative_to(self.base_dir.resolve())
            return True
        except ValueError:
            return False
