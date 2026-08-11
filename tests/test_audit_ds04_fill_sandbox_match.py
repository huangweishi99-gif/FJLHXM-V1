from __future__ import annotations

from scripts.audit_ds04_fill_sandbox_match import parse_setup_dates


def test_parse_setup_dates_from_ds04_setup_key() -> None:
    dates = parse_setup_dates(
        "SHUSDT|DS04|LONG|k1=20260705160000|k2=20260706160000|k3=20260707160000|k4=20260708160000|trigger=1938"
    )

    assert dates == {
        "k1": "2026-07-05 16:00:00",
        "k2": "2026-07-06 16:00:00",
        "k3": "2026-07-07 16:00:00",
        "k4": "2026-07-08 16:00:00",
    }
