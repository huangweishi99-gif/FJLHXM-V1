from __future__ import annotations

import json

import pandas as pd

from fengji_core.fill_supervision import (
    audit_ds01_fill,
    infer_is_add,
    infer_record_timeframe,
    normalize_entry_date,
    parse_ds08_setup_key,
    parse_side,
    parse_signal_date_from_setup_key,
    resolve_fill_entry_date,
)


class MockEngine:
    def __init__(self, hardened: list[list] | None = None):
        self.hardened_by_bar = hardened or []


def test_parse_side_variants() -> None:
    assert parse_side("long") == 1
    assert parse_side("SHORT") == -1
    assert parse_side(1) == 1


def test_infer_is_add_from_setup() -> None:
    assert infer_is_add({"setup": "DS01 add cuogun"}) is True
    assert infer_is_add({"setup": "initial cuogun"}) is False


def test_audit_ds01_valid_long() -> None:
    dates = pd.date_range("2026-01-01", periods=4, freq="D")
    os_df = pd.DataFrame(
        {
            "date": dates,
            "open": [100.0, 101.0, 102.0, 103.0],
            "high": [101.0, 103.0, 104.5, 105.0],
            "low": [99.0, 100.0, 101.5, 102.0],
            "close": [100.5, 102.0, 104.0, 104.5],
            "camp": [1, 1, 1, 1],
            "active_low": [98.0, 98.0, 98.0, 98.0],
            "active_high": [102.0, 102.0, 102.0, 102.0],
        }
    )
    engine = MockEngine(hardened=[[], [], [], []])

    result = audit_ds01_fill(
        side=1,
        entry_date=dates[2],
        trigger_price=103.0,
        stop_price=100.0,
        left_count=0,
        os_df=os_df,
        engine=engine,
        is_add=False,
        symbol="RB",
    )

    assert result.verdict == "valid"
    assert result.issues == []


def test_audit_ds01_blocks_missing_red_defense() -> None:
    dates = pd.date_range("2026-01-01", periods=4, freq="D")
    os_df = pd.DataFrame(
        {
            "date": dates,
            "open": [100.0, 101.0, 102.0, 103.0],
            "high": [101.0, 103.0, 104.5, 105.0],
            "low": [99.0, 100.0, 101.5, 102.0],
            "close": [100.5, 102.0, 104.0, 104.5],
            "camp": [1, 1, 1, 1],
            "active_low": [float("nan"), float("nan"), float("nan"), float("nan")],
            "active_high": [102.0, 102.0, 102.0, 102.0],
        }
    )
    engine = MockEngine(hardened=[[], [], [], []])

    result = audit_ds01_fill(
        side=1,
        entry_date=dates[2],
        trigger_price=103.0,
        stop_price=100.0,
        left_count=0,
        os_df=os_df,
        engine=engine,
        symbol="RB",
    )

    assert result.verdict == "invalid"
    assert any("os_defense_missing" in issue for issue in result.issues)


def test_parse_signal_date_from_setup_key() -> None:
    ts = parse_signal_date_from_setup_key("AGUSDT|DS01|SHORT|signal=20260526160000|trigger=18135")
    assert ts == pd.Timestamp("2026-05-26 16:00:00")


def test_resolve_fill_entry_date_prefers_fill_time() -> None:
    day = resolve_fill_entry_date({"time": "2026-05-27 12:19:01", "setup_key": ""})
    assert normalize_entry_date(day) == pd.Timestamp("2026-05-27")


def test_audit_ds01_uses_signal_bar_camp_not_entry_bar() -> None:
    dates = pd.date_range("2026-01-01", periods=4, freq="D")
    os_df = pd.DataFrame(
        {
            "date": dates,
            "open": [100.0, 101.0, 102.0, 103.0],
            "high": [101.0, 103.0, 104.5, 105.0],
            "low": [99.0, 100.0, 101.5, 102.0],
            "close": [100.5, 102.0, 104.0, 104.5],
            "camp": [1, -1, 1, 1],
            "active_low": [98.0, 90.0, 98.0, 98.0],
            "active_high": [102.0, 105.0, 102.0, 102.0],
        }
    )
    engine = MockEngine(hardened=[[], [], [], []])

    result = audit_ds01_fill(
        side=1,
        entry_date=dates[2],
        trigger_price=103.0,
        stop_price=100.0,
        left_count=0,
        os_df=os_df,
        engine=engine,
        symbol="RB",
    )

    assert result.verdict == "invalid"
    assert any("signal_camp=-1" in issue for issue in result.issues)


def test_load_ack_order_ids(tmp_path) -> None:
    import importlib.util
    from pathlib import Path

    spec = importlib.util.spec_from_file_location(
        "audit_paper_fills",
        Path(__file__).resolve().parents[1] / "scripts" / "audit_paper_fills.py",
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    assert mod.audit_exit_code(fail_on_invalid=True, new_invalid_count=0, needs_data_count=8, invalid_count=0) == 0
    assert mod.audit_exit_code(fail_on_invalid=True, new_invalid_count=1, needs_data_count=0, invalid_count=1) == 2
    assert mod.audit_exit_code(fail_on_invalid=False, new_invalid_count=0, needs_data_count=8, invalid_count=0) == 1
    assert mod.audit_exit_code(fail_on_invalid=False, new_invalid_count=0, needs_data_count=0, invalid_count=0) == 0

    missing = tmp_path / "nope.json"
    assert mod.load_ack_order_ids(missing) == set()

    list_file = tmp_path / "ack_list.json"
    list_file.write_text('["A-DS01-D1-long-1", "B-DS01-D1-short-2"]', encoding="utf-8")
    assert mod.load_ack_order_ids(list_file) == {"A-DS01-D1-long-1", "B-DS01-D1-short-2"}

    dict_file = tmp_path / "ack_dict.json"
    dict_file.write_text(
        '{"note": "x", "acknowledged": ["C-DS01-D1-long-3", {"order_id": "D-DS01-D1-short-4"}]}',
        encoding="utf-8",
    )
    assert mod.load_ack_order_ids(dict_file) == {"C-DS01-D1-long-3", "D-DS01-D1-short-4"}

    broken = tmp_path / "broken.json"
    broken.write_text("{not json", encoding="utf-8")
    assert mod.load_ack_order_ids(broken) == set()


def test_load_exec_gap_order_ids(tmp_path) -> None:
    from fengji_core.fill_supervision import load_exec_gap_order_ids

    assert load_exec_gap_order_ids(tmp_path / "missing.json") == set()
    path = tmp_path / "gap.json"
    path.write_text(
        json.dumps(
            {
                "order_ids": ["WLDUSDT-DS08-H1-short-abc"],
                "entries": [{"order_id": "ATHUSDT-DS08-H1-short-def"}],
            }
        ),
        encoding="utf-8",
    )
    assert load_exec_gap_order_ids(path) == {
        "WLDUSDT-DS08-H1-short-abc",
        "ATHUSDT-DS08-H1-short-def",
    }


def test_audit_ds08_exec_gap_acknowledged(tmp_path, monkeypatch) -> None:
    from fengji_core.fill_supervision import audit_ds08_fill, load_exec_gap_order_ids
    from fengji_core.os_engine import RawNode

    gap_file = tmp_path / "gap.json"
    gap_file.write_text(
        json.dumps({"order_ids": ["WLDUSDT-DS08-H1-short-8317fd9e53809758"]}),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "fengji_core.fill_supervision.load_exec_gap_order_ids",
        lambda path=None: load_exec_gap_order_ids(gap_file),
    )

    dates = pd.date_range("2026-06-20", periods=5, freq="h")
    os_df = pd.DataFrame(
        {
            "date": dates,
            "open": [0.5] * 5,
            "high": [0.51] * 5,
            "low": [0.49] * 5,
            "close": [0.5] * 5,
            "camp": [-1] * 5,
        }
    )
    engine = MockEngine(hardened=[[]] * 5)
    result = audit_ds08_fill(
        side=-1,
        record={"trigger_price": 0.4811, "fill_price": 0.4753},
        os_df=os_df,
        engine=engine,
        symbol="WLDUSDT",
        order_id="WLDUSDT-DS08-H1-short-8317fd9e53809758",
        setup_key="WLDUSDT|SHORT|3|2|0.4811",
        fill_time="2026-06-26 10:09:56",
    )
    assert result.verdict == "exec_gap"


def test_audit_ds08_skips_stale_setup_key_when_pending_fill_ok() -> None:
    from fengji_core.fill_supervision import audit_ds08_fill
    from fengji_core.os_engine import RawNode

    dates = pd.date_range("2026-06-20", periods=5, freq="h")
    os_df = pd.DataFrame(
        {
            "date": dates,
            "open": [0.0045] * 5,
            "high": [0.0046] * 5,
            "low": [0.0043] * 5,
            "close": [0.0044] * 5,
            "camp": [-1] * 5,
        }
    )
    nodes = [
        RawNode(point_idx=0, confirm_idx=0, price=0.0045, raw_type="HIGH"),
        RawNode(point_idx=1, confirm_idx=1, price=0.0044, raw_type="LOW"),
        RawNode(point_idx=2, confirm_idx=2, price=0.0045, raw_type="HIGH"),
        RawNode(point_idx=3, confirm_idx=3, price=0.00438, raw_type="LOW"),
        RawNode(point_idx=4, confirm_idx=4, price=0.00439, raw_type="HIGH"),
    ]
    engine = MockEngine(hardened=[[]] * 4 + [nodes])
    record = {
        "latest_time": str(dates[-1]),
        "trigger_price": 0.004385,
        "stop_price": 0.004516,
        "fill_price": 0.004384,
        "time": "2026-06-24 20:11:29",
    }
    result = audit_ds08_fill(
        side=-1,
        record=record,
        os_df=os_df,
        engine=engine,
        symbol="ATHUSDT",
        order_id="ATHUSDT-DS08-H1-short-test",
        setup_key="ATHUSDT|SHORT|3|2|0.004385",
        fill_time="2026-06-24 20:11:29",
    )
    assert result.verdict == "skipped"
    assert result.checks.get("pending_fill_ok") is True
    assert "stale" in result.issues[0]


def test_parse_ds08_setup_key() -> None:
    parsed = parse_ds08_setup_key("LTCUSDT|LONG|2390|2383|43.46")
    assert parsed is not None
    assert parsed["side"] == 1
    assert parsed["defense_idx"] == 2390
    assert parsed["attack_idx"] == 2383
    assert parsed["trigger_price"] == 43.46


def test_resolve_ohlcv_csv_domestic_futures_h1_strips_usdt_suffix(tmp_path) -> None:
    from fengji_core.fill_supervision import resolve_ohlcv_csv

    h1 = tmp_path / "1h"
    h1.mkdir()
    (h1 / "SR.csv").write_text("date,open,high,low,close\n", encoding="utf-8")
    path = resolve_ohlcv_csv(tmp_path, "SRUSDT", "1h", market="domestic")
    assert path is not None
    assert path.name == "SR.csv"


def test_resolve_ohlcv_csv_domestic_futures_m15(tmp_path) -> None:
    from fengji_core.fill_supervision import resolve_ohlcv_csv

    m15 = tmp_path / "15m"
    m15.mkdir()
    (m15 / "AG.csv").write_text("date,open,high,low,close\n", encoding="utf-8")
    path = resolve_ohlcv_csv(tmp_path, "AGUSDT", "15m", market="domestic")
    assert path is not None
    assert path.name == "AG.csv"


def test_resolve_d1_csv_prefers_freshest_over_legacy_okx(tmp_path) -> None:
    from fengji_core.fill_supervision import resolve_d1_csv

    okx = tmp_path / "crypto_okx"
    live = tmp_path / "1d"
    okx.mkdir()
    live.mkdir()
    (okx / "APT-USDT_1D_1825d.csv").write_text(
        "timestamp,open,high,low,close\n2026-05-20,1,2,0.5,1.5\n",
        encoding="utf-8",
    )
    (live / "APTUSDT.csv").write_text(
        "timestamp,open,high,low,close\n2026-06-28,1,2,0.5,1.5\n",
        encoding="utf-8",
    )
    path = resolve_d1_csv(tmp_path, "APTUSDT", market="crypto")
    assert path is not None
    assert path.parent.name == "1d"
    assert path.name == "APTUSDT.csv"


def test_pending_price_fill_ok() -> None:
    from fengji_core.fill_supervision import pending_price_fill_ok

    assert pending_price_fill_ok(-1, 0.1608, 0.1607) is True
    assert pending_price_fill_ok(1, 43.46, 43.46) is True


def test_apply_radar_ohlcv_tail() -> None:
    from fengji_core.fill_supervision import apply_radar_ohlcv_tail

    df = pd.DataFrame({"date": pd.date_range("2020-01-01", periods=3000, freq="h"), "close": 1.0})
    tailed = apply_radar_ohlcv_tail(df, "1h")
    assert len(tailed) == 2400
    assert tailed.index[0] == 0


def test_infer_record_timeframe() -> None:
    assert infer_record_timeframe({"timeframe": "H1"}) == "1h"
    assert infer_record_timeframe({"timeframe": "D1"}) == "1d"
    assert infer_record_timeframe({}) == "1d"


def test_setup_snapshot_attack_idx_from_reason() -> None:
    from fengji_core.fill_supervision import _setup_snapshot_attack_idx

    record = {
        "reason": "true_peak=157180, attack_idx=171, peak_key=DS03|-1|true_peak|idx=171|px=157180",
        "setup_key": "LCUSDT|DS03|-1|true_peak|idx=171|px=157180",
    }
    assert _setup_snapshot_attack_idx(record) == 171


def test_resolve_ds03_entry_bar_index_prefers_attack_bar_time_over_stale_idx() -> None:
    """New D1 bars shift tail indices; supervision must replay by attack_bar_time."""
    from fengji_core.fill_supervision import resolve_ds03_entry_bar_index

    os_df = pd.DataFrame(
        {
            "date": ["2026-06-30 00:00:00", "2026-07-01 00:00:00", "2026-07-02 00:00:00"],
            "camp": [-1, -1, -1],
        }
    )
    record = {
        "attack_bar_idx": 2,
        "attack_bar_time": "2026-07-01 00:00:00",
        "price_source": "ds03_attack_bar",
        "time": "2026-07-02 00:06:15",
    }
    entry_day = normalize_entry_date(resolve_fill_entry_date(record))
    idx = resolve_ds03_entry_bar_index(os_df, entry_day, record, str(record["time"]))
    assert idx == 1
    assert str(os_df.iloc[idx]["date"]).startswith("2026-07-01")


def test_resolve_ds03_entry_bar_index_falls_back_to_fill_time() -> None:
    from fengji_core.fill_supervision import resolve_ds03_entry_bar_index

    os_df = pd.DataFrame(
        {
            "date": ["2026-06-15 16:00:00", "2026-06-16 16:00:00", "2026-06-17 16:00:00"],
            "camp": [-1, -1, -1],
        }
    )
    record = {"bar_time": "2026-06-18 06:45:00", "time": "2026-06-18 20:34:12"}
    entry_day = normalize_entry_date(resolve_fill_entry_date(record))
    idx = resolve_ds03_entry_bar_index(os_df, entry_day, record, str(record["time"]))
    assert idx == 2
    assert str(os_df.iloc[idx]["date"]).startswith("2026-06-17")


def test_audit_ds01_add_short_uses_order_trigger_not_stale_signal_bar() -> None:
    """续棍 pending 价=12815；信号棍 calc=12745 时不应误报 entry_fill=False。"""
    os_df = pd.DataFrame(
        {
            "date": ["2026-06-16 16:00:00", "2026-06-17 16:00:00", "2026-06-21 16:00:00"],
            "open": [12800.0, 12820.0, 12810.0],
            "high": [12850.0, 12840.0, 12830.0],
            "low": [12740.0, 12745.0, 12800.0],
            "close": [12810.0, 12750.0, 12815.0],
            "camp": [-1, -1, -1],
            "active_low": [12700.0, 12700.0, 12700.0],
            "active_high": [12900.0, 12900.0, 12900.0],
        }
    )
    engine = MockEngine(hardened=[[], [], []])
    setup_key = "BRUSDT|DS01|SHORT|signal=20260617160000|trigger=12815"
    result = audit_ds01_fill(
        side=-1,
        entry_date="2026-06-21",
        trigger_price=12815.0,
        stop_price=12840.0,
        left_count=0,
        os_df=os_df,
        engine=engine,
        is_add=True,
        fill_price=12815.0,
        symbol="BRUSDT",
        setup_key=setup_key,
        record={"setup_key": setup_key, "setup": "DS01 add cuogun"},
    )
    assert result.verdict == "valid"
    assert "entry_fill=False" not in "|".join(result.issues)
    assert result.checks.get("pending_trigger") == 12815.0


def test_parse_ds05_setup_key() -> None:
    from fengji_core.fill_supervision import parse_ds05_setup_key

    parsed = parse_ds05_setup_key(
        "PEPEUSDT|DS05|SHORT|k2=20260610120000|k3=20260611120000|trigger=0.00001234"
    )
    assert parsed is not None
    assert parsed["side"] == -1
    assert parsed["k2_time"] == "20260610120000"
    assert parsed["trigger_price"] == 0.00001234


def test_parse_ds07_setup_key() -> None:
    from fengji_core.fill_supervision import parse_ds07_setup_key

    parsed = parse_ds07_setup_key("INJUSDT|DS07|SHORT|CONT|attack=2392|defense=2395|trigger=4.15")
    assert parsed is not None
    assert parsed["side"] == -1
    assert parsed["attack_idx"] == 2392
    assert parsed["defense_idx"] == 2395
    assert parsed["trigger_price"] == 4.15


def test_audit_fill_record_routes_ds05_unparseable_key() -> None:
    from fengji_core.fill_supervision import audit_fill_record

    dates = pd.date_range("2026-01-01", periods=3, freq="D")
    os_df = pd.DataFrame(
        {
            "date": dates,
            "open": [1.0, 1.0, 1.0],
            "high": [1.1, 1.1, 1.1],
            "low": [0.9, 0.9, 0.9],
            "close": [1.0, 1.0, 1.0],
            "camp": [1, 1, 1],
        }
    )
    engine = MockEngine()
    record = {
        "strategy_id": "DS05",
        "side": "short",
        "setup_key": "bad-key",
        "symbol": "PEPEUSDT",
    }
    result = audit_fill_record(record, os_df, engine)
    assert result.strategy_id == "DS05"
    assert result.verdict == "needs-data"
    assert "unparseable DS05 setup_key" in result.issues


def test_audit_fill_record_routes_ds07_missing_d1() -> None:
    from fengji_core.fill_supervision import audit_fill_record

    dates = pd.date_range("2026-06-20", periods=3, freq="h")
    h1 = pd.DataFrame(
        {
            "date": dates,
            "open": [4.0, 4.0, 4.0],
            "high": [4.1, 4.1, 4.1],
            "low": [3.9, 3.9, 3.9],
            "close": [4.0, 4.0, 4.0],
            "camp": [-1, -1, -1],
        }
    )
    engine = MockEngine()
    record = {
        "strategy_id": "DS07",
        "side": "short",
        "setup_key": "INJUSDT|DS07|SHORT|CONT|attack=1|defense=2|trigger=4.15",
        "symbol": "INJUSDT",
        "latest_time": str(dates[-1]),
    }
    result = audit_fill_record(record, h1, engine, d1_os_df=None)
    assert result.strategy_id == "DS07"
    assert result.verdict == "needs-data"
    assert any("missing D1/H1" in x for x in result.issues)
