from __future__ import annotations

import os
from pathlib import Path


def resolve_feishu_webhook(project_root: Path | None = None) -> str:
    """Read Feishu webhook from env or runtime/feishu_webhook.env (never commit the file)."""
    for key in ("FENGJI_FEISHU_WEBHOOK", "FEISHU_WEBHOOK"):
        value = os.getenv(key, "").strip()
        if value:
            return value

    root = project_root or Path.cwd()
    env_path = root / "runtime" / "feishu_webhook.env"
    if not env_path.exists():
        return ""

    for raw in env_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        if key.strip() in {"FEISHU_WEBHOOK", "FENGJI_FEISHU_WEBHOOK"}:
            return value.strip().strip('"').strip("'")
    return ""
