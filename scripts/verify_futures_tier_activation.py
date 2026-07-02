"""Read-only verify FUTURES tier activation on server (PG + calibration JSON)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for rel in ("services", "packages/fengji_core", "src"):
    p = str(ROOT / rel)
    if p not in sys.path:
        sys.path.insert(0, p)

from fengji_core.context_stats import bucket_profile_for_market  # noqa: E402
from sqlalchemy import select  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from db.models import ContextBucketStat  # noqa: E402
from db.session import get_engine  # noqa: E402


def main() -> int:
    cal_path = ROOT / "data" / "context_market_calibration.json"
    cal = json.loads(cal_path.read_text(encoding="utf-8"))
    fut = cal.get("markets", {}).get("FUTURES", {})
    profile = bucket_profile_for_market("FUTURES")

    with Session(get_engine()) as session:
        rows = session.scalars(select(ContextBucketStat).where(ContextBucketStat.market == "FUTURES")).all()

    eligible = [r for r in rows if int(r.count or 0) >= 30 and r.signal_score is not None]
    tiers: dict[str, int] = {}
    for row in rows:
        key = str(row.signal_tier or "UNKNOWN")
        tiers[key] = tiers.get(key, 0) + 1

    medium = fut.get("tier_medium")
    strong = fut.get("tier_strong")
    ok = (
        profile.name == "futures_v2"
        and abs(float(medium) - 0.443491) < 1e-5
        and abs(float(strong) - 0.70411) < 1e-5
        and len(eligible) >= 30
    )

    payload = {
        "status": "OK" if ok else "FAIL",
        "calibration_medium": medium,
        "calibration_strong": strong,
        "bucket_profile": profile.name,
        "buckets": len(rows),
        "eligible_buckets": len(eligible),
        "tiers": tiers,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
