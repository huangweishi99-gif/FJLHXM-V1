from __future__ import annotations

from fengji_total_radar import RadarRow

from watch_ds09_live_radar_sandbox import pick_new_rows, row_fingerprint


def _row(**kwargs) -> RadarRow:
    base = dict(
        symbol="BNBUSDT",
        strategy_id="DS09",
        timeframe="M15",
        side="long",
        status="NEAR",
        setup="test",
        current_price=600.0,
        trigger_price=610.0,
        distance_pct=0.01,
        stop_price=590.0,
        os_camp="D1=RED,M15=RED",
        latest_time="2026-06-12",
        score=0.5,
        reason="unit",
        setup_key="",
    )
    base.update(kwargs)
    return RadarRow(**base)


def test_row_fingerprint_prefers_setup_key() -> None:
    row = _row(setup_key="BNBUSDT|DS09|LONG|2026-06-12")
    assert row_fingerprint(row) == "BNBUSDT|DS09|BNBUSDT|DS09|LONG|2026-06-12"


def test_pick_new_rows_skips_seen() -> None:
    row = _row(setup_key="k1")
    fp = row_fingerprint(row)
    seen = {fp}
    assert pick_new_rows([row], seen) == []


def test_pick_new_rows_returns_unseen() -> None:
    row = _row(setup_key="k2")
    fp = row_fingerprint(row)
    found = pick_new_rows([row], set())
    assert found == [(fp, row)]
