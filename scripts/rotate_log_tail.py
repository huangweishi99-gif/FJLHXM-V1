"""跨平台日志尾部截断工具：文件超过阈值时只保留末尾一段（幂等、原地截断）。

背景：国内/海外 watchdog 每分钟拉起的监控进程日志（pending/radar/paper/data 泵及
*_err.log）都是无上限追加，长期运行会无限增长。本工具由两端 watchdog 定期调用，
把超过 ``--max-bytes`` 的文件裁剪为末尾 ``--keep-bytes``，避免手工清理与磁盘占满。

安全设计：
- 只处理显式传入的路径；不做目录遍历/通配展开。
- 尾部保留起点推进到行首（丢弃被截断的半行），保证日志首行完整可读。
- **原地截断、保持 inode**（读尾 → ``ftruncate(0)`` → 写回尾部）：日志 writer 的
  文件句柄始终有效、无感知。若用「临时文件 + ``os.replace``」原子替换，Linux 下
  活跃 writer 会继续写已被替换的旧 inode（日志静默丢失），Windows 下 ``cmd >>``
  打开的文件句柄不含 DELETE 共享，``os.replace`` 必然失败 —— 两端都治理不了活跃
  大日志，故不采用替换方案。
- 截断与 writer 追加之间有一个极小的竞态窗口（毫秒级）：期间新写入可能被丢弃或
  落到尾部片段之间。对本工具的用途（治理无上限增长的低频残留）可接受。
- Windows 平台限制：被 ``cmd >>``/``2>>`` 重定向的常驻进程日志在进程存活期间不
  共享写权限（``open("r+b")`` 会 PermissionError），本工具只能在该进程退出后截断。
  这是平台文件共享语义，非工具缺陷。``FENGJI_ROTATE_DEBUG=1`` 时会把被锁文件跳过
  的原因输出到 stderr 便于诊断。
- 空文件 / 小于阈值文件 / 不存在路径一律跳过，退出码 0。

用法：
    python scripts/rotate_log_tail.py [--max-bytes N] [--keep-bytes N] FILE...
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


def _bounded_tail(raw: bytes, keep_bytes: int) -> bytes:
    """取 raw 的末尾 keep_bytes；若起点截断了一行则推进到下一个换行之后。"""
    if keep_bytes <= 0:
        return b""
    start = max(0, len(raw) - keep_bytes)
    data = raw[start:]
    newline = data.find(b"\n")
    if newline != -1 and newline + 1 < len(data):
        data = data[newline + 1 :]
    return data


def rotate_log_tail(path: Path, *, max_bytes: int, keep_bytes: int) -> bool:
    """超限则保留末尾并原地截断（保持 inode，writer 无感知）；返回是否截断。

    路径不存在、打不开或小于阈值时返回 False。实现为：读文件末尾 ``keep_bytes``
    字节并对齐到行首 → ``truncate(0)`` → 写回尾部。不换 inode，因此活跃 writer
    的句柄继续指向同一文件，追加不会丢失（见模块 docstring 的竞态说明）。
    """
    try:
        size = path.stat().st_size
    except OSError:
        return False
    if size <= max_bytes or size <= 0:
        return False
    keep = max(0, min(keep_bytes, size - 1))
    try:
        with path.open("r+b") as handle:
            handle.seek(size - keep)
            tail = handle.read(keep)
            if not tail:
                return False
            tail = _bounded_tail(tail, keep_bytes)
            handle.seek(0)
            handle.truncate()
            handle.write(tail)
            handle.flush()
        return True
    except OSError as exc:
        # Windows 上被 cmd >> 独占写的日志打不开 r+b：静默跳过；开 debug 可诊断
        if os.environ.get("FENGJI_ROTATE_DEBUG"):
            print(f"[rotate_log_tail] skip {path}: {exc}", file=sys.stderr, flush=True)
        return False


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--max-bytes", type=int, default=100 * 1024 * 1024, help="超过该字节数触发截断（默认 100MB）")
    parser.add_argument("--keep-bytes", type=int, default=8 * 1024 * 1024, help="保留文件末尾字节数（默认 8MB）")
    parser.add_argument("paths", nargs="+", help="要检查的日志文件路径（逐个精确处理）")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    rotated = 0
    for raw in args.paths:
        path = Path(raw)
        if rotate_log_tail(path, max_bytes=args.max_bytes, keep_bytes=args.keep_bytes):
            rotated += 1
            print(f"[rotate_log_tail] truncated {path} (keep tail {args.keep_bytes} bytes)", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
