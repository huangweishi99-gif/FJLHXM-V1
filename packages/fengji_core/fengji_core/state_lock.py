"""跨进程状态文件锁：防止多个监控并发读改写同一 paper_state 造成「丢失更新」。

两个写者（挂单监控 + 模拟盘）共用同一 state.json。本模块提供：
- ``file_lock(target)``：基于 sidecar ``<target>.lock`` 的独占锁（Linux flock / Windows msvcrt）。
- ``update_state_file(target, mutator)``：持锁内「重载最新→mutator 改→原子落盘」，
  保证临界区内读到的是最新已提交状态，杜绝丢失更新。

设计要点：
- 锁只覆盖「读最新 → 改 → 落盘」这一小段，**不要**在持锁时做网络/重计算。
- 落盘用临时文件 + 原子 replace，避免半截写入。
"""
from __future__ import annotations

import json
import os
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Callable, Iterator


def lock_path_for(target: Path | str) -> Path:
    target = Path(target)
    return target.with_suffix(target.suffix + ".lock")


@contextmanager
def file_lock(target: Path | str, *, timeout: float = 90.0, poll: float = 0.05) -> Iterator[None]:
    """对 ``<target>.lock`` 取独占锁；超时抛 TimeoutError。"""
    lpath = lock_path_for(target)
    lpath.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(str(lpath), os.O_CREAT | os.O_RDWR)
    deadline = time.time() + timeout
    acquired = False
    try:
        if os.name == "nt":
            import msvcrt

            while True:
                try:
                    msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
                    acquired = True
                    break
                except OSError:
                    if time.time() > deadline:
                        raise TimeoutError(f"acquire lock timeout: {lpath}")
                    time.sleep(poll)
        else:
            import fcntl

            while True:
                try:
                    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    acquired = True
                    break
                except OSError:
                    if time.time() > deadline:
                        raise TimeoutError(f"acquire lock timeout: {lpath}")
                    time.sleep(poll)
        yield
    finally:
        if acquired:
            try:
                if os.name == "nt":
                    import msvcrt

                    os.lseek(fd, 0, os.SEEK_SET)
                    msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
                else:
                    import fcntl

                    fcntl.flock(fd, fcntl.LOCK_UN)
            except OSError:
                pass
        os.close(fd)


def _load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _save_json_atomic(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    tmp.replace(path)


def update_state_file(
    target: Path | str,
    mutator: Callable[[dict[str, Any]], Any],
    *,
    default: dict[str, Any] | None = None,
    timeout: float = 90.0,
) -> dict[str, Any]:
    """持锁内：重载最新 state → mutator(state) → 原子落盘，返回落盘后的 state。

    mutator 直接就地修改传入的 dict（返回值忽略）。临界区内务必只做内存操作。
    """
    target = Path(target)
    with file_lock(target, timeout=timeout):
        state = _load_json(target, dict(default) if default is not None else {})
        if not isinstance(state, dict):
            state = dict(default) if default is not None else {}
        mutator(state)
        _save_json_atomic(target, state)
        return state
