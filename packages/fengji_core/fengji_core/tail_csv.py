"""行情 CSV 尾部读取：避免高频监控每轮全量解析长历史文件。

背景
----
挂单监控（海外 5s / 国内 5s）每轮都要读取每个品种的 OHLCV CSV，
而国内期货 15m 历史可达上万行。原实现一律 ``pd.read_csv(path)`` 全量读取后再
``tail(1)``，磁盘 IO 与日期解析成本随历史长度线性增长。

本模块只读取文件**末尾若干 KB**，拼回表头后交给 ``pd.read_csv`` 解析，
把每轮每品种的成本从 O(文件长度) 降为 O(尾部窗口)。

正确性契约
----------
1. **绝静默改变结果**：尾读失败、行数不足、或文件疑似正在被写入（末行无换行符）
   时返回 ``(None, False)``，调用方必须回退到全量 ``pd.read_csv``。
2. **行数下限**：尾部窗口解析出的行数少于 ``MIN_TAIL_ROWS`` 时不信任，回退全量。
   这保证依赖「倒数第 2 根」的 ``completed_only`` 逻辑仍有足够上下文。
3. **应急开关**：环境变量 ``FENGJI_TAIL_READ_BYTES=0`` 可全局禁用尾读，
   无需改代码即可回退到旧行为（用于线上快速止血）。

非策略层：本模块只做文件 IO，不参与峰极线、阵营、DS01-DS09 任何判断。
"""
from __future__ import annotations

import io
import os
from pathlib import Path

import pandas as pd

DEFAULT_TAIL_BYTES = 65_536
MIN_TAIL_ROWS = 12
_ENCODING = "utf-8"


def tail_bytes_enabled_default() -> int:
    """返回尾读窗口字节数；``0`` 表示禁用尾读。

    读取环境变量 ``FENGJI_TAIL_READ_BYTES``：
    - 未设置 / 非法值 -> ``DEFAULT_TAIL_BYTES``
    - ``0`` / ``off`` / ``false`` -> ``0``（禁用，调用方走全量读取）
    """
    raw = str(os.environ.get("FENGJI_TAIL_READ_BYTES", "") or "").strip().lower()
    if not raw:
        return DEFAULT_TAIL_BYTES
    if raw in {"0", "off", "false", "no", "disable", "disabled"}:
        return 0
    try:
        value = int(raw)
    except ValueError:
        return DEFAULT_TAIL_BYTES
    return value if value > 0 else 0


def read_csv_tail(
    path: Path | str,
    *,
    max_bytes: int | None = None,
    min_rows: int = MIN_TAIL_ROWS,
) -> tuple[pd.DataFrame | None, bool]:
    """读取 CSV 尾部窗口。

    返回 ``(frame, complete)``：
    - ``complete=True``：返回的是**整个文件**（文件小于窗口，结果与全量读取一致）。
    - ``complete=False``：返回的是尾部窗口子集，行数已过 ``min_rows`` 下限校验。
    - ``frame=None``：尾读不可用，调用方**必须**回退全量 ``pd.read_csv``。
    """
    path = Path(path)
    if max_bytes is None:
        max_bytes = tail_bytes_enabled_default()
    if max_bytes <= 0:
        return (None, False)
    if not path.exists():
        return (None, False)

    try:
        size = path.stat().st_size
    except OSError:
        return (None, False)

    # 小文件直接全读：省掉 seek/拼表头的开销，且结果天然完整。
    if size <= max_bytes:
        try:
            return (pd.read_csv(path), True)
        except Exception:
            return (None, False)

    try:
        with open(path, "rb") as handle:
            handle.seek(size - max_bytes)
            raw = handle.read(max_bytes)

        # 丢弃首行残片（seek 落点在行中间）。
        first_break = raw.find(b"\n")
        if first_break == -1:
            return (None, False)
        raw = raw[first_break + 1 :]

        # 末行无换行符 => 文件可能正在被写入，可能有半行；不猜，回退全量。
        if not raw.endswith(b"\n"):
            return (None, False)

        with open(path, "r", encoding=_ENCODING, errors="replace") as handle:
            header = handle.readline()
        if not header.strip():
            return (None, False)

        text = raw.decode(_ENCODING, errors="replace")
        frame = pd.read_csv(io.StringIO(header + text))
    except Exception:
        return (None, False)

    if frame is None or len(frame) < min_rows:
        return (None, False)
    return (frame, False)
