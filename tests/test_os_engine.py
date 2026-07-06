from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from fengji_core.data import load_ohlcv_for_engine
from fengji_core.os_engine import BLUE, NEUTRAL, RED, FengJiOSIdentityEngine, IdentityNode, RawNode, build_identity_line, role


ROOT = Path(__file__).resolve().parents[1]
SAMPLE_CSV = ROOT / "data" / "sample_ohlcv.csv"


@pytest.fixture
def sample_df() -> pd.DataFrame:
    if not SAMPLE_CSV.exists():
        pytest.skip(f"missing sample data: {SAMPLE_CSV}")
    return load_ohlcv_for_engine(SAMPLE_CSV, atr_window=14)


def test_os_engine_runs_on_sample(sample_df: pd.DataFrame) -> None:
    engine = FengJiOSIdentityEngine(gap=3).run(sample_df)
    frame = engine.to_frame(sample_df)
    assert len(engine.raw_nodes) > 0
    assert len(engine.hardened_nodes) > 0
    assert "camp" in frame.columns
    assert set(frame["camp"].dropna().unique()).issubset({RED, BLUE, NEUTRAL})


def test_hardened_nodes_alternate(sample_df: pd.DataFrame) -> None:
    engine = FengJiOSIdentityEngine(gap=3).run(sample_df)
    types = [node.raw_type for node in engine.hardened_nodes]
    for idx in range(1, len(types)):
        assert types[idx] != types[idx - 1]


def test_hardened_nodes_price_alternates(sample_df: pd.DataFrame) -> None:
    """连线必须满足高-低-高-低价格节奏（宪法 3.3 峰极交替）。"""
    engine = FengJiOSIdentityEngine(gap=3).run(sample_df)
    for idx in range(1, len(engine.hardened_nodes)):
        prev = engine.hardened_nodes[idx - 1]
        curr = engine.hardened_nodes[idx]
        if prev.raw_type == "HIGH":
            assert curr.raw_type == "LOW"
            assert curr.price < prev.price
        else:
            assert curr.raw_type == "HIGH"
            assert curr.price > prev.price


def test_reject_low_not_below_prior_high() -> None:
    engine = FengJiOSIdentityEngine(gap=3)
    engine.hardened_nodes = [RawNode(point_idx=89, confirm_idx=92, price=3129.0, raw_type="HIGH")]
    invalid_low = RawNode(point_idx=103, confirm_idx=106, price=3140.0, raw_type="LOW")
    assert engine.update_hardened_nodes(invalid_low) is False
    assert engine.hardened_nodes == [RawNode(point_idx=89, confirm_idx=92, price=3129.0, raw_type="HIGH")]


def test_reject_high_not_above_prior_low() -> None:
    engine = FengJiOSIdentityEngine(gap=3)
    engine.hardened_nodes = [RawNode(point_idx=10, confirm_idx=13, price=20.0, raw_type="LOW")]
    invalid_high = RawNode(point_idx=14, confirm_idx=17, price=19.0, raw_type="HIGH")
    assert engine.update_hardened_nodes(invalid_high) is False
    assert len(engine.hardened_nodes) == 1


def test_hardened_gap_at_least_three(sample_df: pd.DataFrame) -> None:
    engine = FengJiOSIdentityEngine(gap=3).run(sample_df)
    for idx in range(1, len(engine.hardened_nodes)):
        prev = engine.hardened_nodes[idx - 1]
        curr = engine.hardened_nodes[idx]
        if curr.source == "urgent_gap":
            assert curr.point_idx - prev.point_idx < 3
            assert curr.arbitration in {"urgent_gap_down", "urgent_gap_up"}
        else:
            assert curr.point_idx - prev.point_idx >= 3


def test_identity_line_roles_alternate(sample_df: pd.DataFrame) -> None:
    engine = FengJiOSIdentityEngine(gap=3).run(sample_df)
    line = build_identity_line(engine.identity_nodes)
    roles = [role(node.identity) for node in line if role(node.identity) != "FAILED"]
    for idx in range(1, len(roles)):
        assert roles[idx] != roles[idx - 1]


def test_gap_rejected_raw_node_does_not_update_identity() -> None:
    df = pd.DataFrame(
        {
            "date": pd.date_range("2026-01-01", periods=16, freq="D"),
            "open": [12.0] * 16,
            "high": [20.0] * 16,
            "low": [11.0] * 16,
            "close": [12.0] * 16,
        }
    )
    engine = FengJiOSIdentityEngine(gap=3)
    engine.camp = RED
    engine.hardened_nodes = [RawNode(point_idx=10, confirm_idx=13, price=20.0, raw_type="HIGH")]
    engine.red_peak = IdentityNode(10, 13, 20.0, "HIGH", "RED_PEAK", RED)
    engine.red_ext = IdentityNode(7, 10, 10.0, "LOW", "RED_EXT", RED)

    rejected_low = RawNode(point_idx=12, confirm_idx=15, price=15.0, raw_type="LOW")
    engine.detect_raw_33_node = lambda _df, _i: rejected_low  # type: ignore[method-assign]

    engine.process_bar(df, 15)

    assert engine.hardened_nodes == [RawNode(point_idx=10, confirm_idx=13, price=20.0, raw_type="HIGH")]
    assert engine.red_ext == IdentityNode(7, 10, 10.0, "LOW", "RED_EXT", RED)
    assert all(node.point_idx != 12 for node in engine.identity_nodes)


def test_urgent_down_gap_node_is_hardened_and_tagged() -> None:
    df = pd.DataFrame(
        {
            "date": pd.date_range("2026-01-01", periods=16, freq="D"),
            "open": [12.0] * 16,
            "high": [20.0] * 16,
            "low": [11.0] * 16,
            "close": [12.0] * 16,
        }
    )
    df.loc[11, ["open", "high", "low", "close"]] = [19.0, 20.0, 11.0, 12.0]
    df.loc[12, ["open", "high", "low", "close"]] = [12.0, 13.0, 11.0, 11.5]

    engine = FengJiOSIdentityEngine(gap=3)
    engine.camp = RED
    engine.camp_confirmed = RED
    engine.hardened_nodes = [RawNode(point_idx=10, confirm_idx=13, price=20.0, raw_type="HIGH")]
    engine.red_peak = IdentityNode(10, 13, 20.0, "HIGH", "RED_PEAK", RED)
    engine.red_ext = IdentityNode(7, 10, 10.0, "LOW", "RED_EXT", RED)

    urgent_low = RawNode(point_idx=12, confirm_idx=15, price=11.0, raw_type="LOW")
    engine.detect_raw_33_node = lambda _df, _i: urgent_low  # type: ignore[method-assign]

    engine.process_bar(df, 15)

    accepted = engine.hardened_nodes[-1]
    assert accepted.point_idx == 12
    assert accepted.source == "urgent_gap"
    assert accepted.arbitration == "urgent_gap_down"
    assert engine.emergency_nodes == [accepted]
    assert engine.red_ext is not None
    assert engine.red_ext.point_idx == 12
    assert engine.camp == RED


def test_urgent_down_gap_breaking_red_ext_turns_blue() -> None:
    df = pd.DataFrame(
        {
            "date": pd.date_range("2026-01-01", periods=15, freq="D"),
            "open": [12.0] * 15,
            "high": [20.0] * 15,
            "low": [11.0] * 15,
            "close": [12.0] * 15,
        }
    )
    df.loc[11, ["open", "high", "low", "close"]] = [19.0, 20.0, 8.0, 9.0]
    df.loc[14, ["open", "high", "low", "close"]] = [10.0, 11.0, 8.0, 8.5]

    engine = FengJiOSIdentityEngine(gap=3)
    engine.camp = RED
    engine.camp_confirmed = RED
    engine.hardened_nodes = [RawNode(point_idx=10, confirm_idx=13, price=20.0, raw_type="HIGH")]
    engine.red_peak = IdentityNode(10, 13, 20.0, "HIGH", "RED_PEAK", RED)
    engine.red_ext = IdentityNode(7, 10, 10.0, "LOW", "RED_EXT", RED)

    urgent_break = RawNode(point_idx=11, confirm_idx=14, price=8.0, raw_type="LOW")
    engine.detect_raw_33_node = lambda _df, _i: urgent_break  # type: ignore[method-assign]

    engine.process_bar(df, 14)

    assert engine.hardened_nodes[-1].source == "urgent_gap"
    assert engine.turns[-1].turn == "RED_TO_BLUE"
    assert engine.turns[-1].broken_identity == "RED_EXT"
    assert engine.camp == BLUE
    assert engine.camp_confirmed == BLUE


def test_turn_without_failed_peak_does_not_flip_camp() -> None:
    """无假蓝峰 f 时，刺破蓝极不构成 OS 转势（camp 不变）。"""
    df = pd.DataFrame(
        {
            "date": pd.date_range("2026-01-01", periods=8, freq="D"),
            "open": [10.0, 10.5, 11.0, 10.8, 10.2, 9.8, 9.5, 9.3],
            "high": [10.5, 11.0, 11.2, 10.9, 10.0, 9.9, 9.6, 11.5],
            "low": [9.5, 10.0, 10.5, 10.0, 9.5, 9.0, 8.8, 8.5],
            "close": [10.2, 10.8, 10.7, 10.3, 9.7, 9.2, 9.1, 8.9],
        }
    )
    engine = FengJiOSIdentityEngine(gap=3)
    engine.camp = BLUE
    engine.camp_confirmed = BLUE
    # 蓝峰尚未在蓝极之后确立，不构成 C 类急转势
    engine.blue_peak = IdentityNode(3, 6, 9.0, "LOW", "BLUE_PEAK", BLUE)
    engine.blue_ext = IdentityNode(5, 7, 11.0, "HIGH", "BLUE_EXT", BLUE)
    engine.last_failed_low = None
    engine.check_transition(7, df.iloc[7]["date"], 11.5, 8.5)

    assert engine.camp == BLUE
    assert engine.camp_confirmed == BLUE
    assert len(engine.turns) == 0


def test_direct_blue_to_red_turn_redefines_blue_peak_as_red_ext() -> None:
    """N字突破04：C 类/整根脱离蓝转红且无假蓝峰时，启动前蓝峰直接重定义为红极（防守极不得为空）。"""
    engine = FengJiOSIdentityEngine(gap=3)
    engine.camp = BLUE
    engine.camp_confirmed = BLUE
    engine.blue_ext = IdentityNode(5, 7, 11.0, "HIGH", "BLUE_EXT", BLUE)
    engine.blue_peak = IdentityNode(8, 10, 8.0, "LOW", "BLUE_PEAK", BLUE)
    engine.last_failed_low = None

    engine.check_transition(11, pd.Timestamp("2026-01-12"), high=11.5, low=8.5)

    assert engine.camp == RED
    assert engine.camp_confirmed == RED
    assert engine.pending_turn is False
    assert engine.turns[-1].turn == "BLUE_TO_RED"
    # 旧规则曾要求“无假蓝峰则不重定义”，N04 推翻：蓝峰 8 必须成为新红极。
    assert engine.turns[-1].redefined_from_idx == 8
    assert engine.turns[-1].redefined_to == "RED_EXT"
    assert engine.red_ext is not None
    assert engine.red_ext.point_idx == 8
    assert engine.red_ext.price == 8.0
    assert engine.red_ext.source == "redefined"


def test_direct_red_to_blue_turn_redefines_red_peak_as_blue_ext() -> None:
    """红转蓝镜像：C 类/整根脱离且无假红峰时，启动前红峰重定义为蓝极。"""
    engine = FengJiOSIdentityEngine(gap=3)
    engine.camp = RED
    engine.camp_confirmed = RED
    engine.red_ext = IdentityNode(5, 7, 9.0, "LOW", "RED_EXT", RED)
    engine.red_peak = IdentityNode(8, 10, 12.0, "HIGH", "RED_PEAK", RED)
    engine.last_failed_high = None

    engine.check_transition(11, pd.Timestamp("2026-01-12"), high=11.5, low=8.5)

    assert engine.camp == BLUE
    assert engine.turns[-1].turn == "RED_TO_BLUE"
    assert engine.turns[-1].redefined_from_idx == 8
    assert engine.turns[-1].redefined_to == "BLUE_EXT"
    assert engine.blue_ext is not None
    assert engine.blue_ext.point_idx == 8
    assert engine.blue_ext.price == 12.0
    assert engine.blue_ext.source == "redefined"


def test_n04_quick_reversal_blue_peak_becomes_red_ext_then_breaks(tmp_path: Path) -> None:
    """N字突破04 / BNB 复现：假红峰→蓝峰→红峰(创新高)后蓝峰成红极，破红极再红转蓝。"""
    csv = ROOT / "data" / "1d" / "BNBUSDT.csv"
    if not csv.exists():
        pytest.skip(f"missing {csv}")
    raw = pd.read_csv(csv)
    if "timestamp" in raw.columns:
        raw = raw.rename(columns={"timestamp": "date"})
    raw["date"] = pd.to_datetime(raw["date"])
    engine = FengJiOSIdentityEngine(gap=3).run(raw)
    frame = engine.to_frame(raw)
    frame["d"] = pd.to_datetime(frame["date"]).dt.strftime("%Y-%m-%d")
    by_date = frame.set_index("d")

    # 5/28 红转蓝（短暂蓝），5/31 蓝转红创新高
    assert int(by_date.loc["2026-05-28", "camp"]) == BLUE
    assert int(by_date.loc["2026-05-31", "camp"]) == RED
    # 5/31~6/2：628.22（5/28 蓝峰）重定义为红极
    assert abs(float(by_date.loc["2026-06-01", "red_ext_price"]) - 628.22) < 0.05
    assert int(by_date.loc["2026-06-02", "camp"]) == RED
    # 6/3 收盘/影线跌破 628.22 → 红转蓝；6/7 处于蓝营（DS01 做多为逆势）
    assert int(by_date.loc["2026-06-03", "camp"]) == BLUE
    assert int(by_date.loc["2026-06-07", "camp"]) == BLUE
    turns = {(str(pd.to_datetime(t.date).date()), t.turn) for t in engine.turns}
    assert ("2026-06-03", "RED_TO_BLUE") in turns


def test_redefined_failed_low_blue_to_red_confirms_current_camp() -> None:
    engine = FengJiOSIdentityEngine(gap=3)
    engine.camp = BLUE
    engine.camp_confirmed = BLUE
    engine.blue_ext = IdentityNode(5, 7, 11.0, "HIGH", "BLUE_EXT", BLUE)
    engine.blue_peak = IdentityNode(8, 10, 8.0, "LOW", "BLUE_PEAK", BLUE)
    engine.last_failed_low = RawNode(9, 12, 9.5, "LOW")

    engine.check_transition(13, pd.Timestamp("2026-01-14"), high=11.5, low=8.5)

    assert engine.camp == RED
    assert engine.camp_confirmed == RED
    assert engine.pending_turn is False
    assert engine.red_ext == IdentityNode(9, 12, 9.5, "LOW", "RED_EXT", RED, "failed low redefined to red ext", "redefined")
    assert engine.turns[-1].redefined_to == "RED_EXT"


def test_legacy_mismatched_state_normalizes_confirmed_camp() -> None:
    engine = FengJiOSIdentityEngine(gap=3)
    state = {
        "version": 1,
        "gap": 3,
        "processed_len": 0,
        "camp": RED,
        "camp_confirmed": BLUE,
        "pending_turn": True,
        "turn_idx": 10,
        "turn_had_redefine": False,
        "raw_nodes": [],
        "hardened_nodes": [],
        "identity_nodes": [],
        "turns": [],
        "logs": [],
    }

    engine.load_state(state)

    assert engine.camp == RED
    assert engine.camp_confirmed == RED
    assert engine.pending_turn is False


def test_incremental_state_matches_full_run(sample_df: pd.DataFrame) -> None:
    split = max(10, len(sample_df) // 2)
    prefix = sample_df.iloc[:split].reset_index(drop=True)

    full_engine = FengJiOSIdentityEngine(gap=3).run(sample_df)
    prefix_engine = FengJiOSIdentityEngine(gap=3).run(prefix)
    state = json.loads(json.dumps(prefix_engine.to_state(), default=str))
    incremental_engine = FengJiOSIdentityEngine(gap=3).run_from_state(sample_df, state)

    incremental_turns = incremental_engine.export_turns().copy()
    full_turns = full_engine.export_turns().copy()
    if "date" in incremental_turns:
        normalize_date = lambda series: pd.to_datetime(series, errors="coerce").dt.strftime("%Y-%m-%d %H:%M:%S")
        incremental_turns["date"] = normalize_date(incremental_turns["date"])
        full_turns["date"] = normalize_date(full_turns["date"])

    assert incremental_engine.raw_nodes == full_engine.raw_nodes
    assert incremental_engine.identity_nodes == full_engine.identity_nodes
    assert incremental_turns.fillna("__NA__").to_dict("records") == full_turns.fillna("__NA__").to_dict("records")
    assert incremental_engine.hardened_nodes == full_engine.hardened_nodes
    assert incremental_engine.camp == full_engine.camp
    assert incremental_engine.camp_confirmed == full_engine.camp_confirmed
