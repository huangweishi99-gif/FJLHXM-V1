"""DS08 否认确定式核心单测：五点结构（V-P-V-P-V / P-V-P-V-P）+ 外扩价序 + 破攻击点触发。

覆盖：LONG/SHORT 触发、结构价序不符/角色不符不触发、等待期与触发前破攻击点
拒绝并消费 key、initial_stop 约束、成交/移动止损/审计。
"""
from __future__ import annotations

import pandas as pd
import pytest

from fengji_core.ds08 import (
    audit_ds08_structure,
    check_stop,
    entry_fill,
    make_ds08_signal,
    update_ds08_stop,
)
from fengji_core.os_engine import RawNode


def _node(point: int, confirm: int, price: float, raw_type: str) -> RawNode:
    return RawNode(
        point_idx=point,
        confirm_idx=confirm,
        price=price,
        raw_type=raw_type,
        dual_extreme=False,
        arbitration="",
        source="raw_33",
    )


def _frame(rows: list[tuple[float, float, float, float]]) -> pd.DataFrame:
    return pd.DataFrame(rows, columns=["open", "high", "low", "close"])


def _long_skeleton() -> list[RawNode]:
    """v1=10.0 < v2=10.2 < v3=10.8，p1=10.5 < p2=11.0（外扩）。"""
    return [
        _node(0, 0, 10.0, "LOW"),  # v1
        _node(1, 1, 10.5, "HIGH"),  # p1
        _node(2, 2, 10.2, "LOW"),  # v2
        _node(3, 3, 11.0, "HIGH"),  # p2
        _node(4, 5, 10.8, "LOW"),  # v3（point=4, confirm=5）
    ]


def _long_frame() -> pd.DataFrame:
    return _frame(
        [
            (10.0, 10.5, 10.0, 10.3),  # 0 v1
            (10.4, 10.5, 10.1, 10.4),  # 1 p1
            (10.2, 10.4, 10.0, 10.2),  # 2 v2
            (10.8, 11.0, 10.6, 10.9),  # 3 p2
            (10.8, 10.9, 10.6, 10.7),  # 4 v3 point
            (10.7, 10.9, 10.7, 10.8),  # 5 v3 confirm
            (10.8, 10.9, 10.7, 10.8),  # 6 未破 p2(11.0)
            (10.9, 11.2, 10.9, 11.1),  # 7 破 p2 → 触发
        ]
    )


def _short_skeleton() -> list[RawNode]:
    """p1=12.0 > p2=11.8 > p3=11.3，v1=11.5 > v2=11.0（外扩）。"""
    return [
        _node(0, 0, 12.0, "HIGH"),  # p1
        _node(1, 1, 11.5, "LOW"),  # v1
        _node(2, 2, 11.8, "HIGH"),  # p2
        _node(3, 3, 11.0, "LOW"),  # v2
        _node(4, 5, 11.3, "HIGH"),  # p3（point=4, confirm=5）
    ]


def _short_frame() -> pd.DataFrame:
    return _frame(
        [
            (12.0, 12.2, 11.8, 12.1),  # 0 p1
            (11.8, 11.9, 11.5, 11.6),  # 1 v1
            (11.7, 11.9, 11.5, 11.8),  # 2 p2
            (11.2, 11.3, 11.0, 11.1),  # 3 v2
            (11.4, 11.5, 11.2, 11.3),  # 4 p3 point
            (11.3, 11.5, 11.2, 11.4),  # 5 p3 confirm
            (11.3, 11.5, 11.1, 11.2),  # 6 未破 v2(11.0)
            (11.1, 11.3, 10.8, 10.9),  # 7 破 v2 → 触发
        ]
    )


# ---------------------------------------------------------------------------
# LONG / SHORT 正常触发
# ---------------------------------------------------------------------------

def test_long_signal_power_seizure() -> None:
    df = _long_frame()
    sig = make_ds08_signal(df, 7, _long_skeleton(), set(), symbol="BTCUSDT")

    assert sig is not None
    assert sig.side == 1
    assert sig.pattern == "DS08 Long Power Seizure"
    assert sig.activate_idx == 7
    assert sig.entry_ref == pytest.approx(11.0)  # p2
    assert sig.initial_stop == pytest.approx(10.8)  # v3
    assert sig.key == "BTCUSDT|LONG|4|3|11"
    assert sig.n1_price == pytest.approx(10.0)
    assert sig.n2_price == pytest.approx(10.5)
    assert sig.n3_price == pytest.approx(10.2)
    assert sig.n4_price == pytest.approx(11.0)
    assert sig.n5_price == pytest.approx(10.8)
    assert sig.n5_confirm_idx == 5
    assert sig.attack_idx == 3
    assert sig.attack_price == pytest.approx(11.0)
    assert sig.defense_idx == 4
    assert sig.defense_price == pytest.approx(10.8)


def test_short_signal_power_seizure() -> None:
    df = _short_frame()
    sig = make_ds08_signal(df, 7, _short_skeleton(), set(), symbol="BTCUSDT")

    assert sig is not None
    assert sig.side == -1
    assert sig.pattern == "DS08 Short Power Seizure"
    assert sig.activate_idx == 7
    assert sig.entry_ref == pytest.approx(11.0)  # v2
    assert sig.initial_stop == pytest.approx(11.3)  # p3
    assert sig.attack_idx == 3
    assert sig.attack_price == pytest.approx(11.0)
    assert sig.defense_idx == 4
    assert sig.defense_price == pytest.approx(11.3)


# ---------------------------------------------------------------------------
# 不触发场景
# ---------------------------------------------------------------------------

def test_no_signal_skeleton_too_short() -> None:
    df = _long_frame()
    sig = make_ds08_signal(df, 7, _long_skeleton()[:4], set(), symbol="BTCUSDT")
    assert sig is None


def test_no_signal_wrong_roles() -> None:
    skeleton = [
        _node(0, 0, 10.0, "LOW"),
        _node(1, 1, 10.5, "HIGH"),
        _node(2, 2, 10.2, "LOW"),
        _node(3, 3, 11.0, "HIGH"),
        _node(4, 5, 10.8, "HIGH"),  # 末位应为 LOW
    ]
    sig = make_ds08_signal(_long_frame(), 7, skeleton, set(), symbol="BTCUSDT")
    assert sig is None


def test_no_signal_long_price_order_broken() -> None:
    skeleton = [
        _node(0, 0, 10.0, "LOW"),
        _node(1, 1, 10.5, "HIGH"),
        _node(2, 2, 10.2, "LOW"),
        _node(3, 3, 11.0, "HIGH"),
        _node(4, 5, 9.9, "LOW"),  # v3 < v2 → 谷底不抬高
    ]
    sig = make_ds08_signal(_long_frame(), 7, skeleton, set(), symbol="BTCUSDT")
    assert sig is None


def test_no_signal_short_price_order_broken() -> None:
    skeleton = [
        _node(0, 0, 12.0, "HIGH"),
        _node(1, 1, 11.5, "LOW"),
        _node(2, 2, 11.8, "HIGH"),
        _node(3, 3, 11.0, "LOW"),
        _node(4, 5, 12.1, "HIGH"),  # p3 > p2 → 峰不下降
    ]
    sig = make_ds08_signal(_short_frame(), 7, skeleton, set(), symbol="BTCUSDT")
    assert sig is None


def test_no_signal_key_already_used() -> None:
    df = _long_frame()
    used: set[str] = set()
    first = make_ds08_signal(df, 7, _long_skeleton(), used, symbol="BTCUSDT")
    assert first is not None
    second = make_ds08_signal(df, 7, _long_skeleton(), used, symbol="BTCUSDT")
    assert second is None


def test_no_signal_i_within_v3_confirm() -> None:
    df = _long_frame()
    sig = make_ds08_signal(df, 5, _long_skeleton(), set(), symbol="BTCUSDT")  # i == confirm_idx
    assert sig is None


def test_no_signal_wait_period_break_consumes_key() -> None:
    """v3.point..confirm 区间内破 p2 → 拒绝并消耗 key。"""
    frame = _frame(
        [
            (10.0, 10.5, 10.0, 10.3),
            (10.4, 10.5, 10.1, 10.4),
            (10.2, 10.4, 10.0, 10.2),
            (10.8, 11.0, 10.6, 10.9),
            (10.8, 11.1, 10.6, 11.0),  # 4 v3 point 但 high 破 11.0
            (10.7, 10.9, 10.7, 10.8),
            (10.8, 10.9, 10.7, 10.8),
            (10.9, 11.2, 10.9, 11.1),
        ]
    )
    used: set[str] = set()
    sig = make_ds08_signal(frame, 7, _long_skeleton(), used, symbol="BTCUSDT")
    assert sig is None
    assert len(used) == 1  # key 被消耗


def test_no_signal_prev_break_consumes_key() -> None:
    """v3 确认后、触发前破 p2 → 拒绝并消耗 key。"""
    frame = _frame(
        [
            (10.0, 10.5, 10.0, 10.3),
            (10.4, 10.5, 10.1, 10.4),
            (10.2, 10.4, 10.0, 10.2),
            (10.8, 11.0, 10.6, 10.9),
            (10.8, 10.9, 10.6, 10.7),
            (10.7, 10.9, 10.7, 10.8),
            (10.9, 11.1, 10.8, 11.0),  # 6 已破 11.0
            (10.9, 11.2, 10.9, 11.1),
        ]
    )
    used: set[str] = set()
    sig = make_ds08_signal(frame, 7, _long_skeleton(), used, symbol="BTCUSDT")
    assert sig is None
    assert len(used) == 1


def test_no_signal_not_break_p2() -> None:
    frame = _frame(
        [
            (10.0, 10.5, 10.0, 10.3),
            (10.4, 10.5, 10.1, 10.4),
            (10.2, 10.4, 10.0, 10.2),
            (10.8, 11.0, 10.6, 10.9),
            (10.8, 10.9, 10.6, 10.7),
            (10.7, 10.9, 10.7, 10.8),
            (10.8, 10.9, 10.7, 10.8),
            (10.9, 10.95, 10.9, 11.0),  # 7 high=10.95 未破 11.0
        ]
    )
    sig = make_ds08_signal(frame, 7, _long_skeleton(), set(), symbol="BTCUSDT")
    assert sig is None


def test_no_signal_initial_stop_not_below_entry() -> None:
    """v3 >= p2 时 initial_stop >= entry → 拒绝。"""
    skeleton = [
        _node(0, 0, 10.0, "LOW"),
        _node(1, 1, 10.5, "HIGH"),
        _node(2, 2, 10.2, "LOW"),
        _node(3, 3, 11.0, "HIGH"),
        _node(4, 5, 11.5, "LOW"),  # v3=11.5 > p2=11.0（仍满足 v3>v2）但止损 >= 入场
    ]
    sig = make_ds08_signal(_long_frame(), 7, skeleton, set(), symbol="BTCUSDT")
    assert sig is None


# ---------------------------------------------------------------------------
# 成交 / 止损 / 移动止损
# ---------------------------------------------------------------------------

def test_entry_fill_long_short() -> None:
    class _L:  # noqa: N801
        side = 1
        entry_ref = 11.0

    class _S:  # noqa: N801
        side = -1
        entry_ref = 11.0

    long_row = pd.Series({"open": 11.2, "high": 11.3, "low": 11.1, "close": 11.2})
    assert entry_fill(long_row, _L()) == pytest.approx(11.2)  # max(open, ref)
    short_row = pd.Series({"open": 10.9, "high": 11.0, "low": 10.8, "close": 10.9})
    assert entry_fill(short_row, _S()) == pytest.approx(10.9)  # min(open, ref)


def test_check_stop_long_short() -> None:
    long_pos = {"side": 1, "stop": 10.8}
    assert check_stop(pd.Series({"open": 10.7, "low": 10.6, "high": 10.9}), long_pos) == (10.7, "gap_stop")
    assert check_stop(pd.Series({"open": 10.9, "low": 10.8, "high": 11.0}), long_pos) == (10.8, "stop")
    assert check_stop(pd.Series({"open": 11.0, "low": 10.9, "high": 11.1}), long_pos) == (None, None)

    short_pos = {"side": -1, "stop": 11.3}
    assert check_stop(pd.Series({"open": 11.4, "high": 11.5, "low": 11.3}), short_pos) == (11.4, "gap_stop")
    assert check_stop(pd.Series({"open": 11.2, "high": 11.3, "low": 11.1}), short_pos) == (11.3, "stop")
    assert check_stop(pd.Series({"open": 11.1, "high": 11.2, "low": 11.0}), short_pos) == (None, None)


def test_update_stop_moves_with_skeleton() -> None:
    long_pos = {"side": 1, "stop": 10.0}
    long_skeleton = [
        _node(0, 0, 10.0, "LOW"),
        _node(1, 1, 10.5, "HIGH"),
        _node(2, 2, 10.2, "LOW"),
        _node(3, 3, 11.0, "HIGH"),
        _node(4, 5, 10.8, "LOW"),
        _node(5, 6, 11.0, "HIGH"),  # 新峰
        _node(6, 7, 11.2, "LOW"),  # 新谷 → 止损抬升
    ]
    update_ds08_stop(long_pos, long_skeleton)
    assert long_pos["stop"] == pytest.approx(11.2)  # 最后 LOW

    short_pos = {"side": -1, "stop": 12.0}
    short_skeleton = [
        _node(0, 0, 12.0, "HIGH"),
        _node(1, 1, 11.5, "LOW"),
        _node(2, 2, 11.8, "HIGH"),
        _node(3, 3, 11.0, "LOW"),
        _node(4, 5, 11.3, "HIGH"),
        _node(5, 6, 11.0, "LOW"),
        _node(6, 7, 11.0, "HIGH"),  # 新峰 → 止损下移
    ]
    update_ds08_stop(short_pos, short_skeleton)
    assert short_pos["stop"] == pytest.approx(11.0)  # 最后 HIGH


def test_update_stop_empty_skeleton() -> None:
    pos = {"side": 1, "stop": 10.0}
    assert update_ds08_stop(pos, []) is pos


# ---------------------------------------------------------------------------
# 结构审计
# ---------------------------------------------------------------------------

def _clean_long_trade() -> dict:
    return {
        "direction": "long",
        "key": "BTCUSDT|LONG|4|3|11",
        "n1_type": "V", "n1_price": 10.0,
        "n2_type": "P", "n2_price": 10.5,
        "n3_type": "V", "n3_price": 10.2,
        "n4_type": "P", "n4_price": 11.0,
        "n5_type": "V", "n5_price": 10.8,
        "n5_confirm_idx": 5, "entry_idx": 7,
        "defense_price": 10.8, "attack_price": 11.0, "entry_price": 11.2,
    }


def _clean_short_trade() -> dict:
    return {
        "direction": "short",
        "key": "BTCUSDT|SHORT|4|3|11",
        "n1_type": "P", "n1_price": 12.0,
        "n2_type": "V", "n2_price": 11.5,
        "n3_type": "P", "n3_price": 11.8,
        "n4_type": "V", "n4_price": 11.0,
        "n5_type": "P", "n5_price": 11.3,
        "n5_confirm_idx": 5, "entry_idx": 7,
        "defense_price": 11.3, "attack_price": 11.0, "entry_price": 10.9,
    }


def test_audit_structure_clean_long_short() -> None:
    trades = pd.DataFrame([_clean_long_trade(), _clean_short_trade()])
    assert audit_ds08_structure(trades).empty


def test_audit_structure_bad_price_order() -> None:
    trade = _clean_long_trade()
    trade["n5_price"] = 9.9  # v3 < v1 → 谷底不抬高
    bad = audit_ds08_structure(pd.DataFrame([trade]))
    assert len(bad) == 1


def test_audit_structure_bad_roles() -> None:
    trade = _clean_long_trade()
    trade["n5_type"] = "P"  # 末位应为 V
    bad = audit_ds08_structure(pd.DataFrame([trade]))
    assert len(bad) == 1


def test_audit_structure_bad_defense_not_below_entry() -> None:
    trade = _clean_long_trade()
    trade["defense_price"] = 11.5  # 止损 >= 入场 → 非法
    bad = audit_ds08_structure(pd.DataFrame([trade]))
    assert len(bad) == 1


def test_audit_structure_duplicate_key() -> None:
    t1 = _clean_long_trade()
    t2 = _clean_long_trade()
    t2["entry_price"] = 11.3
    bad = audit_ds08_structure(pd.DataFrame([t1, t2]))
    assert len(bad) == 2


def test_audit_structure_empty() -> None:
    assert audit_ds08_structure(pd.DataFrame()).empty
