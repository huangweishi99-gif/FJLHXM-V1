"""海外数据泵 (data_manager.py) 容错改造的单测：重试、汇总、连续失败告警。

data_manager.py 顶层 import binance.client；本机（Windows dev）无该库，
测试前先注入等价 stub（与 conftest 的 tqsdk stub 同思路）。
"""
from __future__ import annotations

import sys
import time
import types
from pathlib import Path


def _install_binance_stub() -> None:
    if "binance.client" in sys.modules:
        return
    mod = types.ModuleType("binance")
    client_mod = types.ModuleType("binance.client")

    class Client:  # noqa: D101 - test stub
        KLINE_INTERVAL_1DAY = "1d"
        KLINE_INTERVAL_1HOUR = "1h"
        KLINE_INTERVAL_15MINUTE = "15m"

        def __init__(self, *_args, **_kwargs) -> None:
            self.calls: list[tuple] = []

        def get_historical_klines(self, symbol, interval, start_str):  # noqa: ANN001
            self.calls.append((symbol, interval, start_str))
            raise NotImplementedError

    client_mod.Client = Client
    mod.client = client_mod
    sys.modules.setdefault("binance", mod)
    sys.modules.setdefault("binance.client", client_mod)


_install_binance_stub()
import data_manager as dm  # noqa: E402


def _klines(n: int = 3) -> list[list]:
    """构造 python-binance K 线原始返回行（12 列）。"""
    base = int(time.time() * 1000) - n * 60_000
    rows = []
    for i in range(n):
        ts = base + i * 60_000
        rows.append([ts, f"{100 + i}", f"{101 + i}", f"{99 + i}", f"{100.5 + i}", "1000",
                     ts + 60_000, "0", "0", "0", "0", "x"])
    return rows


class _FakeApi:
    def __init__(self, *, fail_times: int = 0) -> None:
        self.fail_times = fail_times
        self.attempts = 0

    def get_historical_klines(self, *_args, **_kwargs):  # noqa: ANN002, ANN003
        self.attempts += 1
        if self.attempts <= self.fail_times:
            raise ConnectionError("boom")
        return _klines(3)


def _use_tmp_dir(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(dm, "BASE_DIR", str(tmp_path))
    monkeypatch.setattr(dm, "client", _FakeApi())


def test_sync_success_first_try(tmp_path: Path, monkeypatch) -> None:
    _use_tmp_dir(tmp_path, monkeypatch)
    sleeps: list[float] = []
    monkeypatch.setattr(dm.time, "sleep", lambda s: sleeps.append(s))

    api = dm.client
    result = dm.sync_one_symbol(api, "BTCUSDT", "1h", dm.Client.KLINE_INTERVAL_1HOUR)
    assert result["status"] == "ok"
    assert api.attempts == 1
    assert sleeps == [0.5]
    assert (tmp_path / "1h" / "BTCUSDT.csv").exists()


def test_sync_retry_then_success(tmp_path: Path, monkeypatch) -> None:
    _use_tmp_dir(tmp_path, monkeypatch)
    sleeps: list[float] = []
    monkeypatch.setattr(dm.time, "sleep", lambda s: sleeps.append(s))
    api = _FakeApi(fail_times=2)
    monkeypatch.setattr(dm, "client", api)

    result = dm.sync_one_symbol(api, "ETHUSDT", "15m", dm.Client.KLINE_INTERVAL_15MINUTE)
    assert result["status"] == "ok"
    assert api.attempts == 3
    # 成功前的退避等待 = 5s、10s，再加成功后的 0.5s 防限频
    assert sleeps == [5.0, 10.0, 0.5]


def test_sync_retries_exhausted_failed(tmp_path: Path, monkeypatch) -> None:
    _use_tmp_dir(tmp_path, monkeypatch)
    sleeps: list[float] = []
    monkeypatch.setattr(dm.time, "sleep", lambda s: sleeps.append(s))
    api = _FakeApi(fail_times=99)
    monkeypatch.setattr(dm, "client", api)

    result = dm.sync_one_symbol(api, "SOLUSDT", "1d", dm.Client.KLINE_INTERVAL_1DAY)
    assert result["status"] == "failed"
    assert api.attempts == dm.MAX_SYMBOL_RETRIES
    assert sleeps == [5.0, 10.0]  # 最后一次失败不再 sleep


def test_sync_skipped_when_empty(tmp_path: Path, monkeypatch) -> None:
    _use_tmp_dir(tmp_path, monkeypatch)

    class _Empty:
        def get_historical_klines(self, *_a, **_k):
            return []

    result = dm.sync_one_symbol(_Empty(), "BTCUSDT", "1d", dm.Client.KLINE_INTERVAL_1DAY)
    assert result["status"] == "skipped"


def test_sync_data_summary(tmp_path: Path, monkeypatch) -> None:
    _use_tmp_dir(tmp_path, monkeypatch)

    def fake_sync(_api, symbol, _folder, _interval, **_kw):
        if symbol == "TRUMPUSDT":
            return {"status": "failed", "message": "x"}
        return {"status": "ok" if symbol != "RENDERUSDT" else "skipped", "message": ""}

    monkeypatch.setattr(dm, "sync_one_symbol", fake_sync)
    stats = dm.sync_data()
    # SYMBOLS=16 × INTERVALS=3 = 48 项；TRUMPUSDT 三个周期全失败、RENDERUSDT 全跳过
    assert stats["ok"] == 42
    assert stats["skipped"] == 3
    assert stats["failed"] == 3
    assert stats["failed_items"] == ["TRUMPUSDT-1d", "TRUMPUSDT-1h", "TRUMPUSDT-15m"]


def test_evaluate_failure_alert_resets_on_clean_round() -> None:
    clean = {"failed": 0, "failed_items": []}
    assert dm.evaluate_failure_alert(2, clean) == (0, None)


def test_evaluate_failure_alert_escalates() -> None:
    stats = {"failed": 2, "failed_items": ["X-1d"]}
    consecutive, alert = dm.evaluate_failure_alert(0, stats)
    assert consecutive == 1
    assert alert is not None and alert.startswith("[ALERT]")

    consecutive, alert = dm.evaluate_failure_alert(1, stats)
    assert consecutive == 2
    assert "本轮" in alert

    consecutive, alert = dm.evaluate_failure_alert(2, stats)
    assert consecutive == 3
    assert "连续 3 轮" in alert
