"""A股 K 线增量同步（新浪通道）——补齐 60m / 15m 并滚动更新日线，写回本地数据库。

背景
----
`market_coverage.filter_strategies_for_a_stock_data()` 会按历史行数筛掉定式：

    A_STOCK_H1_MIN_ROWS_DS07_DS08 = 500   # 不足 → 跳过 DS07/DS08
    A_STOCK_M15_MIN_ROWS_DS09     = 800   # 不足 → 跳过 DS09

此前 A 股只有约 128 根 60m（东财 klt=60 上限）、完全没有 15m，导致 A 股回测长期
只能跑日线定式 DS01–DS06。新浪 scale=N 通道单次可返回最多 1023 根，足以跨过门槛。

另一个容易踩的坑：日线若停留在旧日期，`assign_session_date()` 会按"日线交易日集合"
过滤 15m，两者无交集时 15m 会被整表清空，DS09 随之静默产出 0 信号。因此日线必须
保持滚动更新。

增量语义
--------
- 缓存已存在且行数达标 → 跳过，不重复请求（默认行为）。
- 日线额外按"新鲜度"判定：最新一根距今超过 stale_days 即需更新（默认 1 天）。
- 抓取结果与已有 CSV **合并去重**（按 date），而不是覆盖——新浪单次上限 1023 根，
  直接覆盖会把已有的更长历史（如 6 年日线）缩短。
- `--force` 强制重拉。

产出物即可被回测直接使用，`src/backtest_a_stock_fengji.py:512` 已经会读取
`{code}_15m_qfq.csv` 并据此放行 DS09，无需改动策略侧代码。

用法（仓库根目录执行）
----------------------
    python scripts\\sync_a_stock_kline.py                      # 补 60m + 15m + 滚动日线
    python scripts\\sync_a_stock_kline.py --periods 15m        # 只补 15m
    python scripts\\sync_a_stock_kline.py --limit 5            # 先小规模试跑
    python scripts\\sync_a_stock_kline.py --only 002414,000021 # 指定代码
    python scripts\\sync_a_stock_kline.py --force              # 强制刷新全部
    python scripts\\sync_a_stock_kline.py --dry-run            # 只看待同步清单

不改任何策略/规则/回测逻辑，仅维护数据缓存与本地数据库。
"""
from __future__ import annotations

import argparse
import re
import sys
import time
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))
sys.path.insert(0, str(REPO_ROOT / "packages" / "fengji_core"))

from backtest_a_stock_fengji import fetch_sina_kline  # noqa: E402
from market_data_store import connect as connect_market_db  # noqa: E402
from market_data_store import import_frame, init_db  # noqa: E402

try:  # 门槛以 fengji_core 单一真源为准，取不到时退回当前已知值
    from fengji_core.market_coverage import (  # noqa: E402
        A_STOCK_H1_MIN_ROWS_DS07_DS08,
        A_STOCK_M15_MIN_ROWS_DS09,
    )
except Exception:  # noqa: BLE001 - fengji_core 不可导入时不影响数据同步
    A_STOCK_H1_MIN_ROWS_DS07_DS08 = 500
    A_STOCK_M15_MIN_ROWS_DS09 = 800


# 新浪 scale 通道的上限；实际返回可能更少（次新股/长期停牌）
START = "20200101"
END = "20500101"
SLEEP_SECONDS = 0.6
UNKNOWN_AGE = 10**6  # 无法判定新鲜度时视为需要更新


@dataclass(frozen=True)
class PeriodSpec:
    """一个周期的抓取规格。"""

    key: str
    suffix: str  # CSV 文件名片段，与回测侧约定一致
    sina_scale: int
    timeframe: str  # 写入 sqlite 的周期（经 normalize_timeframe 归一化）
    min_rows: int  # 低于此值视为覆盖不足
    unlocks: str  # 达标后解锁的定式，仅用于提示
    stale_days: int  # 最新一根距今超过该天数则需更新；0=不做新鲜度判定


PERIOD_SPECS: tuple[PeriodSpec, ...] = (
    PeriodSpec("15m", "15m", 15, "15m", A_STOCK_M15_MIN_ROWS_DS09, "DS09", 0),
    PeriodSpec("60m", "60m", 60, "1H", A_STOCK_H1_MIN_ROWS_DS07_DS08, "DS07/DS08", 0),
    # 日线必须滚动更新：其交易日集合决定 15m 的 session 归属，过期会让 DS09 静默归零。
    # 阈值取 3 天以容忍周末/节假日，否则每周一都会被判定为过期。
    PeriodSpec("1d", "1D", 240, "1D", 0, "日线定式/DS09 前提", 3),
)


def _reconfigure_stdout() -> None:
    """Windows 控制台默认可能是 GBK，避免中文提示抛 UnicodeEncodeError。"""
    try:
        sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    except Exception:  # noqa: BLE001 - 老版本 Python 无此方法
        pass


def cache_path_for(cache_root: Path, code: str, spec: PeriodSpec) -> Path:
    return cache_root / f"{code}_{spec.suffix}_qfq.csv"


def count_rows(path: Path) -> int:
    """统计 CSV 数据行数（不含表头），文件损坏/缺失时返回 0。"""
    try:
        with path.open("r", encoding="utf-8-sig") as handle:
            return max(0, sum(1 for _ in handle) - 1)
    except OSError:
        return 0


def last_bar_age_days(path: Path) -> int:
    """最新一根 K 线距今的天数；无法解析时返回 UNKNOWN_AGE。"""
    try:
        frame = pd.read_csv(path, usecols=["date"])
        if frame.empty:
            return UNKNOWN_AGE
        last = pd.to_datetime(frame["date"], errors="coerce").max()
        if pd.isna(last):
            return UNKNOWN_AGE
        return int((pd.Timestamp.now().normalize() - last.normalize()).days)
    except Exception:  # noqa: BLE001 - 任意解析失败都按"需要更新"处理
        return UNKNOWN_AGE


def collect_codes(cache_root: Path) -> list[str]:
    """从现有缓存反推 A 股代码池（`{code}_{period}_qfq.csv`）。"""
    codes: set[str] = set()
    for path in cache_root.glob("*_qfq.csv"):
        match = re.match(r"^(\d{6})_", path.name)
        if match:
            codes.add(match.group(1))
    return sorted(codes)


def merge_into_cache(old: pd.DataFrame, new: pd.DataFrame, cache_path: Path) -> pd.DataFrame:
    """把新数据与已有缓存按 date 合并去重后写回，返回合并结果。

    新浪单次只返回最近 1023 根；若直接覆盖会把已有更长历史截短，
    因此对日线等长周期必须合并。
    """
    if old.empty:
        return new
    old.columns = [str(c).strip().lower() for c in old.columns]
    shared = [c for c in new.columns if c in old.columns]
    if "date" not in shared:
        return new
    merged = pd.concat([old[shared], new[shared]], ignore_index=True)
    merged["date"] = pd.to_datetime(merged["date"], errors="coerce")
    merged = (
        merged.dropna(subset=["date"])
        .drop_duplicates(subset=["date"], keep="last")
        .sort_values("date")
        .reset_index(drop=True)
    )
    merged.to_csv(cache_path, index=False, encoding="utf-8")
    return merged


def sync_one(
    code: str,
    spec: PeriodSpec,
    cache_root: Path,
    conn,
    *,
    write_db: bool,
) -> tuple[str, int, str]:
    """同步单只股票单个周期，返回 (状态, 行数, 说明)。

    状态：ok=达标 / short=不足阈值 / fail=请求失败
    """
    cache_path = cache_path_for(cache_root, code, spec)

    # fetch_sina_kline 内部会把结果写回同一路径，因此旧数据必须先读进内存，
    # 抓取成功后再合并；否则旧历史会被覆盖丢失。
    old_frame = pd.DataFrame()
    if cache_path.exists():
        try:
            old_frame = pd.read_csv(cache_path)
        except Exception:  # noqa: BLE001 - 旧缓存损坏则放弃合并，直接以新数据为准
            old_frame = pd.DataFrame()

    try:
        frame = fetch_sina_kline(
            code, spec.sina_scale, START, END, cache_path, refresh=True
        )
    except Exception as exc:  # noqa: BLE001 - 收集失败原因，继续处理其余股票
        return "fail", 0, str(exc)

    if not old_frame.empty:
        try:
            frame = merge_into_cache(old_frame, frame, cache_path)
        except Exception as exc:  # noqa: BLE001 - 合并失败不应丢掉本次抓取结果
            return "short", len(frame), f"合并失败(已写入新数据): {exc}"

    rows = len(frame)
    if write_db and conn is not None and rows:
        try:
            import_frame(conn, frame, "A_STOCK", code, spec.timeframe, "sina", name=code)
        except Exception as exc:  # noqa: BLE001 - 写库失败不阻塞 CSV 落地
            return ("short" if rows < spec.min_rows else "ok"), rows, f"写库失败: {exc}"

    if rows < spec.min_rows:
        return "short", rows, f"不足 {spec.min_rows} 根（次新股或长期停牌）"
    return "ok", rows, ""


def summarize(cache_root: Path, codes: list[str], specs: tuple[PeriodSpec, ...]) -> None:
    """打印当前覆盖率与新鲜度，判断各定式是否已解锁。"""
    print("\n=== 当前覆盖 ===")
    for spec in specs:
        paths = [cache_path_for(cache_root, c, spec) for c in codes]
        counts = [count_rows(p) for p in paths]
        eligible = sum(1 for n in counts if n >= spec.min_rows)
        ages = [last_bar_age_days(p) for p in paths if count_rows(p) > 0]
        stale = sum(1 for a in ages if a > max(spec.stale_days, 1))
        fresh = max(ages) if ages else -1
        print(
            f"{spec.key:>3}: 达标 {eligible}/{len(codes)} (>= {spec.min_rows} 根)"
            f" → {'已解锁' if eligible == len(codes) else '部分解锁' if eligible else '未解锁'} {spec.unlocks}"
            f"；最新距今 {fresh} 天，过期 {stale} 只"
        )


def build_todo(
    cache_root: Path,
    codes: list[str],
    specs: tuple[PeriodSpec, ...],
    *,
    force: bool,
    stale_override: int | None,
) -> list[tuple[str, PeriodSpec, str]]:
    """列出需要请求的 (code, spec, 原因)。"""
    todo: list[tuple[str, PeriodSpec, str]] = []
    for spec in specs:
        stale_days = stale_override if stale_override is not None else spec.stale_days
        for code in codes:
            path = cache_path_for(cache_root, code, spec)
            rows = count_rows(path)
            if force:
                todo.append((code, spec, "强制刷新"))
                continue
            if rows < spec.min_rows:
                todo.append((code, spec, f"仅 {rows} 根 < {spec.min_rows}"))
                continue
            if stale_days > 0:
                age = last_bar_age_days(path)
                if age > stale_days:
                    todo.append((code, spec, f"最新距今 {age} 天 > {stale_days}"))
    return todo


def main() -> int:
    _reconfigure_stdout()

    parser = argparse.ArgumentParser(description="A股 K 线增量同步（新浪通道）")
    parser.add_argument("--cache-dir", default="data/a_stock")
    parser.add_argument("--db", default="data/market_data.sqlite")
    parser.add_argument("--periods", default="60m,15m,1d", help="逗号分隔，可选 15m/60m/1d")
    parser.add_argument("--limit", type=int, default=0, help="只处理前 N 只（0=全部）")
    parser.add_argument("--only", default="", help="逗号分隔的股票代码，只处理这些")
    parser.add_argument("--sleep", type=float, default=SLEEP_SECONDS, help="请求间隔秒")
    parser.add_argument("--force", action="store_true", help="忽略门槛与新鲜度，强制重拉")
    parser.add_argument(
        "--stale-days",
        type=int,
        default=None,
        help="覆盖所有周期的新鲜度阈值（天），默认按各周期内置值",
    )
    parser.add_argument("--no-db", action="store_true", help="不写回 sqlite")
    parser.add_argument("--dry-run", action="store_true", help="只列出待同步清单")
    args = parser.parse_args()

    wanted = [p.strip().lower() for p in args.periods.split(",") if p.strip()]
    specs = tuple(s for s in PERIOD_SPECS if s.key in wanted)
    if not specs:
        print(f"没有匹配的周期: {args.periods}（可选 15m/60m/1d）")
        return 2

    cache_root = Path(args.cache_dir)
    cache_root.mkdir(parents=True, exist_ok=True)

    if args.only:
        codes = [c.strip().zfill(6) for c in args.only.split(",") if c.strip()]
    else:
        codes = collect_codes(cache_root)
    if args.limit > 0:
        codes = codes[: args.limit]

    if not codes:
        print(f"未找到股票代码池，检查 --cache-dir={cache_root} 下是否有 *_qfq.csv")
        return 1

    todo = build_todo(
        cache_root, codes, specs, force=args.force, stale_override=args.stale_days
    )

    print(
        f"代码池 {len(codes)} 只，待同步 {len(todo)} 项"
        f"（周期: {','.join(s.key for s in specs)}"
        f"{'，强制刷新' if args.force else ''}）"
    )
    if args.dry_run:
        preview = [f"{c}:{s.key}({why})" for c, s, why in todo[:15]]
        print("dry-run 预览: " + ", ".join(preview) + ("..." if len(todo) > 15 else ""))
        return 0

    if not todo:
        summarize(cache_root, codes, specs)
        print("全部已达门槛且新鲜，无需同步")
        return 0

    conn = None
    if not args.no_db:
        conn = connect_market_db(Path(args.db))
        init_db(conn)

    tally = {"ok": 0, "short": 0, "fail": 0}
    failures: list[str] = []
    try:
        for idx, (code, spec, why) in enumerate(todo, start=1):
            status, rows, note = sync_one(
                code, spec, cache_root, conn, write_db=not args.no_db
            )
            tally[status] = tally.get(status, 0) + 1
            if status == "fail":
                failures.append(f"{code}/{spec.key}: {note}")
            tag = {"ok": "OK  ", "short": "WARN", "fail": "FAIL"}[status]
            extra = f" — {note}" if note else ""
            print(f"[{idx}/{len(todo)}] {tag} {code} {spec.key}（{why}）: -> {rows}{extra}")
            if args.sleep > 0:
                time.sleep(args.sleep)
    finally:
        if conn is not None:
            conn.close()

    print(f"\n完成: 达标 {tally['ok']}, 不足 {tally['short']}, 失败 {tally['fail']}")
    if failures:
        print(f"失败明细（{len(failures)} 项，可重跑本脚本续传）:")
        for line in failures[:15]:
            print(f"  {line}")
        if len(failures) > 15:
            print("  ...")

    summarize(cache_root, codes, specs)
    return 0 if tally["fail"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
