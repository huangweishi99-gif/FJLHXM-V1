from __future__ import annotations

import pandas as pd

from fengji_core.chart_line import chart_solid_hardened_nodes, hardened_node_excluded_from_solid
from fengji_core.os_engine import FengJiOSIdentityEngine, IdentityNode, RawNode


def test_failed_only_hardened_node_excluded() -> None:
    engine = FengJiOSIdentityEngine(gap=3)
    node = RawNode(20, 23, 80.0, "LOW")
    engine.hardened_nodes = [RawNode(10, 13, 100.0, "HIGH"), node, RawNode(30, 33, 90.0, "HIGH")]
    engine.identity_nodes = [
        IdentityNode(10, 13, 100.0, "HIGH", "BLUE_EXT", -1, "ok", "confirmed_raw"),
        IdentityNode(20, 23, 80.0, "LOW", "FAILED_LOW", -1, "not blue peak", "confirmed_raw"),
        IdentityNode(30, 33, 90.0, "HIGH", "BLUE_EXT", -1, "ok", "confirmed_raw"),
    ]
    assert hardened_node_excluded_from_solid(engine, node) is True


def test_camp_hardened_nodes_kept_in_order() -> None:
    engine = FengJiOSIdentityEngine(gap=3)
    engine.hardened_nodes = [
        RawNode(10, 13, 809.0, "HIGH"),
        RawNode(20, 23, 587.0, "LOW"),
        RawNode(30, 33, 694.0, "HIGH"),
        RawNode(40, 43, 691.0, "HIGH"),
    ]
    engine.identity_nodes = [
        IdentityNode(10, 13, 809.0, "HIGH", "RED_PEAK", 1, "", "confirmed_raw"),
        IdentityNode(20, 23, 587.0, "LOW", "BLUE_PEAK", -1, "", "confirmed_raw"),
        IdentityNode(30, 33, 694.0, "HIGH", "BLUE_EXT", -1, "", "confirmed_raw"),
        IdentityNode(40, 43, 691.0, "HIGH", "BLUE_EXT", -1, "", "confirmed_raw"),
    ]
    df = pd.DataFrame(
        {
            "date": pd.date_range("2026-01-01", periods=50, freq="D"),
            "open": 600.0,
            "high": 700.0,
            "low": 500.0,
            "close": 600.0,
        }
    )
    last_row = pd.Series({"camp": -1, "pending_turn": False})
    visible_dates = {pd.Timestamp(d).strftime("%Y-%m-%d") for d in df["date"]}
    solid = chart_solid_hardened_nodes(
        engine,
        df,
        last_row,
        visible_dates,
        lambda v: pd.Timestamp(v).strftime("%Y-%m-%d"),
    )
    assert len(solid) == 4
    assert [n.point_idx for n in solid] == [10, 20, 30, 40]


def test_identity_empty_hardened_low_stays_on_solid_line() -> None:
    """物理硬化点即使尚无红/蓝身份，也不能从实线中跳过（沪镍 5/26 类）。"""
    engine = FengJiOSIdentityEngine(gap=3)
    engine.hardened_nodes = [
        RawNode(10, 13, 155670.0, "HIGH"),
        RawNode(20, 23, 140650.0, "LOW"),
    ]
    engine.identity_nodes = [
        IdentityNode(10, 13, 155670.0, "HIGH", "RED_PEAK", 1, "", "confirmed_raw"),
    ]
    df = pd.DataFrame(
        {
            "date": pd.date_range("2026-05-01", periods=30, freq="D"),
            "open": 140000.0,
            "high": 156000.0,
            "low": 140000.0,
            "close": 143000.0,
        }
    )
    last_row = pd.Series({"camp": 1, "pending_turn": False})
    visible_dates = {pd.Timestamp(d).strftime("%Y-%m-%d") for d in df["date"]}
    solid = chart_solid_hardened_nodes(
        engine,
        df,
        last_row,
        visible_dates,
        lambda v: pd.Timestamp(v).strftime("%Y-%m-%d"),
    )
    assert len(solid) == 2
    assert solid[-1].point_idx == 20


def test_labelable_excludes_failed_from_camp_line_when_not_broken() -> None:
    from fengji_core.chart_line import labelable_identity_keys

    engine = FengJiOSIdentityEngine(gap=3)
    engine.hardened_nodes = [RawNode(5, 8, 50.0, "LOW")]
    engine.identity_nodes = [
        IdentityNode(5, 8, 50.0, "LOW", "FAILED_LOW", -1, "probe", "confirmed_raw"),
    ]
    last_row = pd.Series(
        {
            "camp": -1,
            "pending_turn": False,
            "blue_peak_price": float("nan"),
            "blue_ext_price": float("nan"),
        }
    )
    keys = labelable_identity_keys(engine.identity_nodes, engine.hardened_nodes, last_row, [], 0, 10)
    assert (5, "FAILED_LOW") in keys
