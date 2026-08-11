from __future__ import annotations

from pathlib import Path

import pytest

from chart_bundle import ChartBundleRequest, build_chart_bundle
from fengji_core.chart_line import audit_hardened_segments, audit_web_vs_sandbox, build_hardened_segments


def test_audit_rejects_high_high_solid_chain() -> None:
    segments = [
        {"t0": "2026-04-30", "p0": 694.9, "t1": "2026-05-08", "p1": 609.1, "type": "HIGH", "style": "solid"},
        {"t0": "2026-05-08", "p0": 609.1, "t1": "2026-05-20", "p1": 691.4, "type": "HIGH", "style": "solid"},
    ]
    issues = audit_hardened_segments(
        segments,
        {"2026-04-30", "2026-05-08", "2026-05-20", "2026-06-03"},
        require_trail=False,
    )
    assert any(i.code == "SOLID_TYPE_REPEAT" for i in issues)


def test_audit_accepts_valid_trail() -> None:
    segments = [
        {"t0": "2026-04-30", "p0": 694.9, "t1": "2026-05-08", "p1": 609.1, "type": "HIGH", "style": "solid"},
        {"t0": "2026-05-08", "p0": 609.1, "t1": "2026-05-20", "p1": 691.4, "type": "LOW", "style": "solid"},
        {
            "t0": "2026-05-20",
            "p0": 691.4,
            "t1": "2026-06-03",
            "p1": 594.6,
            "type": "trail",
            "style": "dashed",
            "kind": "provisional",
        },
    ]
    issues = audit_hardened_segments(
        segments,
        {"2026-04-30", "2026-05-08", "2026-05-20", "2026-06-03"},
        require_trail=True,
        last_bar_date="2026-06-03",
    )
    assert not issues


@pytest.mark.parametrize("symbol,csv_name", [("SC", "原油.csv"), ("NI", "沪镍.csv")])
def test_domestic_futures_chart_lines_pass_audit(symbol: str, csv_name: str) -> None:
    root = Path(__file__).resolve().parents[1]
    csv = root / "data" / "futures" / "1d" / csv_name
    if not csv.exists():
        pytest.skip(f"{csv_name} not available")
    state_dir = root / "runtime" / "fengji_os_state"
    bundle = build_chart_bundle(
        ChartBundleRequest(
            csv_path=csv,
            strategy_id="DS03",
            years=2,
            futures_mode=True,
            os_state_dir=state_dir,
            os_symbol=symbol,
            os_timeframe="1d",
        )
    )
    bars = bundle["bars"]
    segs = bundle["hardened_segments"]
    bar_dates = {b["t"] for b in bars}
    issues = audit_hardened_segments(segs, bar_dates, require_trail=True, last_bar_date=bars[-1]["t"])
    assert not issues, [f"{i.code}: {i.message}" for i in issues]


def test_build_hardened_segments_exported_from_chart_line() -> None:
    assert callable(build_hardened_segments)
