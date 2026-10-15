"""os_state_store：OS 状态「内容不变不回写」行为 + 不引入大对象缓存的契约。

背景实测（runtime/fengji_os_state/SOLUSDT_1d.json，14.2MB）：
- 重新解析 ~0.10s；解析后常驻内存 ~44MB。
- 写盘 ~9ms；内容相同时 dict 比较 ~17ms；内容不同时首个键即短路（~0ms）。
- 序列化字符串比较需 145ms/次 —— 比写盘贵一个量级，不能用作兜底。
故：保留「内容不变不回写」，明确不做进程内缓存（循环扫描命中率低、内存不可控）。
"""
from __future__ import annotations

import json
import time
from pathlib import Path

import pandas as pd

from fengji_core import os_state_store as store


def _frame(rows: int = 30) -> pd.DataFrame:
    idx = pd.date_range("2024-01-01", periods=rows, freq="D")
    close = [100.0 + (i % 5) for i in range(rows)]
    return pd.DataFrame(
        {
            "date": idx.strftime("%Y-%m-%d %H:%M:%S"),
            "open": close,
            "high": [c + 1.0 for c in close],
            "low": [c - 1.0 for c in close],
            "close": close,
            "volume": [1000.0] * rows,
        }
    )


class _FakeEngine:
    """最小替身：只提供 write_os_state / build 需要的接口。"""

    def __init__(self, gap: int = 3, record_hardened_by_bar: bool = True, payload: dict | None = None):
        self.gap = gap
        self.record_hardened_by_bar = record_hardened_by_bar
        self.payload = payload if payload is not None else {"version": 1, "processed_len": 10, "gap": 3}
        self.seen_state = None

    def run_from_state(self, df, state):  # noqa: ANN001, ANN201
        self.seen_state = state
        return self

    def to_state(self, include_hardened_by_bar=None) -> dict:  # noqa: ANN001
        return dict(self.payload)


def test_read_os_state_has_no_in_process_cache(tmp_path: Path, monkeypatch) -> None:
    path = tmp_path / "S_1d.json"
    path.write_text(json.dumps({"version": 1, "processed_len": 5}), encoding="utf-8")
    real_loads = json.loads
    calls = {"n": 0}

    def counting_loads(*args, **kwargs):
        calls["n"] += 1
        return real_loads(*args, **kwargs)

    monkeypatch.setattr(store.json, "loads", counting_loads)

    first = store.read_os_state(path)
    second = store.read_os_state(path)

    # 契约：不做进程内缓存（大对象缓存 ~40MB/份，循环扫描命中率低）
    assert calls["n"] == 2
    assert first == second and first is not second


def test_write_os_state_skips_rewrite_when_content_identical(tmp_path: Path) -> None:
    df = _frame()
    path = tmp_path / "S_1d.json"

    wrote_first = store.write_os_state(path, _FakeEngine(), df, include_hardened_by_bar=True)
    mtime_after_first = path.stat().st_mtime_ns
    previous = store.read_os_state(path)

    wrote_second = store.write_os_state(
        path, _FakeEngine(payload=previous), df, include_hardened_by_bar=True, previous_state=previous
    )

    assert wrote_first is True
    assert wrote_second is False
    assert path.stat().st_mtime_ns == mtime_after_first
    assert store.read_os_state(path) == previous


def test_write_os_state_rewrites_when_content_changes(tmp_path: Path) -> None:
    df = _frame()
    path = tmp_path / "S_1d.json"
    store.write_os_state(path, _FakeEngine(), df, include_hardened_by_bar=True)
    previous = store.read_os_state(path)

    changed = dict(previous)
    changed["processed_len"] = int(previous["processed_len"]) + 1
    wrote = store.write_os_state(
        path, _FakeEngine(payload=changed), df, include_hardened_by_bar=True, previous_state=previous
    )

    assert wrote is True
    assert store.read_os_state(path)["processed_len"] == int(previous["processed_len"]) + 1


def test_write_os_state_without_previous_always_writes(tmp_path: Path) -> None:
    df = _frame()
    path = tmp_path / "S_1d.json"

    assert store.write_os_state(path, _FakeEngine(), df, include_hardened_by_bar=True) is True
    assert store.write_os_state(path, _FakeEngine(), df, include_hardened_by_bar=True) is True


def test_build_stateful_passes_previous_state_and_skips_rewrite(tmp_path: Path, monkeypatch) -> None:
    df = _frame()
    path = tmp_path / "S_1d.json"
    engines: list[_FakeEngine] = []

    def factory(gap: int = 3, record_hardened_by_bar: bool = True):
        # processed_len 必须等于帧长度：write_os_state 写的是末行日期，而
        # state_matches_frame 用 iloc[processed_len-1] 校验（真实增量场景下二者同一行）
        engine = _FakeEngine(gap=gap, record_hardened_by_bar=record_hardened_by_bar, payload={"version": 1, "processed_len": len(df), "gap": gap})
        engines.append(engine)
        return engine

    monkeypatch.setattr(store, "FengJiOSIdentityEngine", factory)

    store.build_os_detail_frame_stateful(df, 3, path, lambda frame, engine: frame, record_hardened_by_bar=True)
    first_state = store.read_os_state(path)
    mtime_first = path.stat().st_mtime_ns
    time.sleep(0.01)

    store.build_os_detail_frame_stateful(df, 3, path, lambda frame, engine: frame, record_hardened_by_bar=True)

    # 第二轮：旧状态被匹配并传给引擎，且因内容相同而不再写盘
    assert engines[1].seen_state is not None
    assert path.stat().st_mtime_ns == mtime_first
    assert store.read_os_state(path) == first_state


def test_write_os_state_ignores_empty_frame(tmp_path: Path) -> None:
    path = tmp_path / "S_1d.json"
    wrote = store.write_os_state(path, _FakeEngine(), pd.DataFrame(), include_hardened_by_bar=True)
    assert wrote is False
    assert not path.exists()
