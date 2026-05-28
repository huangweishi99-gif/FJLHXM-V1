from __future__ import annotations

import pandas as pd

from fengji_core.ds03 import make_ds03_signal, resolve_ds03_attack


def base_frame() -> pd.DataFrame:
    rows = []
    for i in range(8):
        rows.append(
            {
                "date": pd.Timestamp("2026-05-01") + pd.Timedelta(days=i),
                "open": 9.0,
                "high": 9.2,
                "low": 8.8,
                "close": 9.0,
                "camp": 1,
                "active_high": 10.0,
                "active_low": 8.0,
                "red_peak_idx": 1,
                "red_ext_idx": 3,
                "last_failed_high_idx": float("nan"),
                "last_failed_high_price": float("nan"),
                "blue_peak_idx": float("nan"),
                "blue_ext_idx": float("nan"),
                "last_failed_low_idx": float("nan"),
                "last_failed_low_price": float("nan"),
            }
        )
    return pd.DataFrame(rows)


def test_ds03_true_peak_first_starter_bar() -> None:
    df = base_frame()
    df.loc[7, "high"] = 10.2

    signal = make_ds03_signal(df, 7)

    assert signal is not None
    assert signal.side == 1
    assert signal.entry_ref == 10.0
    assert signal.trigger_source == "true_peak"
    assert signal.ref_idx == 1


def test_ds03_true_peak_blocks_second_starter_bar() -> None:
    df = base_frame()
    df.loc[6, "high"] = 10.2
    df.loc[7, "high"] = 10.3
    consumed: set[str] = set()

    first = make_ds03_signal(df, 6, consumed)
    second = make_ds03_signal(df, 7, consumed)

    assert first is not None
    assert second is None


def test_ds03_one_peak_key_only_once_even_after_pullback() -> None:
    df = base_frame()
    df.loc[6, "high"] = 10.2
    consumed: set[str] = set()
    first = make_ds03_signal(df, 6, consumed)
    assert first is not None
    df.loc[7, "high"] = 9.5
    df.loc[8] = df.loc[7].copy()
    df.loc[8, "date"] = pd.Timestamp("2026-05-09")
    df.loc[8, "high"] = 10.3
    retry = make_ds03_signal(df, 8, consumed)
    assert retry is None


def test_ds03_fake_peak_starter_bar_under_true_peak_cap() -> None:
    df = base_frame()
    df.loc[7, "high"] = 9.7
    df.loc[7, "last_failed_high_idx"] = 4
    df.loc[7, "last_failed_high_price"] = 9.5
    df.loc[7, "red_ext_idx"] = 6

    attack = resolve_ds03_attack(df, 7)
    signal = make_ds03_signal(df, 7)

    assert attack is not None
    assert attack.trigger_source == "fake_peak"
    assert signal is not None
    assert signal.entry_ref == 9.5
    assert signal.ref_idx == 4
    assert signal.pattern == "DS03 Red Break Fake Peak Shou2-Shou4"


def test_ds03_fake_peak_requires_later_defense_extreme() -> None:
    df = base_frame()
    df.loc[7, "high"] = 9.7
    df.loc[7, "last_failed_high_idx"] = 4
    df.loc[7, "last_failed_high_price"] = 9.5
    df.loc[7, "red_ext_idx"] = 3

    assert resolve_ds03_attack(df, 7) is None
    assert make_ds03_signal(df, 7) is None


def test_ds03_fake_peak_cannot_break_true_peak() -> None:
    df = base_frame()
    df.loc[7, "high"] = 10.2
    df.loc[7, "last_failed_high_idx"] = 4
    df.loc[7, "last_failed_high_price"] = 9.5
    df.loc[7, "red_ext_idx"] = 6

    assert resolve_ds03_attack(df, 7) is not None
    assert resolve_ds03_attack(df, 7).trigger_source == "true_peak"


def test_ds03_blue_fake_peak_is_mirrored() -> None:
    df = base_frame()
    for idx in [6, 7]:
        df.loc[idx, "camp"] = -1
    df.loc[6, "active_low"] = 8.0
    df.loc[6, "blue_peak_idx"] = 1
    df.loc[7, "low"] = 8.25
    df.loc[7, "active_low"] = 8.0
    df.loc[7, "last_failed_low_idx"] = 4
    df.loc[7, "last_failed_low_price"] = 8.4
    df.loc[7, "blue_ext_idx"] = 6

    signal = make_ds03_signal(df, 7)

    assert signal is not None
    assert signal.side == -1
    assert signal.entry_ref == 8.4
    assert signal.trigger_source == "fake_peak"
