"""fengji_core.tail_csv 尾部读取的单元测试：与全量读取结果必须一致。"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from fengji_core.tail_csv import read_csv_tail


def _write_rows(path: Path, n: int, *, fmt: str = "csv") -> None:
    lines = ["date,open,high,low,close,volume"]
    for i in range(n):
        lines.append(f"2026-01-01 00:{i // 60:02d}:{i % 60:02d},{i},{i + 1},{i - 1},{i + 0.5},{10}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def test_small_file_returns_whole_frame(tmp_path: Path) -> None:
    path = tmp_path / "small.csv"
    _write_rows(path, 20)
    frame, complete = read_csv_tail(path)
    assert complete is True
    assert frame is not None
    assert len(frame) == 20


def test_large_file_tail_matches_full_read(tmp_path: Path) -> None:
    """大文件尾读的最后一行必须与全量读取一致（监控只取 tail(1)）。"""
    path = tmp_path / "large.csv"
    _write_rows(path, 5000)
    frame, complete = read_csv_tail(path, max_bytes=4096)
    assert complete is False
    assert frame is not None
    assert len(frame) < 5000
    assert len(frame) >= 12
    full = pd.read_csv(path)
    assert full.iloc[-1]["close"] == frame.iloc[-1]["close"]
    assert full.iloc[-1]["date"] == frame.iloc[-1]["date"]


def test_crlf_file_tail_matches_full_read(tmp_path: Path) -> None:
    path = tmp_path / "crlf.csv"
    rows = ["date,open,high,low,close,volume"]
    for i in range(3000):
        rows.append(f"2026-01-02 00:00:{i:02d},{i},{i + 1},{i - 1},{i},{10}")
    path.write_bytes(("\r\n".join(rows) + "\r\n").encode("utf-8"))
    frame, complete = read_csv_tail(path, max_bytes=2048)
    assert complete is False
    assert frame is not None
    full = pd.read_csv(path)
    assert len(full) == 3000
    assert full.iloc[-1]["close"] == frame.iloc[-1]["close"]


def test_incomplete_last_line_returns_none(tmp_path: Path) -> None:
    """文件末尾无换行符（疑似正在写入）时必须拒绝尾读，由调用方回退全量。"""
    path = tmp_path / "halfwrite.csv"
    _write_rows(path, 300)
    with path.open("ab") as fh:
        fh.write(b"2026-01-03 00:00:00,1,2,3,4,5")  # no trailing newline
    frame, complete = read_csv_tail(path, max_bytes=1024)
    assert frame is None
    assert complete is False


def test_min_rows_gate(tmp_path: Path) -> None:
    """窗口内行数不足下限时拒绝尾读（防止依赖倒数第 2 根的逻辑缺少上下文）。"""
    path = tmp_path / "gate.csv"
    _write_rows(path, 5000)
    frame, complete = read_csv_tail(path, max_bytes=4096, min_rows=10_000)
    assert frame is None
    assert complete is False


def test_missing_file_returns_none(tmp_path: Path) -> None:
    frame, complete = read_csv_tail(tmp_path / "nope.csv")
    assert frame is None
    assert complete is False


def test_disabled_via_env_returns_none(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("FENGJI_TAIL_READ_BYTES", "0")
    path = tmp_path / "disabled.csv"
    _write_rows(path, 5000)
    frame, complete = read_csv_tail(path)
    assert frame is None
    assert complete is False


def test_bad_env_value_falls_back_to_default(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("FENGJI_TAIL_READ_BYTES", "not-a-number")
    from fengji_core.tail_csv import tail_bytes_enabled_default

    assert tail_bytes_enabled_default() > 0
    path = tmp_path / "badenv.csv"
    _write_rows(path, 5000)
    frame, complete = read_csv_tail(path, max_bytes=tail_bytes_enabled_default())
    assert complete is False
    assert frame is not None
