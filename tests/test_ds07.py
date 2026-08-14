"""DS07 共振式核心单测：D1 camp 战略授权 + H1 DS03 二四棒同向触发。

覆盖：LONG/SHORT_CONTINUE 触发、双周期不同向/缺 N 结构/缺极值线不触发、
attack_key 去重、止损与成交、D1→H1 周期映射、结构审计。
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from fengji_core.ds07 import (
    add_atr,
    audit_ds07_structure,
    check_stop,
    entry_fill,
    make_ds07_signal,
    map_d1_to_h1_future,
    map_d1_to_h1_natural_day,
    prepare_datetime_ohlcv,
    update_ds07_stop,
)


def _prev_long() -> dict:
    return {
        "open": 9.8, "high": 9.9, "low": 9.7, "close": 9.8, "volume": 100,
        "camp": 1, "camp_confirmed": 1,
        "active_high": 10.0, "active_low": 9.0,
        "red_peak_idx": 3, "red_peak_price": 10.0,
        "red_ext_idx": 2, "red_ext_price": 8.8,
        "hardened_count": 4,
        "session_date": pd.Timestamp("2026-08-13"),
    }


def _row_long() -> dict:
    return {
        "open": 10.2, "high": 10.5, "low": 10.1, "close": 10.4, "volume": 100,
        "camp": 1, "camp_confirmed": 1,
        "active_high": 10.0, "active_low": 9.0,
        "d1_camp": 1,
        "session_date": pd.Timestamp("2026-08-13"),
    }


def _prev_short() -> dict:
    return {
        "open": 8.3, "high": 8.4, "low": 8.2, "close": 8.3, "volume": 100,
        "camp": -1, "camp_confirmed": -1,
        "active_high": 10.0, "active_low": 8.0,
        "blue_peak_idx": 3, "blue_peak_price": 8.0,
        "blue_ext_idx": 2, "blue_ext_price": 9.2,
        "hardened_count": 4,
        "session_date": pd.Timestamp("2026-08-13"),
    }


def _row_short() -> dict:
    return {
        "open": 7.9, "high": 8.1, "low": 7.7, "close": 7.8, "volume": 100,
        "camp": -1, "camp_confirmed": -1,
        "active_high": 10.0, "active_low": 8.0,
        "d1_camp": -1,
        "session_date": pd.Timestamp("2026-08-13"),
    }


def _h1_frame(prev: dict, row: dict) -> pd.DataFrame:
    return pd.DataFrame([prev, row])


def _row(row: pd.DataFrame, i: int) -> pd.Series:
    return row.iloc[i]


# ---------------------------------------------------------------------------
# LONG / SHORT_CONTINUE 正常触发
# ---------------------------------------------------------------------------

def test_long_continue_trigger() -> None:
    df = _h1_frame(_prev_long(), _row_long())
    used: set[str] = set()
    sig = make_ds07_signal(_row(df, 1), 1, used, symbol="BTCUSDT", prev_row=_row(df, 0), df=df)

    assert sig is not None
    assert sig.side == 1
    assert sig.trigger_type == "LONG_CONTINUE"
    assert sig.d1_camp == 1
    assert sig.prev_h1_camp == 1
    assert sig.h1_camp == 1
    assert sig.attack_idx == 3
    assert sig.attack_price == pytest.approx(10.0)
    assert sig.defense_idx == 2
    assert sig.defense_price == pytest.approx(8.8)
    assert sig.entry_ref == pytest.approx(10.0)
    assert sig.initial_stop == pytest.approx(8.8)
    assert sig.pattern == "DS07 D1 Red + H1 Red DS03 | DS03 Red Break True Peak Shou2-Shou4"
    assert sig.session_date == pd.Timestamp("2026-08-13")
    assert sig.attack_key == "BTCUSDT|LONG_CONTINUE|DS03|1|true_peak|idx=3|px=10"


def test_short_continue_trigger() -> None:
    df = _h1_frame(_prev_short(), _row_short())
    used: set[str] = set()
    sig = make_ds07_signal(_row(df, 1), 1, used, symbol="BTCUSDT", prev_row=_row(df, 0), df=df)

    assert sig is not None
    assert sig.side == -1
    assert sig.trigger_type == "SHORT_CONTINUE"
    assert sig.d1_camp == -1
    assert sig.prev_h1_camp == -1
    assert sig.h1_camp == -1
    assert sig.attack_idx == 3
    assert sig.attack_price == pytest.approx(8.0)
    assert sig.defense_idx == 2
    assert sig.defense_price == pytest.approx(9.2)
    assert sig.entry_ref == pytest.approx(8.0)
    assert sig.initial_stop == pytest.approx(9.2)


def test_fake_peak_trigger_source() -> None:
    """假峰（FAILED 峰）突破同样可触发 DS07。"""
    prev = _prev_long()
    prev["hardened_count"] = 4
    prev["high"] = 9.75  # 上一根未触及假峰价 → 本根是首破
    row = _row_long()
    # 构造假峰突破：high 未破 active_high(10.0)，但破了 last_failed_high(9.8)
    row["last_failed_high_idx"] = 4
    row["last_failed_high_price"] = 9.8
    row["red_ext_idx"] = 5
    row["red_ext_price"] = 8.8
    row["high"] = 9.9
    row["open"] = 9.7
    row["low"] = 9.6
    row["close"] = 9.85
    # prev.camp=1 & cur.camp=1，defense_idx(5) > fake_idx(4)，row.high 9.9 > fake 9.8 且 <= active_high 10.0
    df = _h1_frame(prev, row)
    used: set[str] = set()
    sig = make_ds07_signal(_row(df, 1), 1, used, symbol="BTCUSDT", prev_row=_row(df, 0), df=df)

    assert sig is not None
    assert sig.attack_key == "BTCUSDT|LONG_CONTINUE|DS03|1|fake_peak|idx=4|px=9.8"


# ---------------------------------------------------------------------------
# 不触发场景
# ---------------------------------------------------------------------------

def test_no_signal_without_ds03_attack() -> None:
    row = _row_long()
    row["high"] = 9.9  # 未破 active_high=10.0
    df = _h1_frame(_prev_long(), row)
    sig = make_ds07_signal(_row(df, 1), 1, set(), symbol="BTCUSDT", prev_row=_row(df, 0), df=df)

    assert sig is None


def test_no_signal_d1_mismatch_long_short() -> None:
    # D1=1 但 H1 是 SHORT 攻击 → 不同向
    row = _row_short()
    row["d1_camp"] = 1
    df = _h1_frame(_prev_short(), row)
    sig = make_ds07_signal(_row(df, 1), 1, set(), symbol="BTCUSDT", prev_row=_row(df, 0), df=df)
    assert sig is None

    # D1=-1 但 H1 是 LONG 攻击 → 不同向
    row2 = _row_long()
    row2["d1_camp"] = -1
    df2 = _h1_frame(_prev_long(), row2)
    sig2 = make_ds07_signal(_row(df2, 1), 1, set(), symbol="BTCUSDT", prev_row=_row(df2, 0), df=df2)
    assert sig2 is None


def test_no_signal_missing_n_structure() -> None:
    prev = _prev_long()
    prev["hardened_count"] = 3  # < 4 → N 结构不足
    df = _h1_frame(prev, _row_long())
    sig = make_ds07_signal(_row(df, 1), 1, set(), symbol="BTCUSDT", prev_row=_row(df, 0), df=df)

    assert sig is None


def test_no_signal_missing_red_ext_line() -> None:
    prev = _prev_long()
    prev["red_ext_price"] = np.nan
    prev["red_ext_idx"] = np.nan
    df = _h1_frame(prev, _row_long())
    sig = make_ds07_signal(_row(df, 1), 1, set(), symbol="BTCUSDT", prev_row=_row(df, 0), df=df)

    assert sig is None


def test_no_signal_missing_prev_h1_camp() -> None:
    prev = _prev_long()
    prev["camp_confirmed"] = -1  # 上一根 H1 还在蓝阵营
    df = _h1_frame(prev, _row_long())
    sig = make_ds07_signal(_row(df, 1), 1, set(), symbol="BTCUSDT", prev_row=_row(df, 0), df=df)

    assert sig is None


def test_no_signal_stop_not_below_entry() -> None:
    prev = _prev_long()
    prev["red_ext_price"] = 10.3  # 止损 >= 入场(10.2) → 拒绝
    df = _h1_frame(prev, _row_long())
    sig = make_ds07_signal(_row(df, 1), 1, set(), symbol="BTCUSDT", prev_row=_row(df, 0), df=df)

    assert sig is None


def test_used_attack_keys_dedup() -> None:
    """make_ds07_signal 不写 used；调用方负责消费 key，消费后同 key 不再触发。"""
    df = _h1_frame(_prev_long(), _row_long())
    used: set[str] = set()
    first = make_ds07_signal(_row(df, 1), 1, used, symbol="BTCUSDT", prev_row=_row(df, 0), df=df)
    assert first is not None
    assert len(used) == 0  # 纯函数不修改入参
    used.add(first.attack_key)  # 模拟调用方消费
    second = make_ds07_signal(_row(df, 1), 1, used, symbol="BTCUSDT", prev_row=_row(df, 0), df=df)
    assert second is None


def test_requires_prev_row_and_df() -> None:
    row = _row_long()
    assert make_ds07_signal(row, 0, set(), symbol="BTCUSDT") is None
    assert make_ds07_signal(row, 1, set(), symbol="BTCUSDT", prev_row=None, df=None) is None


# ---------------------------------------------------------------------------
# 成交 / 止损 / 移动止损
# ---------------------------------------------------------------------------

def test_entry_fill_long_short() -> None:
    class _L:  # noqa: N801
        side = 1
        entry_ref = 10.0

    class _S:  # noqa: N801
        side = -1
        entry_ref = 8.0

    long_row = pd.Series({"open": 10.5, "high": 10.6, "low": 10.4, "close": 10.5})
    assert entry_fill(long_row, _L()) == pytest.approx(10.5)
    short_row = pd.Series({"open": 8.3, "high": 8.4, "low": 8.2, "close": 8.3})
    assert entry_fill(short_row, _S()) == pytest.approx(8.0)  # min(8.3, 8.0)


def test_check_stop_long_short() -> None:
    long_pos = {"side": 1, "stop": 9.5}
    assert check_stop(pd.Series({"open": 9.4, "low": 9.3, "high": 9.6}), long_pos) == (9.4, "gap_stop")
    assert check_stop(pd.Series({"open": 9.6, "low": 9.5, "high": 9.7}), long_pos) == (9.5, "stop")
    assert check_stop(pd.Series({"open": 9.8, "low": 9.6, "high": 9.9}), long_pos) == (None, None)

    short_pos = {"side": -1, "stop": 10.5}
    assert check_stop(pd.Series({"open": 10.6, "high": 10.8, "low": 10.5}), short_pos) == (10.6, "gap_stop")
    assert check_stop(pd.Series({"open": 10.4, "high": 10.6, "low": 10.3}), short_pos) == (10.5, "stop")
    assert check_stop(pd.Series({"open": 10.3, "high": 10.4, "low": 10.2}), short_pos) == (None, None)


def test_update_stop_moves_with_extreme_line() -> None:
    long_pos = {"side": 1, "stop": 8.8}
    update_ds07_stop(long_pos, pd.Series({"red_ext_price": 9.0, "red_ext_idx": 7}))
    assert long_pos["stop"] == pytest.approx(9.0)

    short_pos = {"side": -1, "stop": 9.2}
    update_ds07_stop(short_pos, pd.Series({"blue_ext_price": 9.0, "blue_ext_idx": 7}))
    assert short_pos["stop"] == pytest.approx(9.0)


def test_update_stop_ignores_invalid_line() -> None:
    long_pos = {"side": 1, "stop": 8.8}
    update_ds07_stop(long_pos, pd.Series({"red_ext_price": np.nan}))
    assert long_pos["stop"] == pytest.approx(8.8)


# ---------------------------------------------------------------------------
# 数据映射与预处理
# ---------------------------------------------------------------------------

def test_prepare_datetime_ohlcv_chinese_columns() -> None:
    frame = pd.DataFrame(
        {
            "时间": ["2026-08-13 09:00:00", "2026-08-13 10:00:00"],
            "开盘": [10.0, 10.2],
            "最高": [10.5, 10.6],
            "最低": [9.9, 10.1],
            "收盘": [10.4, 10.5],
            "成交量": [100, 120],
        }
    )
    out = prepare_datetime_ohlcv(frame)
    assert list(out.columns) == ["date", "open", "high", "low", "close", "volume"]
    assert out["date"].iloc[0] == pd.Timestamp("2026-08-13 09:00:00")
    assert out["close"].iloc[1] == pytest.approx(10.5)


def test_prepare_datetime_ohlcv_positional_columns() -> None:
    frame = pd.DataFrame(
        [
            ["2026-08-13 09:00:00", 10.0, 10.5, 9.9, 10.4, 100],
            ["2026-08-13 10:00:00", 10.2, 10.6, 10.1, 10.5, 120],
        ]
    )
    out = prepare_datetime_ohlcv(frame)
    assert out["open"].iloc[0] == pytest.approx(10.0)
    assert out["date"].iloc[1] == pd.Timestamp("2026-08-13 10:00:00")


def test_prepare_datetime_ohlcv_missing_columns_raises() -> None:
    frame = pd.DataFrame({"时间": ["2026-08-13"], "开盘": [10.0]})
    with pytest.raises(ValueError):
        prepare_datetime_ohlcv(frame)


def test_add_atr() -> None:
    frame = pd.DataFrame(
        {
            "date": pd.date_range("2026-08-01", periods=15, freq="h"),
            "open": 100.0, "high": 101.0, "low": 99.0, "close": 100.0,
            "volume": 100,
        }
    )
    out = add_atr(frame, window=14)
    assert "atr" in out.columns
    assert out["atr"].iloc[:13].isna().all()
    assert out["atr"].iloc[14] == pytest.approx(2.0)


def test_map_d1_to_h1_natural_day() -> None:
    d1 = pd.DataFrame(
        {
            "date": ["2026-08-12", "2026-08-13", "2026-08-14"],
            "camp": [1, -1, -1],
        }
    )
    h1 = pd.DataFrame(
        {
            "date": ["2026-08-13 09:00", "2026-08-13 15:00", "2026-08-14 10:00"],
            "open": [10.0, 10.2, 10.4],
            "high": [10.5, 10.6, 10.8],
            "low": [9.9, 10.1, 10.3],
            "close": [10.4, 10.5, 10.7],
            "volume": [100, 120, 110],
        }
    )
    out = map_d1_to_h1_natural_day(d1, h1)
    # d1_camp = 上一交易日 D1 camp：8-13 → 8-12 camp=1；8-14 → 8-13 camp=-1
    assert out["d1_camp"].tolist() == [1, 1, -1]
    assert len(out) == 3


def test_map_d1_to_h1_future_night_session() -> None:
    d1 = pd.DataFrame(
        {
            "date": ["2026-08-12", "2026-08-13", "2026-08-14"],
            "camp": [1, -1, 1],
        }
    )
    h1 = pd.DataFrame(
        {
            "date": [
                "2026-08-12 20:00",  # 夜盘 20 点 → 归属 8-12
                "2026-08-12 22:00",  # 夜盘 22 点 → 归属 8-13（>=21 点 +1 天）
                "2026-08-13 10:00",  # 日盘 → 归属 8-13
            ],
            "open": [10.0, 10.2, 10.4],
            "high": [10.5, 10.6, 10.8],
            "low": [9.9, 10.1, 10.3],
            "close": [10.4, 10.5, 10.7],
            "volume": [100, 120, 110],
        }
    )
    out = map_d1_to_h1_future(d1, h1)
    # 8-12 归属 → d1_camp = 8-11 camp（无 → 0）
    # 8-13 归属 → d1_camp = 8-12 camp=1
    assert out["d1_camp"].tolist() == [0, 1, 1]
    assert out["session_date"].iloc[1] == pd.Timestamp("2026-08-13")
    assert len(out) == 3


def test_map_d1_to_h1_future_out_of_range_dropped() -> None:
    d1 = pd.DataFrame({"date": ["2026-08-13"], "camp": [1]})
    h1 = pd.DataFrame(
        {
            "date": ["2026-08-12 22:00"],  # 22 点 → 归属 8-13，在 d1 范围内
            "open": [10.0], "high": [10.5], "low": [9.9], "close": [10.4], "volume": [100],
        }
    )
    out = map_d1_to_h1_future(d1, h1)
    assert len(out) == 1
    assert out["d1_camp"].iloc[0] == 0  # 8-12 的 camp 无 → 0


# ---------------------------------------------------------------------------
# 结构审计
# ---------------------------------------------------------------------------

def _clean_long_trade() -> dict:
    return {
        "direction": "long",
        "d1_camp": 1,
        "h1_camp": 1,
        "prev_h1_camp": 1,
        "trigger_type": "LONG_CONTINUE",
        "attack_price": 10.0,
        "entry_price": 10.2,
        "defense_price": 8.8,
        "attack_key": "BTCUSDT|LONG_CONTINUE|DS03|1|true_peak|idx=3|px=10",
    }


def test_audit_structure_clean_long_short() -> None:
    short_trade = {
        "direction": "short",
        "d1_camp": -1,
        "h1_camp": -1,
        "prev_h1_camp": -1,
        "trigger_type": "SHORT_CONTINUE",
        "attack_price": 8.0,
        "entry_price": 7.9,
        "defense_price": 9.2,
        "attack_key": "BTCUSDT|SHORT_CONTINUE|DS03|-1|true_peak|idx=3|px=8",
    }
    trades = pd.DataFrame([_clean_long_trade(), short_trade])
    assert audit_ds07_structure(trades).empty


def test_audit_structure_bad_defense_above_entry() -> None:
    trade = _clean_long_trade()
    trade["defense_price"] = 10.5  # 防守 >= 入场 → 非法
    bad = audit_ds07_structure(pd.DataFrame([trade]))
    assert len(bad) == 1


def test_audit_structure_bad_camp() -> None:
    trade = _clean_long_trade()
    trade["d1_camp"] = -1  # long 但 D1 蓝 → 非法
    bad = audit_ds07_structure(pd.DataFrame([trade]))
    assert len(bad) == 1


def test_audit_structure_duplicate_attack_key() -> None:
    trade = _clean_long_trade()
    duplicate = dict(trade)
    duplicate["entry_price"] = 10.3
    trades = pd.DataFrame([trade, duplicate])
    bad = audit_ds07_structure(trades)
    assert len(bad) == 2


def test_audit_structure_empty() -> None:
    assert audit_ds07_structure(pd.DataFrame()).empty
