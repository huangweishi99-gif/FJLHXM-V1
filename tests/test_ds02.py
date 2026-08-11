"""DS02 standalone unit tests: Yin-Yang devouring pattern."""
from __future__ import annotations

import pandas as pd

from fengji_core.ds02 import (
    DS02Signal,
    audit_ds02_camp_direction,
    check_stop,
    make_ds02_signal,
    update_ds02_stop,
)


def red_yin_yang_long_frame() -> pd.DataFrame:
    """Red camp: K1 yin, K2 yang close > K1 high."""
    return pd.DataFrame(
        [
            {"open": 10.5, "high": 10.6, "low": 10.0, "close": 10.2, "camp": 1},  # K1 yin, high=10.6
            {"open": 10.1, "high": 10.8, "low": 9.9, "close": 10.7, "camp": 1},  # K2 yang, close=10.7 > 10.6
            {"open": 10.6, "high": 11.2, "low": 10.4, "close": 11.0, "camp": 1},  # next bar
        ]
    )


def blue_yang_yin_short_frame() -> pd.DataFrame:
    """Blue camp: K1 yang, K2 yin close < K1 low."""
    return pd.DataFrame(
        [
            {"open": 20.0, "high": 21.0, "low": 19.5, "close": 20.8, "camp": -1},  # K1 yang
            {"open": 20.9, "high": 21.1, "low": 19.0, "close": 19.3, "camp": -1},  # K2 yin close<K1 low
            {"open": 19.4, "high": 19.8, "low": 19.0, "close": 19.5, "camp": -1},  # next bar
        ]
    )


class TestMakeDS02Signal:
    def test_red_yin_eats_yang_long(self) -> None:
        """K1 yin, K2 yang, K2 close > K1 high, camp=1 => Long."""
        df = red_yin_yang_long_frame()
        sig = make_ds02_signal(df, 1)

        assert sig is not None
        assert sig.side == 1
        assert sig.activate_idx == 2
        assert sig.pattern == "DS02 Red Yang-Eats-Yin"
        assert sig.k1 == 0
        assert sig.k2 == 1
        assert sig.camp_k1 == 1
        assert sig.camp_k2 == 1
        assert sig.signal_camp == 1
        assert sig.initial_stop == min(10.0, 9.9)

    def test_blue_yang_eats_yin_short(self) -> None:
        """K1 yang, K2 yin, K2 close < K1 low, camp=-1 => Short."""
        df = blue_yang_yin_short_frame()
        sig = make_ds02_signal(df, 1)

        assert sig is not None
        assert sig.side == -1
        assert sig.pattern == "DS02 Blue Yin-Eats-Yang"
        assert sig.k1 == 0
        assert sig.k2 == 1
        assert sig.camp_k1 == -1
        assert sig.camp_k2 == -1
        assert sig.signal_camp == -1
        assert sig.initial_stop == max(21.0, 21.1)

    def test_rejects_camp_mismatch(self) -> None:
        """K1 camp != K2 camp => reject."""
        df = pd.DataFrame(
            [
                {"open": 10.5, "high": 11.0, "low": 10.0, "close": 10.2, "camp": 1},  # K1 red
                {"open": 10.1, "high": 10.8, "low": 9.9, "close": 10.7, "camp": -1},  # K2 blue
            ]
        )
        sig = make_ds02_signal(df, 1)
        assert sig is None

    def test_rejects_camp_zero(self) -> None:
        """camp=0 => reject."""
        df = pd.DataFrame(
            [
                {"open": 10.5, "high": 11.0, "low": 10.0, "close": 10.2, "camp": 0},
                {"open": 10.1, "high": 10.8, "low": 9.9, "close": 10.7, "camp": 0},
            ]
        )
        sig = make_ds02_signal(df, 1)
        assert sig is None

    def test_rejects_when_no_devour_price_condition(self) -> None:
        """K2 close does not exceed K1 high => no devour => reject."""
        df = pd.DataFrame(
            [
                {"open": 10.5, "high": 11.5, "low": 10.0, "close": 10.2, "camp": 1},  # K1 high=11.5
                {"open": 10.1, "high": 10.3, "low": 9.9, "close": 10.25, "camp": 1},  # K2 close=10.25 < K1 high=11.5
            ]
        )
        sig = make_ds02_signal(df, 1)
        assert sig is None

    def test_rejects_too_short_frame(self) -> None:
        """Not enough bars before index."""
        df = pd.DataFrame([
            {"open": 10.0, "high": 11.0, "low": 9.5, "close": 10.8, "camp": 1},
        ])
        sig = make_ds02_signal(df, 0)
        assert sig is None

    def test_rejects_at_frame_end_without_next_bar(self) -> None:
        """i+1 >= len(df) => reject."""
        df = pd.DataFrame(
            [
                {"open": 10.5, "high": 11.0, "low": 10.0, "close": 10.2, "camp": 1},
                {"open": 10.1, "high": 10.8, "low": 9.9, "close": 10.7, "camp": 1},
            ]
        )
        sig = make_ds02_signal(df, 1)  # i+1=2 >= len=2
        assert sig is None

    def test_ds02_signal_to_dict(self) -> None:
        sig = DS02Signal(
            side=1,
            activate_idx=2,
            initial_stop=9.9,
            pattern="DS02 Red Yang-Eats-Yin",
            k1=0,
            k2=1,
            camp_k1=1,
            camp_k2=1,
            signal_camp=1,
        )
        d = sig.to_dict()
        assert d["side"] == 1
        assert d["pattern"] == "DS02 Red Yang-Eats-Yin"
        assert d["k1"] == 0
        assert d["k2"] == 1


class TestUpdateDS02Stop:
    def test_long_trail_on_yang_bar(self) -> None:
        pos = {"side": 1, "stop": 10.0}
        row = pd.Series({"close": 10.5, "open": 10.0, "low": 10.2})
        updated = update_ds02_stop(pos, row)
        assert updated["stop"] == 10.2  # max(10.0, 10.2)

    def test_long_no_trail_on_yin_bar(self) -> None:
        pos = {"side": 1, "stop": 10.0}
        row = pd.Series({"close": 9.8, "open": 10.2, "low": 9.5})
        updated = update_ds02_stop(pos, row)
        assert updated["stop"] == 10.0  # unchanged

    def test_short_trail_on_yin_bar(self) -> None:
        pos = {"side": -1, "stop": 20.0}
        row = pd.Series({"close": 19.5, "open": 20.0, "high": 19.8})
        updated = update_ds02_stop(pos, row)
        assert updated["stop"] == 19.8  # min(20.0, 19.8)

    def test_short_no_trail_on_yang_bar(self) -> None:
        pos = {"side": -1, "stop": 20.0}
        row = pd.Series({"close": 20.5, "open": 20.0, "high": 21.0})
        updated = update_ds02_stop(pos, row)
        assert updated["stop"] == 20.0  # unchanged


class TestCheckStop:
    def test_long_gap_stop(self) -> None:
        pos = {"side": 1, "stop": 10.0}
        row = pd.Series({"open": 9.5, "high": 10.3, "low": 9.0})
        price, reason = check_stop(row, pos)
        assert price == 9.5
        assert reason == "gap_stop"

    def test_long_intraday_stop(self) -> None:
        pos = {"side": 1, "stop": 10.0}
        row = pd.Series({"open": 10.2, "high": 10.5, "low": 9.5})
        price, reason = check_stop(row, pos)
        assert price == 10.0
        assert reason == "stop"

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
        assert reason == "gap_stop"

    def test_short_intraday_stop(self) -> None:
        pos = {"side": -1, "stop": 20.0}
        row = pd.Series({"open": 19.5, "high": 20.5, "low": 19.3})
        price, reason = check_stop(row, pos)
        assert price == 20.0
        assert reason == "stop"

    def test_short_no_stop(self) -> None:
        pos = {"side": -1, "stop": 20.0}
        row = pd.Series({"open": 19.5, "high": 19.8, "low": 19.3})
        price, reason = check_stop(row, pos)
        assert price is None
        assert reason is None


class TestAuditDS02CampDirection:
    def test_empty_trades(self) -> None:
        result = audit_ds02_camp_direction(pd.DataFrame())
        assert result.empty

    def test_valid_trades_pass(self) -> None:
        trades = pd.DataFrame([
            {"direction": "long", "camp_k1": 1, "camp_k2": 1},
            {"direction": "short", "camp_k1": -1, "camp_k2": -1},
        ])
        bad = audit_ds02_camp_direction(trades)
        assert bad.empty

    def test_long_with_wrong_camp_flagged(self) -> None:
        trades = pd.DataFrame([
            {"direction": "long", "camp_k1": -1, "camp_k2": -1},
        ])
        bad = audit_ds02_camp_direction(trades)
        assert len(bad) == 1

    def test_short_with_wrong_camp_flagged(self) -> None:
        trades = pd.DataFrame([
            {"direction": "short", "camp_k1": 1, "camp_k2": 1},
        ])
        bad = audit_ds02_camp_direction(trades)
        assert len(bad) == 1
