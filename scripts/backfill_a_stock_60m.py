"""A股 60m 长历史补齐工具（新浪通道，1023 根）。

用途：东财 klt=60 仅返回约 125 根 60m K 线，H1<500 时回测会跳过 DS07/DS08。
本脚本用新浪 scale=60 datalen=1023 刷新 `data/a_stock/{code}_60m_qfq.csv` 缓存，
并写回 `data/market_data.sqlite`（market=A_STOCK, timeframe=1H）。

用法（在仓库根目录执行）：
    python scripts\\backfill_a_stock_60m.py                # 补齐所有 <500 根的 60m 缓存
    python scripts\\backfill_a_stock_60m.py --limit 5      # 只补前 5 只（分批/试跑）
    python scripts\\backfill_a_stock_60m.py --only 000021,000049  # 指定代码

不改任何策略/规则/回测逻辑，仅维护数据缓存与本地数据库。
"""
from __future__ import annotations

import argparse
import glob
import os
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

from backtest_a_stock_fengji import fetch_sina_kline  # noqa: E402
from market_data_store import connect as connect_market_db  # noqa: E402
from market_data_store import import_frame, init_db  # noqa: E402

MIN_H1_ROWS = 500
START = "20200101"
END = "20500101"
SLEEP_SECONDS = 0.6


def collect_low_rows(cache_root: Path) -> list[tuple[str, int]]:
    """扫描 60m 缓存，返回 (code, rows) 且 rows < MIN_H1_ROWS 的列表。"""
    need: list[tuple[str, int]] = []
    for path in sorted(glob.glob(str(cache_root / "*_60m_qfq.csv"))):
        code = os.path.basename(path).split("_")[0]
        with open(path, "r", encoding="utf-8-sig") as handle:
            rows = max(0, sum(1 for _ in handle) - 1)
        if rows < MIN_H1_ROWS:
            need.append((code, rows))
    return need


def backfill_one(code: str, cache_root: Path, db_path: Path, refresh: bool) -> tuple[bool, int]:
    """刷新单只 60m 缓存并写回 sqlite，返回 (成功?, 行数)。"""
    cache_path = cache_root / f"{code}_60m_qfq.csv"
    try:
        frame = fetch_sina_kline(code, 60, START, END, cache_path, refresh=refresh)
    except Exception as exc:  # noqa: BLE001 - 收集失败信息继续处理其余股票
        print(f"[FAIL] {code}: 下载失败 {exc}")
        return False, 0
    rows = len(frame)
    if rows < MIN_H1_ROWS:
        print(f"[WARN] {code}: 下载后仍仅 {rows} 根（次新股或停牌），未达标")
    try:
        conn = connect_market_db(db_path)
        init_db(conn)
        import_frame(conn, frame, "A_STOCK", code, "1H", "sina", name=code)
        conn.close()
    except Exception as exc:  # noqa: BLE001 - 写库失败不阻塞整体
        print(f"[WARN] {code}: 写回 sqlite 失败（CSV 已更新）: {exc}")
    print(f"[OK] {code}: {rows} 根 -> {cache_path.name}")
    return True, rows


def main() -> int:
    parser = argparse.ArgumentParser(description="A股 60m 长历史补齐（新浪 1023 根）")
    parser.add_argument("--cache-dir", default="data/a_stock")
    parser.add_argument("--db", default="data/market_data.sqlite")
    parser.add_argument("--limit", type=int, default=0, help="只补齐前 N 只（0=全部）")
    parser.add_argument("--only", default="", help="逗号分隔的股票代码，只处理这些")
    parser.add_argument("--no-refresh", action="store_true", help="不强制刷新（读缓存）")
    args = parser.parse_args()

    cache_root = Path(args.cache_dir)
    db_path = Path(args.db)

    if args.only:
        target = [(code.strip(), 0) for code in args.only.split(",") if code.strip()]
    else:
        target = collect_low_rows(cache_root)
    if args.limit > 0:
        target = target[: args.limit]

    if not target:
        print(f"没有需要补齐的股票（全部 >= {MIN_H1_ROWS} 根）")
        return 0

    print(f"待补齐 {len(target)} 只: {[c for c, _ in target[:20]]}{'...' if len(target) > 20 else ''}")
    ok = failed = 0
    for idx, (code, old_rows) in enumerate(target, start=1):
        success, new_rows = backfill_one(code, cache_root, db_path, refresh=not args.no_refresh)
        if success:
            ok += 1
        else:
            failed += 1
        print(f"  [{idx}/{len(target)}] {code}: {old_rows} -> {new_rows}")
        time.sleep(SLEEP_SECONDS)

    print(f"\n完成: 成功 {ok}, 失败 {failed}")
    remaining = collect_low_rows(cache_root)
    print(f"剩余未达标: {len(remaining)} 只 {[c for c, _ in remaining[:15]]}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
