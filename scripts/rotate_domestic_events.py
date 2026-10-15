"""归档国内端膨胀的 events.jsonl（同盘改名，瞬时完成、可回滚）。

背景：domestic 端 runtime/fengji_pending_orders/events.jsonl 长期只追加不轮转，
涨到 11GB 后 Windows 上 Python 追加打开报 OSError [Errno 22]，导致挂单监控每轮
异常、整轮回滚（成交/平仓/跳过事件与 state 均写不进去），故障自 2026-08-17 起
长期存在。

用法（在 domestic 服务器上执行）：
    python scripts/rotate_domestic_events.py [--max-bytes 268435456] [--force]
"""
from __future__ import annotations

import argparse
import os
import shutil
from datetime import datetime
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="Archive oversized events.jsonl on domestic runtime.")
    parser.add_argument("--root", default=r"C:\Users\Administrator\quant_futures")
    parser.add_argument("--max-bytes", type=int, default=268435456, help="超过该体积才处理（默认 256MB）")
    parser.add_argument("--force", action="store_true", help="忽略体积阈值强制执行")
    args = parser.parse_args()

    root = Path(args.root)
    pending_dir = root / "runtime" / "fengji_pending_orders"
    target = pending_dir / "events.jsonl"

    if not target.exists():
        print("events.jsonl missing - nothing to rotate")
        return 0

    size = target.stat().st_size
    mtime = datetime.fromtimestamp(target.stat().st_mtime)
    print(f"before: size={size} ({size / (1024 ** 3):.2f} GB) mtime={mtime}")

    if size < args.max_bytes and not args.force:
        print(f"size below threshold {args.max_bytes} - skip (use --force)")
        return 0

    arch_dir = root / "runtime" / "archives"
    arch_dir.mkdir(parents=True, exist_ok=True)
    dest = arch_dir / f"events_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jsonl"

    try:
        os.replace(str(target), str(dest))  # 同盘改名：瞬时、可逆
    except OSError as exc:
        print(f"MOVE_FAIL: {exc}")
        print("HINT: 可能有进程持有句柄，先停掉 pending monitor 再重试")
        return 1

    print(f"archived -> {dest} ({dest.stat().st_size} bytes)")
    print(f"events.jsonl now exists={target.exists()} (下一次 append 会自动重建)")
    if dest.exists():
        # 归档后按需压缩提示（不自动删）
        print(f"NOTE: 归档文件保留在 {arch_dir}，确认无需回溯后可手动删除释放空间")

    usage = shutil.disk_usage(str(root))
    print(f"disk: free={usage.free / (1024 ** 3):.2f} GB total={usage.total / (1024 ** 3):.2f} GB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
