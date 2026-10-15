from __future__ import annotations

from pathlib import Path

import pandas as pd

import fengji_core.stop_bar_monitor as sbm
from fengji_core.stop_bar_monitor import (
    filter_valid_price_rows,
    read_latest_bar,
    read_price_frame,
    stop_crossed,
)


def test_filter_valid_price_rows_keeps_crypto_pepe(tmp_path: Path) -> None:
    frame = pd.DataFrame(
        {
            "date": ["2026-06-29", "2026-06-30"],
            "open": [2.35e-06, 2.35e-06],
            "high": [2.42e-06, 2.37e-06],
            "low": [2.31e-06, 2.32e-06],
            "close": [2.36e-06, 2.35e-06],
            "volume": [1.0, 1.0],
        }
    )
    out = filter_valid_price_rows(frame)
    assert len(out) == 2


def test_read_latest_bar_completed_ds01(tmp_path: Path) -> None:
    data = tmp_path / "data"
    (data / "1d").mkdir(parents=True)
    (data / "1d" / "SUIUSDT.csv").write_text(
        "datetime,open,high,low,close,volume\n"
        "2026-06-29,0.68,0.685,0.67,0.682,1\n"
        "2026-06-30,0.70,0.7034,0.69,0.6957,1\n",
        encoding="utf-8",
    )
    bar = read_latest_bar(data, "SUIUSDT", ["1d"], completed_only=True)
    assert bar is not None
    assert bar["date"].startswith("2026-06-29")


def test_stop_crossed_short_string_side() -> None:
    pos = {"side": "short", "current_stop": 1.05}
    bar = {"high": 1.06, "low": 1.0, "open": 1.02, "close": 1.03}
    assert stop_crossed(pos, bar) is True


def _write_futures_bars(data_dir: Path, n: int) -> Path:
    """构造国内期货 15m 风格 CSV（日期时间 + OHLC + volume），日期取过去时点。"""
    from datetime import datetime, timedelta

    (data_dir / "15m").mkdir(parents=True, exist_ok=True)
    path = data_dir / "15m" / "RB2510.csv"
    start = datetime(2026, 6, 1, 0, 0)
    lines = ["datetime,open,high,low,close,volume"]
    for i in range(n):
        stamp = (start + timedelta(minutes=i * 15)).strftime("%Y-%m-%d %H:%M:%S")
        lines.append(f"{stamp},{100 + i},{101 + i},{99 + i},{100.5 + i},{200}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def test_read_price_frame_tail_equals_full(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("FENGJI_MARKET", "futures")
    path = _write_futures_bars(tmp_path, 4000)
    tail, complete = sbm.read_csv_tail(path, max_bytes=8192)
    assert complete is False
    assert tail is not None
    full = pd.read_csv(path)
    assert len(full) == 4000
    assert tail.iloc[-1]["close"] == full.iloc[-1]["close"]
    # 最新一根 bar 与全量一致（非 completed 场景取 tail(1)）
    bar = read_latest_bar(tmp_path, "RB2510USDT", ["15m"])
    assert bar is not None
    assert bar["close"] == full.iloc[-1]["close"]


def test_read_latest_bar_completed_tail_equals_full(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("FENGJI_MARKET", "futures")
    _write_futures_bars(tmp_path, 4000)
    full = pd.read_csv(tmp_path / "15m" / "RB2510.csv")
    bar = read_latest_bar(tmp_path, "RB2510USDT", ["15m"], completed_only=True)
    assert bar is not None
    assert bar["close"] == full.iloc[-2]["close"]


def test_read_price_frame_falls_back_when_tail_refused(tmp_path: Path, monkeypatch) -> None:
    path = _write_futures_bars(tmp_path, 200)
    monkeypatch.setattr(sbm, "read_csv_tail", lambda *_a, **_k: (None, False))
    frame = read_price_frame(path)
    assert frame is not None
    assert len(frame) == 200


def test_read_price_frame_kill_switch_falls_back(tmp_path: Path, monkeypatch) -> None:
    """FENGJI_TAIL_READ_BYTES=0 禁用尾读后仍能取到正确 bar。"""
    monkeypatch.setenv("FENGJI_MARKET", "futures")
    monkeypatch.setenv("FENGJI_TAIL_READ_BYTES", "0")
    _write_futures_bars(tmp_path, 200)
    full = pd.read_csv(tmp_path / "15m" / "RB2510.csv")
    bar = read_latest_bar(tmp_path, "RB2510USDT", ["15m"])
    assert bar is not None
    assert bar["close"] == full.iloc[-1]["close"]
