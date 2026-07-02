#!/usr/bin/env python3
"""Export FastAPI OpenAPI schema to docs/api/openapi.json (Plan B B0-1)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SERVICES = ROOT / "services"
sys.path.insert(0, str(SERVICES))
sys.path.insert(0, str(ROOT / "packages" / "fengji_core"))


def main() -> int:
    out = ROOT / "docs" / "api" / "openapi.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    from api.main import app  # noqa: WPS433

    schema = app.openapi()
    out.write_text(json.dumps(schema, ensure_ascii=False, indent=2), encoding="utf-8")
    paths = len(schema.get("paths") or {})
    print(f"openapi paths={paths} -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
