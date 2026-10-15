"""行为测试：fengji_core.sector_exposure（板块敞口上限，默认关闭）。"""
from __future__ import annotations

from fengji_core.sector_exposure import (
    UNKNOWN_SECTOR,
    sector_exposure,
    sector_of,
    would_breach_sector_limit,
)


def _state(symbol: str, opens: int) -> dict:
    return {
        "symbols": {
            symbol: {
                "open_positions": [{"closed": False} for _ in range(opens)],
            }
        }
    }


def test_sector_of_maps_symbols() -> None:
    assert sector_of("RB") == "BLACK"
    assert sector_of("RB2601") == "BLACK"
    assert sector_of("rb2601.SHFE") == "BLACK"
    assert sector_of("MA") == "ENERGY_CHEM"
    assert sector_of("AU") == "PRECIOUS"
    assert sector_of("XYZ") == UNKNOWN_SECTOR
    assert sector_of("") == UNKNOWN_SECTOR


def test_sector_exposure_counts_open_positions() -> None:
    state = {
        "symbols": {
            "RB2601": {"open_positions": [{"closed": False}, {"closed": False}, {"closed": True}]},
            "JM2601": {"open_positions": [{"closed": False}]},
            "AU2612": {"open_positions": []},
        }
    }
    counts = sector_exposure(state)
    assert counts["BLACK"] == 3  # RB 2 + JM 1
    assert "PRECIOUS" not in counts  # 无未平仓不计入


def test_limit_disabled_by_default() -> None:
    """回归契约：上限为 0（默认）时不拦截任何开仓。"""
    state = _state("RB2601", 10)
    assert would_breach_sector_limit(state, "JM2601", max_positions=0) is None


def test_limit_blocks_when_sector_full() -> None:
    state = _state("RB2601", 3)
    assert would_breach_sector_limit(state, "JM2601", max_positions=3) == "BLACK"
    assert would_breach_sector_limit(state, "JM2601", max_positions=5) is None


def test_limit_counts_planned_fills_same_round() -> None:
    """同一轮里已计划成交的品种也要计入，否则一轮就能突破上限。"""
    state = _state("RB2601", 2)
    assert would_breach_sector_limit(state, "JM2601", max_positions=3, planned=[]) is None
    assert would_breach_sector_limit(state, "JM2601", max_positions=3, planned=["SF2601"]) == "BLACK"


def test_unknown_sector_never_blocked() -> None:
    state = _state("RB2601", 5)
    assert would_breach_sector_limit(state, "XYZ999", max_positions=1) is None


def test_other_sectors_unaffected() -> None:
    state = _state("RB2601", 5)
    assert would_breach_sector_limit(state, "AU2612", max_positions=2) is None
