"""DS06 外扩峰式核心单测：转势后 D 攻击节点 + E 防御节点 + 外扩突破触发。

覆盖：LONG/SHORT 触发、无转势/无结构不触发、WAIT_E 破 D 重置、
E 顺序与价格约束、成交/止损/移动止损、结构审计。
"""
from __future__ import annotations

import pandas as pd
import pytest

from fengji_core.ds06 import (
    audit_ds06_structure,
    check_stop,
    detect_ds06_signals,
    entry_fill,
    update_ds06_stop,
)
from fengji_core.os_engine import RawNode, TurnEvent


def _frame(rows: list[tuple[float, float, float, float, float]]) -> pd.DataFrame:
    return pd.DataFrame(rows, columns=["open", "high", "low", "close", "volume"])


def _turn(idx: int, turn_type: str, broken_price: float) -> TurnEvent:
    return TurnEvent(
        idx=idx,
        date=pd.Timestamp("2026-08-13"),
        turn=turn_type,
        broken_identity="L_Peak" if turn_type == "BLUE_TO_RED" else "H_Peak",
        broken_price=broken_price,
        break_price=broken_price,
        broken_point_idx=idx - 1,
        redefined_from_idx=None,
        redefined_to=None,
    )


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


def _hardened(by_confirm: dict[int, list[RawNode]], n_bars: int) -> list[list[RawNode]]:
    """只把节点放在其确认 bar（confirm_idx==i），匹配 _new_hardened_nodes_at 语义。"""
    return [by_confirm.get(i, []) for i in range(n_bars)]


# ---------------------------------------------------------------------------
# LONG / SHORT 正常触发
# ---------------------------------------------------------------------------

def test_long_signal_blue_to_red_external_break() -> None:
    turn = _turn(1, "BLUE_TO_RED", broken_price=12.0)
    d = _node(2, 3, price=10.0, raw_type="HIGH")
    e = _node(4, 5, price=8.0, raw_type="LOW")
    df = _frame(
        [
            (10.0, 10.5, 9.8, 10.2, 100),  # 0 转势前
            (12.0, 12.0, 11.0, 11.5, 100),  # 1 转势（旧防御 12.0 被破）
            (10.1, 10.2, 10.0, 10.1, 100),  # 2
            (10.0, 10.0, 9.9, 10.0, 100),  # 3 D 确认（high 不破 10.0）
            (9.9, 9.9, 9.8, 9.9, 100),  # 4 不破 D
            (9.8, 9.8, 9.7, 9.8, 100),  # 5 E 确认（LOW 8.0）
            (9.7, 9.9, 9.0, 9.5, 100),  # 6 未破 D(10.0)
            (10.0, 10.2, 9.6, 10.1, 100),  # 7 破 D → 触发
        ]
    )
    hardened = _hardened({3: [d], 5: [e]}, len(df))

    signals = detect_ds06_signals(df, [turn], hardened)

    assert len(signals) == 1
    sig = signals[0]
    assert sig.side == 1
    assert sig.pattern == "DS06 Blue-to-Red External Peak"
    assert sig.turn_type == "BLUE_TO_RED"
    assert sig.signal_camp == 1
    assert sig.activate_idx == 7
    assert sig.entry_ref == 10.0
    assert sig.d_idx == 2
    assert sig.d_confirm_idx == 3
    assert sig.d_price == 10.0
    assert sig.e_idx == 4
    assert sig.e_confirm_idx == 5
    assert sig.e_price == 8.0
    assert sig.old_extreme_price == 12.0
    # initial_stop = low[6:8].min()
    assert sig.initial_stop == pytest.approx(9.0)


def test_short_signal_red_to_blue_external_break() -> None:
    turn = _turn(1, "RED_TO_BLUE", broken_price=8.0)
    d = _node(2, 3, price=8.0, raw_type="LOW")
    e = _node(4, 5, price=10.0, raw_type="HIGH")
    df = _frame(
        [
            (10.0, 10.5, 9.8, 10.2, 100),
            (8.5, 9.0, 8.0, 8.2, 100),  # 1 转势（旧防御 8.0 被破）
            (8.4, 8.6, 8.2, 8.5, 100),
            (8.5, 8.7, 8.1, 8.2, 100),  # 3 D 确认
            (8.3, 8.5, 8.0, 8.1, 100),
            (8.4, 10.0, 8.3, 9.8, 100),  # 5 E 确认（HIGH 10.0）
            (9.6, 9.9, 9.0, 9.2, 100),  # 6 未破 D(8.0)
            (8.1, 8.3, 7.8, 7.9, 100),  # 7 破 D → 触发
        ]
    )
    hardened = _hardened({3: [d], 5: [e]}, len(df))

    signals = detect_ds06_signals(df, [turn], hardened)

    assert len(signals) == 1
    sig = signals[0]
    assert sig.side == -1
    assert sig.pattern == "DS06 Red-to-Blue External Peak"
    assert sig.turn_type == "RED_TO_BLUE"
    assert sig.signal_camp == -1
    assert sig.activate_idx == 7
    assert sig.entry_ref == 8.0
    assert sig.initial_stop == pytest.approx(9.9)  # high[6:8].max()


# ---------------------------------------------------------------------------
# 不触发场景
# ---------------------------------------------------------------------------

def test_no_signal_without_turn() -> None:
    d = _node(2, 3, price=10.0, raw_type="HIGH")
    e = _node(4, 5, price=8.0, raw_type="LOW")
    df = _frame(
        [
            (10.0, 10.5, 9.8, 10.2, 100),
            (10.0, 10.2, 9.9, 10.1, 100),
            (10.0, 10.6, 9.9, 10.4, 100),
            (10.0, 10.5, 9.9, 10.2, 100),
            (10.0, 10.3, 9.9, 10.1, 100),
            (10.0, 10.4, 9.9, 10.2, 100),
            (10.0, 10.6, 9.9, 10.4, 100),
            (10.0, 10.8, 9.9, 10.6, 100),
        ]
    )
    hardened = _hardened({3: [d], 5: [e]}, len(df))

    assert detect_ds06_signals(df, [], hardened) == []


def test_no_signal_turn_only_no_d_or_e() -> None:
    turn = _turn(1, "BLUE_TO_RED", broken_price=12.0)
    df = _frame(
        [
            (10.0, 10.5, 9.8, 10.2, 100),
            (12.0, 12.0, 11.0, 11.5, 100),
            (10.4, 10.6, 10.2, 10.5, 100),
            (10.5, 10.8, 10.3, 10.6, 100),
            (10.6, 10.9, 10.4, 10.7, 100),
            (10.7, 11.0, 10.5, 10.8, 100),
        ]
    )
    hardened = _hardened({}, len(df))

    assert detect_ds06_signals(df, [turn], hardened) == []


def test_no_signal_break_before_e_confirm_resets_wait_d() -> None:
    """WAIT_E 阶段破 D → 重置 WAIT_D；无新 D/E → 不触发。"""
    turn = _turn(1, "BLUE_TO_RED", broken_price=12.0)
    d = _node(2, 3, price=10.0, raw_type="HIGH")
    df = _frame(
        [
            (10.0, 10.5, 9.8, 10.2, 100),
            (12.0, 12.0, 11.0, 11.5, 100),
            (10.2, 10.4, 10.0, 10.3, 100),
            (10.1, 10.3, 9.9, 10.0, 100),  # 3 D 确认
            (10.4, 10.8, 10.3, 10.6, 100),  # 4 破 D → 重置 WAIT_D
            (10.5, 10.9, 10.4, 10.7, 100),  # 5 无新 D
            (10.6, 11.0, 10.5, 10.8, 100),
            (10.7, 11.2, 10.6, 11.0, 100),
        ]
    )
    hardened = _hardened({3: [d]}, len(df))

    assert detect_ds06_signals(df, [turn], hardened) == []


def test_no_signal_d_not_after_turn() -> None:
    """D 必须 point_idx/confirm_idx 都在转势之后。"""
    turn = _turn(1, "BLUE_TO_RED", broken_price=12.0)
    d = _node(1, 1, price=10.0, raw_type="HIGH")  # point_idx == turn.idx → 非法
    e = _node(2, 3, price=8.0, raw_type="LOW")
    df = _frame(
        [
            (10.0, 10.5, 9.8, 10.2, 100),
            (12.0, 12.0, 11.0, 11.5, 100),
            (10.2, 10.4, 10.0, 10.3, 100),
            (10.1, 10.3, 9.9, 10.0, 100),
            (10.0, 10.2, 9.9, 10.1, 100),
            (9.9, 10.1, 9.8, 9.9, 100),
            (9.8, 9.9, 9.0, 9.5, 100),
            (10.0, 10.2, 9.6, 10.1, 100),
        ]
    )
    hardened = _hardened({1: [d], 3: [e]}, len(df))

    assert detect_ds06_signals(df, [turn], hardened) == []


def test_no_signal_e_wrong_raw_type_for_long() -> None:
    """LONG 中 E 必须是 LOW；HIGH 节点不进入 WAIT_F。"""
    turn = _turn(1, "BLUE_TO_RED", broken_price=12.0)
    d = _node(2, 3, price=10.0, raw_type="HIGH")
    wrong_e = _node(4, 5, price=8.0, raw_type="HIGH")  # 类型错误
    df = _frame(
        [
            (10.0, 10.5, 9.8, 10.2, 100),
            (12.0, 12.0, 11.0, 11.5, 100),
            (10.1, 10.2, 10.0, 10.1, 100),
            (10.0, 10.0, 9.9, 10.0, 100),  # 3 D 确认
            (9.9, 9.9, 9.8, 9.9, 100),
            (9.9, 10.0, 9.8, 9.9, 100),  # 5 HIGH 节点，且 high=10.0 未破 D → 走类型检查
            (9.8, 9.9, 9.0, 9.5, 100),
            (10.0, 10.2, 9.6, 10.1, 100),
        ]
    )
    hardened = _hardened({3: [d], 5: [wrong_e]}, len(df))

    assert detect_ds06_signals(df, [turn], hardened) == []


def test_second_turn_replaces_active() -> None:
    """新的转势覆盖旧的 active 状态。"""
    turn1 = _turn(1, "BLUE_TO_RED", broken_price=12.0)
    turn2 = _turn(4, "RED_TO_BLUE", broken_price=8.0)
    d = _node(2, 3, price=10.0, raw_type="HIGH")
    df = _frame(
        [
            (10.0, 10.5, 9.8, 10.2, 100),
            (12.0, 12.0, 11.0, 11.5, 100),
            (10.2, 10.4, 10.0, 10.3, 100),
            (10.1, 10.3, 9.9, 10.0, 100),
            (8.5, 9.0, 8.0, 8.2, 100),  # 4 第二转势
            (8.4, 8.6, 8.2, 8.5, 100),
            (8.3, 8.5, 8.0, 8.1, 100),
            (10.0, 10.2, 9.6, 10.1, 100),  # 破旧 D(10.0) 但状态已被第二转势覆盖
        ]
    )
    hardened = _hardened({3: [d]}, len(df))

    assert detect_ds06_signals(df, [turn1, turn2], hardened) == []


# ---------------------------------------------------------------------------
# 成交 / 止损 / 移动止损
# ---------------------------------------------------------------------------

def test_entry_fill_long_short() -> None:
    long_row = pd.Series({"open": 10.5, "high": 10.6, "low": 10.4, "close": 10.5})

    class _S:  # noqa: N801
        side = 1
        entry_ref = 10.0

    class _S2:  # noqa: N801
        side = -1
        entry_ref = 8.0

    assert entry_fill(long_row, _S()) == pytest.approx(10.5)  # max(open, ref)
    short_row = pd.Series({"open": 8.3, "high": 8.4, "low": 8.2, "close": 8.3})
    assert entry_fill(short_row, _S2()) == pytest.approx(8.0)  # min(open, ref)


def test_entry_fill_respects_entry_ref() -> None:
    class _S:  # noqa: N801
        side = 1
        entry_ref = 10.0

    row = pd.Series({"open": 9.8, "high": 10.2, "low": 9.7, "close": 10.0})
    assert entry_fill(row, _S()) == pytest.approx(10.0)  # 缺口高开按 entry_ref


def test_check_stop_long() -> None:
    pos = {"side": 1, "stop": 9.5}
    gap = pd.Series({"open": 9.4, "high": 9.6, "low": 9.3, "close": 9.4})
    assert check_stop(gap, pos) == (9.4, "gap_stop")
    hit = pd.Series({"open": 9.6, "high": 9.7, "low": 9.5, "close": 9.6})
    assert check_stop(hit, pos) == (9.5, "stop")
    ok = pd.Series({"open": 9.8, "high": 9.9, "low": 9.6, "close": 9.8})
    assert check_stop(ok, pos) == (None, None)


def test_check_stop_short() -> None:
    pos = {"side": -1, "stop": 10.5}
    gap = pd.Series({"open": 10.6, "high": 10.8, "low": 10.5, "close": 10.7})
    assert check_stop(gap, pos) == (10.6, "gap_stop")
    hit = pd.Series({"open": 10.4, "high": 10.6, "low": 10.3, "close": 10.5})
    assert check_stop(hit, pos) == (10.5, "stop")
    ok = pd.Series({"open": 10.3, "high": 10.4, "low": 10.2, "close": 10.3})
    assert check_stop(ok, pos) == (None, None)


def test_update_stop_tightens_long_and_short() -> None:
    df = _frame(
        [
            (10.0, 10.4, 9.9, 10.2, 100),
            (10.2, 10.6, 10.1, 10.5, 100),
            (10.5, 10.8, 10.3, 10.7, 100),
        ]
    )
    long_pos = {"side": 1, "stop": 9.5}
    update_ds06_stop(long_pos, df, 2)
    assert long_pos["stop"] == pytest.approx(9.9)  # low[0:3].min()=9.9 > 9.5

    short_pos = {"side": -1, "stop": 10.9}
    update_ds06_stop(short_pos, df, 2)
    # start=max(0,2-3)=0, high[0:3].max()=10.8 → stop=min(10.9,10.8)=10.8
    assert short_pos["stop"] == pytest.approx(10.8)


# ---------------------------------------------------------------------------
# 结构审计
# ---------------------------------------------------------------------------

def _clean_long_trade() -> dict:
    return {
        "direction": "long",
        "turn_type": "BLUE_TO_RED",
        "signal_camp": 1,
        "d_price": 10.0,
        "e_price": 8.0,
        "turn_idx": 1,
        "d_idx": 2,
        "e_idx": 4,
        "entry_idx": 7,
        "d_confirm_idx": 3,
        "e_confirm_idx": 5,
    }


def test_audit_structure_clean_long_short() -> None:
    trades = pd.DataFrame([_clean_long_trade(), {
        "direction": "short",
        "turn_type": "RED_TO_BLUE",
        "signal_camp": -1,
        "d_price": 8.0,
        "e_price": 10.0,
        "turn_idx": 1,
        "d_idx": 2,
        "e_idx": 4,
        "entry_idx": 7,
        "d_confirm_idx": 3,
        "e_confirm_idx": 5,
    }])
    assert audit_ds06_structure(trades).empty


def test_audit_structure_bad_d_price_le_e_price() -> None:
    trade = _clean_long_trade()
    trade["d_price"] = 8.0
    trade["e_price"] = 8.0
    bad = audit_ds06_structure(pd.DataFrame([trade]))
    assert len(bad) == 1
    assert bad.iloc[0]["d_price"] == 8.0


def test_audit_structure_bad_order() -> None:
    trade = _clean_long_trade()
    trade["e_idx"] = 1  # e 在 turn 之前 → 顺序非法
    bad = audit_ds06_structure(pd.DataFrame([trade]))
    assert len(bad) == 1


def test_audit_structure_bad_turn_type() -> None:
    trade = _clean_long_trade()
    trade["turn_type"] = "RED_TO_BLUE"  # long 却标 RED_TO_BLUE
    bad = audit_ds06_structure(pd.DataFrame([trade]))
    assert len(bad) == 1


def test_audit_structure_empty() -> None:
    assert audit_ds06_structure(pd.DataFrame()).empty
