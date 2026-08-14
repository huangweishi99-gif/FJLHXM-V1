"""A股 60m 覆盖率核对工具（CSV 缓存 vs sqlite vs master summary）。

用法（仓库根目录执行）：
    python scripts\\verify_a_stock_60m_coverage.py

输出：
1) data/a_stock/*_60m_qfq.csv 行数 < 500 的股票
2) data/market_data.sqlite 中 A_STOCK/1H 行数 < 500 的股票
3) results/a_stock_all_sectors_master_summary.csv 中 h1_rows < 500 的板块股票
4) master summary 中 data_warning 是否包含 H1 相关降级提示
"""
from __future__ import annotations

import glob
import os
import sqlite3
import sys
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
MIN_H1 = 500


def csv_rows(path: Path) -> int:
    with open(path, "r", encoding="utf-8-sig") as handle:
        return max(0, sum(1 for _ in handle) - 1)


def main() -> int:
    cache_root = REPO_ROOT / "data" / "a_stock"
    db_path = REPO_ROOT / "data" / "market_data.sqlite"
    master_path = REPO_ROOT / "results" / "a_stock_all_sectors_master_summary.csv"

    csv_below = []
    for path in sorted(glob.glob(str(cache_root / "*_60m_qfq.csv"))):
        code = os.path.basename(path).split("_")[0]
        n = csv_rows(Path(path))
        if n < MIN_H1:
            csv_below.append((code, n))

    db_below = []
    if db_path.exists():
        conn = sqlite3.connect(str(db_path))
        rows = conn.execute(
            "SELECT symbol, COUNT(*) AS n FROM bars "
            "WHERE market='A_STOCK' AND timeframe='1H' "
            "GROUP BY symbol HAVING n BETWEEN 1 AND ? ORDER BY symbol",
            (MIN_H1 - 1,),
        ).fetchall()
        db_below = [(r[0], r[1]) for r in rows]
        conn.close()

    summary_below = []
    summary_old = []
    if master_path.exists():
        master = pd.read_csv(master_path, encoding="utf-8-sig")
        low = master[master["h1_rows"] < MIN_H1]
        summary_below = list(zip(low["symbol"].astype(str), low["h1_rows"].astype(int)))
        warned = master[
            master["h1_rows"] < MIN_H1
        ] if "h1_rows" in master else pd.DataFrame()
        summary_old = [
            (r.symbol, int(r.h1_rows), str(r.data_warning))
            for r in warned.itertuples()
            if not str(r.data_warning).strip() or "DS07" not in str(r.data_warning)
        ]

    print(f"[CSV] 60m 文件: 总计达标 {len(glob.glob(str(cache_root / '*_60m_qfq.csv')))} - 低于{MIN_H1}: {len(csv_below)}")
    for code, n in csv_below:
        print(f"  {code}: {n}")
    print(f"[DB]  A_STOCK/1H 低于{MIN_H1}: {len(db_below)}")
    for code, n in db_below:
        print(f"  {code}: {n}")
    print(f"[SUMMARY] master_summary h1_rows 低于{MIN_H1}: {len(summary_below)}")
    for code, n in summary_below[:30]:
        print(f"  {code}: {n}")
    print(f"[SUMMARY] 旧行且无 DS07 降级提示: {len(summary_old)}")
    for code, n, warn in summary_old[:10]:
        print(f"  {code}: h1={n} data_warning='{warn}'")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
