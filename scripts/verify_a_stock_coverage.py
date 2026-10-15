"""A股 K 线覆盖率核对工具（60m / 15m，CSV 缓存 vs sqlite）。

用途
----
`market_coverage.filter_strategies_for_a_stock_data()` 按历史行数筛定式：

    H1(60m) < 500 → 跳过 DS07/DS08
    M15(15m) < 800 → 跳过 DS09

本脚本从三个维度核对门槛是否被满足，用于同步前后、以及定时任务的健康检查：
1) CSV 缓存行数（回测实际读取的文件）
2) sqlite `bars` 表行数（`data-source db` 模式读取的来源）
3) 两者是否一致——不一致说明忘记写库，会导致两种取数模式结论不同

用法（仓库根目录执行）
----------------------
    python scripts\\verify_a_stock_coverage.py
    python scripts\\verify_a_stock_coverage.py --fail-under 0.95   # 覆盖率低于阈值返回 1
"""
from __future__ import annotations

import argparse
import re
import sqlite3
import sys
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "packages" / "fengji_core"))

try:  # 门槛以 fengji_core 单一真源为准
    from fengji_core.market_coverage import (  # noqa: E402
        A_STOCK_H1_MIN_ROWS_DS07_DS08,
        A_STOCK_M15_MIN_ROWS_DS09,
    )
except Exception:  # noqa: BLE001 - 不可导入时退回已知值
    A_STOCK_H1_MIN_ROWS_DS07_DS08 = 500
    A_STOCK_M15_MIN_ROWS_DS09 = 800


@dataclass(frozen=True)
class Check:
    key: str
    suffix: str
    timeframe: str
    min_rows: int
    unlocks: str


CHECKS: tuple[Check, ...] = (
    Check("60m", "60m", "1H", A_STOCK_H1_MIN_ROWS_DS07_DS08, "DS07/DS08"),
    Check("15m", "15m", "15m", A_STOCK_M15_MIN_ROWS_DS09, "DS09"),
)


def _reconfigure_stdout() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    except Exception:  # noqa: BLE001
        pass


def csv_rows(path: Path) -> int:
    try:
        with path.open("r", encoding="utf-8-sig") as handle:
            return max(0, sum(1 for _ in handle) - 1)
    except OSError:
        return 0


def collect_codes(cache_root: Path) -> list[str]:
    codes: set[str] = set()
    if not cache_root.is_dir():
        return []
    for path in cache_root.glob("*_qfq.csv"):
        match = re.match(r"^(\d{6})_", path.name)
        if match:
            codes.add(match.group(1))
    return sorted(codes)


def load_db_rows(db_path: Path, timeframe: str) -> dict[str, int]:
    """返回 {symbol: bars 行数}；库不存在或无数据返回空 dict。"""
    if not db_path.exists():
        return {}
    conn = sqlite3.connect(str(db_path))
    try:
        rows = conn.execute(
            "SELECT symbol, COUNT(*) AS n FROM bars "
            "WHERE market='A_STOCK' AND timeframe=? GROUP BY symbol",
            (timeframe,),
        ).fetchall()
        return {str(r[0]).upper(): int(r[1]) for r in rows}
    except sqlite3.Error as exc:
        print(f"[DB] 查询失败 {timeframe}: {exc}")
        return {}
    finally:
        conn.close()


def main() -> int:
    _reconfigure_stdout()
    parser = argparse.ArgumentParser(description="A股 60m/15m 覆盖率核对")
    parser.add_argument("--cache-dir", default=str(REPO_ROOT / "data" / "a_stock"))
    parser.add_argument("--db", default=str(REPO_ROOT / "data" / "market_data.sqlite"))
    parser.add_argument(
        "--fail-under",
        type=float,
        default=0.0,
        help="CSV 覆盖率低于该比例(0-1)时返回退出码 1，默认 0=始终返回 0",
    )
    parser.add_argument("--verbose", action="store_true", help="列出未达标明细")
    args = parser.parse_args()

    cache_root = Path(args.cache_dir)
    codes = collect_codes(cache_root)
    if not codes:
        print(f"未找到 A 股缓存: {cache_root}")
        return 1

    db_cache: dict[str, dict[str, int]] = {}
    overall_ok = True

    print(f"代码池: {len(codes)} 只\n")
    for check in CHECKS:
        below_csv: list[tuple[str, int]] = []
        below_db: list[tuple[str, int]] = []
        mismatched: list[tuple[str, int, int]] = []

        if check.timeframe not in db_cache:
            db_cache[check.timeframe] = load_db_rows(Path(args.db), check.timeframe)
        db_rows = db_cache[check.timeframe]

        for code in codes:
            n_csv = csv_rows(cache_root / f"{code}_{check.suffix}_qfq.csv")
            if n_csv < check.min_rows:
                below_csv.append((code, n_csv))
            n_db = db_rows.get(code.upper(), 0)
            if n_db < check.min_rows:
                below_db.append((code, n_db))
            if n_csv >= check.min_rows and abs(n_csv - n_db) > max(2, n_csv // 20):
                # CSV 达标但库里行数明显偏少 → 两种取数模式结论会不一致
                mismatched.append((code, n_csv, n_db))

        eligible = len(codes) - len(below_csv)
        ratio = eligible / len(codes) if codes else 0.0
        status = "已解锁" if eligible == len(codes) else ("部分解锁" if eligible else "未解锁")
        print(
            f"[{check.key}] CSV 达标 {eligible}/{len(codes)} ({ratio:.1%}) "
            f"→ {status} {check.unlocks}"
        )
        print(f"   未达标(CSV) {len(below_csv)} 只；未达标(库 {check.timeframe}) {len(below_db)} 只；"
              f"CSV/库不一致 {len(mismatched)} 只")
        if args.verbose:
            for code, n in below_csv[:20]:
                print(f"   below {code}: csv={n} < {check.min_rows}")
            for code, n_csv, n_db in mismatched[:20]:
                print(f"   mismatch {code}: csv={n_csv} db={n_db}")

        if ratio < args.fail_under:
            overall_ok = False

    print("\n提示：缺数据用 scripts\\sync_a_stock_kline.py 补齐（增量，只请求未达标项）。")
    return 0 if overall_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
