from __future__ import annotations

import importlib
import json
import sys

import pandas as pd
import pytest


def load_data_manager(monkeypatch: pytest.MonkeyPatch, tmp_path):
    monkeypatch.setenv("FUTURES_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("FUTURES_LOG_DIR", str(tmp_path / "logs"))
    monkeypatch.setenv("FUTURES_MAIN_CONTRACT_MANIFEST", str(tmp_path / "logs" / "manifest.json"))
    sys.modules.pop("data_manager_futures", None)
    return importlib.import_module("data_manager_futures")


def test_all_domestic_futures_symbols_use_tq_main_continuous(monkeypatch, tmp_path):
    dm = load_data_manager(monkeypatch, tmp_path)

    assert dm.TQ_SYMBOL_MAP
    assert all(dm.is_main_continuous_code(tq_code) for tq_code in dm.TQ_SYMBOL_MAP.values())
    dm.validate_main_continuous_map(dm.TQ_SYMBOL_MAP)

    dm.initialize_main_contract_manifest()
    manifest = json.loads(dm.MAIN_CONTRACT_MANIFEST.read_text(encoding="utf-8"))
    assert manifest["mode"] == "tq_actual_main_contract"
    assert len(manifest["symbols"]) == len(dm.TQ_SYMBOL_MAP)
    assert manifest["symbols"]["LH"]["tq_code"] == "KQ.m@DCE.lh"
    assert manifest["symbols"]["LH"]["display_contract"] == "KQ.m@DCE.lh"
    assert manifest["symbols"]["LH"]["data_contract"] == "KQ.m@DCE.lh"
    assert manifest["symbols"]["LH"]["data_contract_is_actual"] is False
    assert manifest["symbols"]["LH"]["timeframes"] == {}


def test_actual_month_contract_is_fetchable_but_not_used_for_discovery(monkeypatch, tmp_path):
    dm = load_data_manager(monkeypatch, tmp_path)

    with pytest.raises(ValueError, match="KQ\\.m@"):
        dm.validate_main_continuous_map({"RB": "SHFE.rb2609"})

    class DummyApi:
        def get_kline_serial(self, tq_code, _seconds, data_length):
            base = pd.Timestamp("2026-06-01 09:00:00")
            return pd.DataFrame(
                {
                    "datetime": [(base + pd.Timedelta(minutes=15 * i)).value for i in range(12)],
                    "symbol": [tq_code] * 12,
                    "open": [100 + i for i in range(12)],
                    "high": [101 + i for i in range(12)],
                    "low": [99 + i for i in range(12)],
                    "close": [100.5 + i for i in range(12)],
                }
            )

    frame = dm.fetch_frame(DummyApi(), "SHFE.rb2609", "1d")
    assert frame["symbol"].iloc[-1] == "SHFE.rb2609"

    with pytest.raises(ValueError, match="非 KQ\\.m@"):
        dm.resolve_data_contract(DummyApi(), "RB", "SHFE.rb2609")


def test_fetch_symbol_writes_main_contract_manifest(monkeypatch, tmp_path):
    dm = load_data_manager(monkeypatch, tmp_path)

    class DummyApi:
        def get_quote(self, tq_code):
            return type(
                "Quote",
                (),
                {
                    "underlying_symbol": "DCE.lh2609",
                    "instrument_id": tq_code,
                },
            )()

        def wait_update(self, deadline=None):
            return False

        def get_kline_serial(self, tq_code, _seconds, data_length):
            assert tq_code == "DCE.lh2609"
            base = pd.Timestamp("2026-06-01 09:00:00")
            return pd.DataFrame(
                {
                    "datetime": [(base + pd.Timedelta(minutes=15 * i)).value for i in range(12)],
                    "symbol": [tq_code] * 12,
                    "open": [100 + i for i in range(12)],
                    "high": [101 + i for i in range(12)],
                    "low": [99 + i for i in range(12)],
                    "close": [100.5 + i for i in range(12)],
                    "volume": [1000 + i for i in range(12)],
                    "open_oi": [2000 + i for i in range(12)],
                    "close_oi": [2000 + i for i in range(12)],
                    "duration": [data_length] * 12,
                    "id": list(range(12)),
                }
            )

    assert dm.fetch_symbol(DummyApi(), "LH", "KQ.m@DCE.lh") is True

    manifest_path = tmp_path / "logs" / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    entry = manifest["symbols"]["LH"]
    assert manifest["mode"] == "tq_actual_main_contract"
    assert entry["tq_code"] == "KQ.m@DCE.lh"
    assert entry["underlying_symbol"] == "DCE.lh2609"
    assert entry["data_contract"] == "DCE.lh2609"
    assert entry["data_contract_is_actual"] is True
    assert entry["display_contract"] == "DCE.lh2609"
    assert entry["main_continuous"] is True
    assert set(entry["timeframes"]) == {"1d", "1h", "15m", "5m"}
    assert entry["timeframes"]["15m"]["source_symbols"] == ["DCE.lh2609"]
    assert entry["timeframes"]["15m"]["data_contract"] == "DCE.lh2609"
    assert (tmp_path / "data" / "15m" / "LH.csv").exists()
    assert (tmp_path / "data" / "15m" / "LHUSDT.csv").exists()


def test_missing_underlying_refuses_to_write_main_continuous(monkeypatch, tmp_path):
    dm = load_data_manager(monkeypatch, tmp_path)

    class NoUnderlyingApi:
        def get_quote(self, tq_code):
            return type("Quote", (), {"underlying_symbol": "", "instrument_id": tq_code})()

        def wait_update(self, deadline=None):
            return False

    with pytest.raises(RuntimeError, match="拒绝继续写入主连数据"):
        dm.resolve_data_contract(NoUnderlyingApi(), "LH", "KQ.m@DCE.lh")


def test_normalize_frame_drops_future_and_invalid_ohlcv_rows(monkeypatch, tmp_path):
    dm = load_data_manager(monkeypatch, tmp_path)

    valid_time = pd.Timestamp("2026-06-03 09:15:00").value
    future_time = pd.Timestamp("2117-11-11 06:26:59").value
    frame = pd.DataFrame(
        [
            {
                "datetime": valid_time,
                "symbol": "GFEX.lc2609",
                "open": 172000.0,
                "high": 173000.0,
                "low": 171000.0,
                "close": 172500.0,
                "volume": 100,
            },
            {
                "datetime": future_time,
                "symbol": "GFEX.lc2609",
                "open": 8715.0,
                "high": 9165.0,
                "low": 9135.0,
                "close": 8750.0,
                "volume": 100,
            },
            {
                "datetime": pd.Timestamp("2026-06-03 09:30:00").value,
                "symbol": "GFEX.lc2609",
                "open": 2.17e-322,
                "high": 9165.0,
                "low": 9135.0,
                "close": 7.57e-96,
                "volume": 100,
            },
            {
                "datetime": pd.Timestamp("2026-06-03 09:40:00").value,
                "symbol": "DCE.pp2609",
                "open": 6.5181547e-143,
                "high": 5.040429e180,
                "low": 3.183734e-312,
                "close": 3.189770e-312,
                "volume": 6360567320059846688,
            },
            {
                "datetime": pd.Timestamp("2026-06-03 09:45:00").value,
                "symbol": "GFEX.lc2609",
                "open": 172000.0,
                "high": 171000.0,
                "low": 173000.0,
                "close": 172500.0,
                "volume": 100,
            },
        ]
    )

    cleaned = dm.normalize_frame(frame)

    assert len(cleaned) == 1
    assert cleaned["date"].tolist() == ["2026-06-03 09:15:00"]
    assert cleaned["close"].tolist() == [172500.0]


def test_normalize_frame_drops_pre_2020_rows(monkeypatch, tmp_path):
    dm = load_data_manager(monkeypatch, tmp_path)
    frame = pd.DataFrame(
        [
            {
                "datetime": pd.Timestamp("2016-08-26 06:15:00").value,
                "open": 4590.0,
                "high": 4598.0,
                "low": 4550.0,
                "close": 4598.0,
            },
            {
                "datetime": pd.Timestamp("2026-06-03 09:15:00").value,
                "open": 5000.0,
                "high": 5010.0,
                "low": 4990.0,
                "close": 5005.0,
            },
        ]
    )
    cleaned = dm.normalize_frame(frame)
    assert len(cleaned) == 1
    assert cleaned["date"].tolist() == ["2026-06-03 09:15:00"]


def test_frame_looks_sane_accepts_short_clean_history(monkeypatch, tmp_path):
    dm = load_data_manager(monkeypatch, tmp_path)
    base = pd.Timestamp("2026-06-01 09:00:00")
    frame = pd.DataFrame(
        {
            "date": [(base + pd.Timedelta(minutes=15 * i)).strftime("%Y-%m-%d %H:%M:%S") for i in range(8)],
            "open": [100 + i for i in range(8)],
            "high": [101 + i for i in range(8)],
            "low": [99 + i for i in range(8)],
            "close": [100.5 + i for i in range(8)],
        }
    )
    assert dm.frame_looks_sane(frame) is True


def test_frame_looks_acceptable_rejects_tiny_frames(monkeypatch, tmp_path):
    dm = load_data_manager(monkeypatch, tmp_path)
    base = pd.Timestamp("2026-06-01 09:00:00")
    frame = pd.DataFrame(
        {
            "date": [(base + pd.Timedelta(minutes=15 * i)).strftime("%Y-%m-%d %H:%M:%S") for i in range(40)],
            "open": [100 + i for i in range(40)],
            "high": [101 + i for i in range(40)],
            "low": [99 + i for i in range(40)],
            "close": [100.5 + i for i in range(40)],
        }
    )
    assert dm.frame_looks_acceptable(frame, min_rows=100) is False


def test_frame_looks_acceptable_accepts_mixed_history_when_strict_fails(monkeypatch, tmp_path):
    dm = load_data_manager(monkeypatch, tmp_path)
    base = pd.Timestamp("2026-06-01 09:00:00")
    n = 400
    rows = []
    for i in range(n):
        if i % 5 == 0:
            rows.append(
                {
                    "date": (base + pd.Timedelta(minutes=15 * i)).strftime("%Y-%m-%d %H:%M:%S"),
                    "open": 100.0,
                    "high": 99.0,
                    "low": 100.0,
                    "close": 100.0,
                }
            )
        else:
            rows.append(
                {
                    "date": (base + pd.Timedelta(minutes=15 * i)).strftime("%Y-%m-%d %H:%M:%S"),
                    "open": 100.0,
                    "high": 101.0,
                    "low": 99.0,
                    "close": 100.5,
                }
            )
    frame = pd.DataFrame(rows)
    assert dm.frame_looks_sane(frame) is False
    assert dm.frame_looks_acceptable(frame, min_rows=100) is True


def test_fetch_frame_falls_back_to_acceptable_when_strict_sane_fails(monkeypatch, tmp_path):
    dm = load_data_manager(monkeypatch, tmp_path)
    base = pd.Timestamp("2026-06-01 09:00:00")

    def _make_frame(rows: int, *, corrupt_tail: int) -> pd.DataFrame:
        good = rows - corrupt_tail
        datetimes = [(base + pd.Timedelta(minutes=15 * i)).value for i in range(rows)]
        opens = [100.0] * good + [1e-200] * corrupt_tail
        highs = [101.0] * good + [1e200] * corrupt_tail
        lows = [99.0] * good + [1e-300] * corrupt_tail
        closes = [100.5] * good + [1e-300] * corrupt_tail
        return pd.DataFrame(
            {
                "datetime": datetimes,
                "open": opens,
                "high": highs,
                "low": lows,
                "close": closes,
            }
        )

    class DummyApi:
        def get_kline_serial(self, tq_code, _seconds, data_length):
            return _make_frame(min(data_length, 4000), corrupt_tail=500)

    frame = dm.fetch_frame(DummyApi(), "DCE.pg2608", "15m")
    assert len(frame) >= 100
    assert frame["date"].iloc[-1].startswith("2026-")


def test_needs_stale_catchup_when_bar_time_old(monkeypatch, tmp_path):
    dm = load_data_manager(monkeypatch, tmp_path)
    monkeypatch.setenv("FUTURES_STALE_BAR_HOURS", "48")
    dm.STALE_BAR_HOURS = 48
    one_d = tmp_path / "data" / "1d"
    one_d.mkdir(parents=True, exist_ok=True)
    sample = one_d / "FG.csv"
    sample.write_text(
        "datetime,open,high,low,close,volume,date\n"
        "1,100,110,90,105,10,2026-06-10 16:00:00\n",
        encoding="utf-8",
    )
    sample.touch()
    assert dm.latest_1d_bar_time("FG") == __import__("datetime").datetime(2026, 6, 10, 16, 0, 0)
    assert dm.needs_stale_catchup() is True


def test_fetch_frame_error_includes_reason_when_all_checks_fail(monkeypatch, tmp_path):
    dm = load_data_manager(monkeypatch, tmp_path)
    base = pd.Timestamp("2026-06-01 09:00:00")

    class DummyApi:
        def get_kline_serial(self, tq_code, _seconds, data_length):
            rows = min(data_length, 40)
            return pd.DataFrame(
                {
                    "datetime": [(base + pd.Timedelta(minutes=15 * i)).value for i in range(rows)],
                    "open": [100.0] * rows,
                    "high": [99.0] * rows,
                    "low": [100.0] * rows,
                    "close": [100.0] * rows,
                }
            )

    with pytest.raises(RuntimeError, match="校验均未通过|连续抓取失败"):
        dm.fetch_frame(DummyApi(), "DCE.pg2608", "15m")
