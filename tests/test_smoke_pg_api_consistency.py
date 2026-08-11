from __future__ import annotations

from scripts.smoke_pg_api_consistency import DEFAULT_SAMPLE_PLAN, parse_sample_plan


def test_default_pg_api_smoke_samples_futures() -> None:
    plan = dict(parse_sample_plan(DEFAULT_SAMPLE_PLAN))
    assert plan == {
        "A_STOCK": 4,
        "CRYPTO": 3,
        "FUTURES": 3,
        "US_STOCK": 3,
    }
