"""DS04 standalone unit tests: clip / barrier gun pattern (K1/K2/K3)."""
from __future__ import annotations

import pandas as pd

from fengji_core.ds04 import (
    DS04Signal,
    audit_ds04_structure,
    check_stop,
    k2_is_weakest,
    make_ds04_signal,
    no_price_gap,
    update_ds04_stop,
)


def yang_yin_yang_long_frame() -> pd.DataFrame:
    """K0/K1=yang, K2=yin weakest, K3=yang close>K1 high, K4=entry bar."""
    return pd.DataFrame(
        [
            {"open": 10.2, "high": 10.8, "low": 9.8, "close": 10.6, "camp": 0},  # K0 bar-before-K1
            {"open": 10.5, "high": 11.5, "low": 10.2, "close": 11.2, "camp": 1},  # K1 yang (idx 1)
            {"open": 11.2, "high": 11.3, "low": 10.9, "close": 11.0, "camp": 1},  # K2 yin small body (idx 2)
            {"open": 10.9, "high": 12.0, "low": 10.8, "close": 11.8, "camp": 1},  # K3 yang reclaims K1 high (idx 3)
            {"open": 11.7, "high": 12.2, "low": 11.5, "close": 12.0, "camp": 1},  # K4 entry bar (idx 4)
        ]
    )


def yin_yang_yin_short_frame() -> pd.DataFrame:
    """K0/K1=yin, K2=yang weakest, K3=yin close<K1 low, K4=entry bar."""
    return pd.DataFrame(
        [
            {"open": 20.5, "high": 21.2, "low": 20.0, "close": 20.8, "camp": 0},  # K0 bar-before-K1
            {"open": 21.0, "high": 22.0, "low": 20.1, "close": 20.3, "camp": -1},  # K1 yin (idx 1)
            {"open": 20.4, "high": 20.6, "low": 20.0, "close": 20.5, "camp": -1},  # K2 yang small (idx 2)
            {"open": 20.6, "high": 20.8, "low": 19.5, "close": 19.7, "camp": -1},  # K3 yin reclaims K1 low (idx 3)
            {"open": 19.6, "high": 20.0, "low": 19.2, "close": 19.4, "camp": -1},  # K4 entry bar (idx 4)
        ]
    )


def gap_frame() -> pd.DataFrame:
    """K2 gaps away from K1 => should reject. Needs 5 bars (K0-K4)."""
    return pd.DataFrame(
        [
            {"open": 10.0, "high": 10.5, "low": 9.5, "close": 10.3, "camp": 0},  # K0
            {"open": 10.2, "high": 11.0, "low": 10.0, "close": 10.8, "camp": 1},  # K1 yang
            {"open": 12.0, "high": 12.2, "low": 11.8, "close": 11.9, "camp": 1},  # K2: low(11.8) > K1 high(11.0) = GAP
            {"open": 11.8, "high": 12.5, "low": 11.7, "close": 12.3, "camp": 1},  # K3
            {"open": 12.2, "high": 12.8, "low": 12.0, "close": 12.5, "camp": 1},  # K4 entry
        ]
    )


class TestMakeDS04Signal:
    def test_long_yang_yin_yang_reclaim(self) -> None:
        """K1 yang, K2 yin weakest, K3 yang close > K1 high => DS04 Long."""
        df = yang_yin_yang_long_frame()
        sig = make_ds04_signal(df, 3)

        assert sig is not None
        assert sig.side == 1
        assert sig.activate_idx == 4  # k3_idx + 1
        assert sig.pattern == "DS04 Long Yang-Yin-Yang Reclaim"
        assert sig.k1 == 1
        assert sig.k2 == 2
        assert sig.k3 == 3
        assert sig.reclaim_price == 11.5  # K1 high
        assert sig.initial_stop == 10.2  # min low from K1..K3
        assert sig.k3_camp == 1

    def test_short_yin_yang_yin_reclaim(self) -> None:
        """K1 yin, K2 yang weakest, K3 yin close < K1 low => DS04 Short."""
        df = yin_yang_yin_short_frame()
        sig = make_ds04_signal(df, 3)

        assert sig is not None
        assert sig.side == -1
        assert sig.pattern == "DS04 Short Yin-Yang-Yin Reclaim"
        assert sig.k1 == 1
        assert sig.k2 == 2
        assert sig.k3 == 3
        assert sig.reclaim_price == 20.1  # K1 low
        assert sig.initial_stop == 22.0  # max high from K1..K3
        assert sig.k3_camp == -1

    def test_rejects_when_noise_price_gap(self) -> None:
        """Gap between K1 and K2 => reject."""
        df = gap_frame()
        sig = make_ds04_signal(df, 3)
        assert sig is None

    def test_rejects_when_k2_not_weakest(self) -> None:
        """K2 body/range not the smallest => reject."""
        df = pd.DataFrame(
            [
                {"open": 10.0, "high": 10.8, "low": 9.8, "close": 10.5, "camp": 0},  # K0
                {"open": 10.5, "high": 11.5, "low": 10.2, "close": 11.2, "camp": 1},  # K1 small range
                {"open": 10.0, "high": 12.0, "low": 9.0, "close": 11.8, "camp": 1},  # K2 BIG range (not weakest)
                {"open": 11.5, "high": 12.5, "low": 11.0, "close": 12.3, "camp": 1},  # K3
                {"open": 12.2, "high": 13.0, "low": 12.0, "close": 12.8, "camp": 1},  # K4
            ]
        )
        sig = make_ds04_signal(df, 3)
        assert sig is None

    def test_rejects_when_no_reclaim(self) -> None:
        """K3 close does not exceed K1 high => no reclaim => reject."""
        df = pd.DataFrame(
            [
                {"open": 10.0, "high": 10.5, "low": 9.5, "close": 10.3, "camp": 0},  # K0
                {"open": 10.2, "high": 11.5, "low": 10.0, "close": 11.2, "camp": 1},  # K1 high=11.5
                {"open": 11.2, "high": 11.3, "low": 10.8, "close": 11.0, "camp": 1},  # K2 yin small
                {"open": 10.9, "high": 11.3, "low": 10.7, "close": 11.1, "camp": 1},  # K3 close=11.1 < K1 high=11.5
                {"open": 11.0, "high": 11.4, "low": 10.9, "close": 11.3, "camp": 1},  # K4
            ]
        )
        sig = make_ds04_signal(df, 3)
        assert sig is None

    def test_rejects_too_short_frame(self) -> None:
        """k3_idx < 3 => reject."""
        df = pd.DataFrame(
            [
                {"open": 10.0, "high": 11.0, "low": 9.5, "close": 10.8, "camp": 0},
                {"open": 10.5, "high": 11.5, "low": 10.2, "close": 11.2, "camp": 1},
                {"open": 11.2, "high": 11.3, "low": 10.8, "close": 11.0, "camp": 1},
                {"open": 10.9, "high": 12.0, "low": 10.7, "close": 11.8, "camp": 1},
            ]
        )
        sig = make_ds04_signal(df, 2)
        assert sig is None

    def test_rejects_k3_at_end_without_next_bar(self) -> None:
        """k3_idx+1 >= len(df) => reject (need next bar for entry)."""
        df = pd.DataFrame(
            [
                {"open": 10.0, "high": 10.5, "low": 9.5, "close": 10.3, "camp": 0},
                {"open": 10.2, "high": 11.5, "low": 10.0, "close": 11.2, "camp": 1},
                {"open": 11.2, "high": 11.3, "low": 10.8, "close": 11.0, "camp": 1},
                {"open": 10.9, "high": 12.0, "low": 10.7, "close": 11.8, "camp": 1},
                {"open": 11.7, "high": 12.2, "low": 11.5, "close": 12.0, "camp": 1},
            ]
        )
        # k3_idx=4, len=5, 4+1=5 >= 5 => reject
        sig = make_ds04_signal(df, 4)
        assert sig is None


class TestK2IsWeakest:
    def test_true_when_body_and_range_smallest(self) -> None:
        df = pd.DataFrame(
            [
                {"open": 10.0, "high": 11.0, "low": 9.5, "close": 10.8},
                {"open": 10.5, "high": 10.6, "low": 10.3, "close": 10.4},
                {"open": 10.4, "high": 11.5, "low": 10.2, "close": 11.2},
            ]
        )
        assert k2_is_weakest(df, 0, 1, 2) is True

    def test_false_when_body_not_smallest(self) -> None:
        df = pd.DataFrame(
            [
                {"open": 10.0, "high": 10.3, "low": 9.8, "close": 10.1},
                {"open": 10.5, "high": 11.5, "low": 9.5, "close": 11.3},
                {"open": 10.5, "high": 11.0, "low": 10.2, "close": 10.8},
            ]
        )
        assert k2_is_weakest(df, 0, 1, 2) is False


class TestNoPriceGap:
    def test_no_gap_when_overlapping(self) -> None:
        df = pd.DataFrame(
            [
                {"high": 10.5, "low": 9.5},
                {"high": 10.8, "low": 9.8},
            ]
        )
        assert no_price_gap(df, 0, 1) is True

    def test_gap_when_second_higher(self) -> None:
        df = pd.DataFrame(
            [
                {"high": 10.0, "low": 9.5},
                {"high": 11.0, "low": 10.5},  # low=10.5 > first.high=10.0 => gap
            ]
        )
        assert no_price_gap(df, 0, 1) is False

    def test_gap_when_second_lower(self) -> None:
        df = pd.DataFrame(
            [
                {"high": 10.0, "low": 9.5},
                {"high": 9.0, "low": 8.0},  # high=9.0 < first.low=9.5 => gap
            ]
        )
        assert no_price_gap(df, 0, 1) is False


class TestUpdateDS04Stop:
    def test_long_upgrades_to_red_ext(self) -> None:
        pos = {"side": 1, "stop": 10.0, "stop_source": "INITIAL_3K"}
        row = pd.Series({"red_ext_price": 10.5})
        updated = update_ds04_stop(pos, row)
        assert updated["stop"] == 10.5
        assert updated["stop_source"] == "UPGRADED_RED_EXT"

    def test_long_no_upgrade_when_red_ext_lower(self) -> None:
        pos = {"side": 1, "stop": 10.0, "stop_source": "INITIAL_3K"}
        row = pd.Series({"red_ext_price": 9.5})
        updated = update_ds04_stop(pos, row)
        assert updated["stop"] == 10.0
        assert updated["stop_source"] == "INITIAL_3K"

    def test_short_upgrades_to_blue_ext(self) -> None:
        pos = {"side": -1, "stop": 20.0, "stop_source": "INITIAL_3K"}
        row = pd.Series({"blue_ext_price": 19.5})
        updated = update_ds04_stop(pos, row)
        assert updated["stop"] == 19.5
        assert updated["stop_source"] == "UPGRADED_BLUE_EXT"

    def test_short_no_upgrade_when_blue_ext_higher(self) -> None:
        pos = {"side": -1, "stop": 20.0, "stop_source": "INITIAL_3K"}
        row = pd.Series({"blue_ext_price": 20.5})
        updated = update_ds04_stop(pos, row)
        assert updated["stop"] == 20.0
        assert updated["stop_source"] == "INITIAL_3K"

    def test_does_not_upgrade_when_nan(self) -> None:
        import numpy as np

        pos = {"side": 1, "stop": 10.0, "stop_source": "INITIAL_3K"}
        row = pd.Series({"red_ext_price": np.nan})
        updated = update_ds04_stop(pos, row)
        assert updated["stop"] == 10.0


class TestCheckStop:
    def test_long_gap_stop(self) -> None:
        pos = {"side": 1, "stop": 10.0}
        row = pd.Series({"open": 9.5, "high": 10.3, "low": 9.0})
        price, reason = check_stop(row, pos)
        assert price == 9.5
        assert "GAP" in reason

    def test_long_intraday_stop(self) -> None:
        pos = {"side": 1, "stop": 10.0}
        row = pd.Series({"open": 10.2, "high": 10.5, "low": 9.5})
        price, reason = check_stop(row, pos)
        assert price == 10.0
        assert "GAP" not in reason

    def test_long_no_stop(self) -> None:
        pos = {"side": 1, "stop": 10.0}
        row = pd.Series({"open": 10.2, "high": 10.5, "low": 10.1})
        price, reason = check_stop(row, pos)
        assert price is None
        assert reason is None

    def test_short_gap_stop(self) -> None:
        pos = {"side": -1, "stop": 20.0}
        row = pd.Series({"open": 20.5, "high": 21.0, "low": 19.0})
        price, reason = check_stop(row, pos)
        assert price == 20.5
        assert "GAP" in reason

    def test_short_intraday_stop(self) -> None:
        pos = {"side": -1, "stop": 20.0}
        row = pd.Series({"open": 19.5, "high": 20.5, "low": 19.3})
        price, reason = check_stop(row, pos)
        assert price == 20.0
        assert "GAP" not in reason

    def test_short_no_stop(self) -> None:
        pos = {"side": -1, "stop": 20.0}
        row = pd.Series({"open": 19.5, "high": 19.8, "low": 19.3})
        price, reason = check_stop(row, pos)
        assert price is None
        assert reason is None


class TestAuditDS04Structure:
    def test_empty_trades(self) -> None:
        result = audit_ds04_structure(pd.DataFrame())
        assert result.empty

    def test_valid_trades_pass(self) -> None:
        trades = pd.DataFrame([
            {"k1": 0, "k2": 1, "k3": 2, "reclaim_price": 10.0, "initial_stop": 9.5},
            {"k1": 5, "k2": 6, "k3": 7, "reclaim_price": 20.0, "initial_stop": 22.0},
        ])
        bad = audit_ds04_structure(trades)
        assert bad.empty

    def test_missing_required_field_flagged(self) -> None:
        trades = pd.DataFrame([
            {"k1": 0, "k2": 1, "k3": 2, "reclaim_price": None, "initial_stop": 9.5},
        ])
        bad = audit_ds04_structure(trades)
        assert len(bad) == 1
