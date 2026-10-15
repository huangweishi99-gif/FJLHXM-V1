"""用模拟盘历史平仓台账回填实时统计桶（幂等、可重放）。

为什么需要：``live_ops_stats`` 是**进程内增量**统计，重启后从零累积；而两端
``runtime/fengji_pending_orders/closed_trades.csv`` 已经躺着几百笔真实（模拟）平仓。
不回填的话：胜率/avg_r 长期为空 → 期望值排序拿不到证据直接退化为按距离排序，
策略衰退监控也永远「证据不足」。

口径说明（与实时完全一致，避免两套数字）：
- 走 ``LiveOpsStats.record`` 同一条路径（同分桶键、同平滑、同评分）。
- 只补 **close 事件**（平仓），不补 skip：skip 由实时链路持续写入，回填历史
  skip 会把成交率分母灌成陈年数据。
- **R 倍数需要 initial_stop**：海外台账自带该列；国内台账（及 fills）没有，
  回填后 avg_r 仍为 None（诚实留空，不用假风险值），胜率/avg_net/止损率照常可用。

幂等：已导入的平仓 key 记录在 ``{MARKET}_backfill_state.json``，重复执行只导入
新增行；``--reset`` 清空统计与状态后全量重灌。

用法（在服务器上执行）：
    python scripts/backfill_ops_stats.py --market CRYPTO            # 海外
    python scripts/backfill_ops_stats.py --market FUTURES --dry-run  # 国内先看摘要
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages" / "fengji_core"))

from fengji_core.live_ops_stats import LiveOpsStats, build_close_event, stats_path_for  # noqa: E402

# 各市场台账默认位置（相对 runtime root）
DEFAULT_CLOSED_CSV = "runtime/fengji_pending_orders/closed_trades.csv"


def _read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        raise SystemExit(f"closed csv not found: {path}")
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def _trade_key(row: dict[str, str]) -> str:
    """平仓业务键：优先 order_id，其次 trade_key（国内形如 pending|XXX-DS01-...）。

    **不能把 exit_time/closed_at 放进兜底键**：台账里同一笔平仓被重复 append 时，
    只有记录时间不同（入场时间/价格、出场价格都一样），含记录时间就会误判成两笔。
    同一 symbol+strategy+入场时间+入场价 但出场价不同（分批平仓）仍是两笔。
    """
    for field in ("order_id", "trade_key", "id"):
        value = str(row.get(field) or "").strip()
        if value:
            return value
    return "|".join(
        str(row.get(field) or "")
        for field in ("symbol", "strategy_id", "entry_time", "entry_price", "exit_price")
    )


def _to_close_event(row: dict[str, str]) -> dict[str, Any]:
    """台账行 → close 事件（字段名兼容海外/国内两套台账）。"""
    exit_reason = str(row.get("exit_reason") or row.get("reason") or "").strip()
    return {
        "event_type": "close",
        "strategy_id": str(row.get("strategy_id") or "UNKNOWN").strip().upper(),
        "symbol": str(row.get("symbol") or "").strip(),
        "side": row.get("side") or row.get("direction") or "",
        "entry_price": row.get("entry_price") or "",
        "exit_price": row.get("exit_price") or "",
        # 海外台账有 initial_stop；国内没有 → 留空（R 记为 None，不用假值）
        "initial_stop": row.get("initial_stop") or row.get("stop_price") or "",
        "net_pnl": row.get("net_pnl") or "",
        "exit_reason": exit_reason,
        "time": str(row.get("closed_at") or row.get("event_time") or ""),
        "order_id": _trade_key(row),
    }


def _load_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"imported_keys": [], "sources": {}}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {"imported_keys": [], "sources": {}}
    data.setdefault("imported_keys", [])
    data.setdefault("sources", {})
    return data


def _atomic_write(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2, default=str)
        os.replace(tmp, path)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def _summarize(stats_file: Path, market: str) -> str:
    if not stats_file.exists():
        return "no stats file"
    data = json.loads(stats_file.read_text(encoding="utf-8"))
    by_strategy: dict[str, dict[str, float]] = {}
    # 桶里没有 strategy_id 列，策略名只能从桶键前缀取（形如 DS01|camp=...）
    for key, bucket in (data.get("buckets") or {}).items():
        name = str(key).split("|")[0].strip().upper() or "UNKNOWN"
        slot = by_strategy.setdefault(name, {"count": 0.0, "wins": 0.0, "r_sum": 0.0, "r_n": 0.0, "net_sum": 0.0})
        count = float(bucket.get("count") or 0.0)
        slot["count"] += count
        slot["wins"] += float(bucket.get("wins") or 0.0)
        slot["r_sum"] += float(bucket.get("r_sum") or 0.0)
        slot["r_n"] += float(bucket.get("r_n") or 0.0)
        slot["net_sum"] += float(bucket.get("net_sum") or 0.0)
    lines = [f"market={market} events_total={data.get('events_total')} buckets={len(data.get('buckets') or {})} recent={len(data.get('recent') or [])}"]
    for name in sorted(by_strategy):
        slot = by_strategy[name]
        count = slot["count"]
        if not count:
            continue
        wr = slot["wins"] / count
        avg_r = (slot["r_sum"] / slot["r_n"]) if slot["r_n"] else None
        avg_net = slot["net_sum"] / count
        r_text = f"{avg_r:.2f}" if avg_r is not None else "n/a(无 initial_stop)"
        lines.append(f"  {name}: n={int(count)} win_rate={wr:.1%} avg_r={r_text} avg_net={avg_net:.2f}")
    return "\n".join(lines)


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Backfill live ops stats from simulated closed-trade ledger.")
    parser.add_argument("--root", default=str(ROOT))
    parser.add_argument("--market", required=True, help="CRYPTO / FUTURES")
    parser.add_argument("--closed-csv", default="", help=f"默认 {DEFAULT_CLOSED_CSV}（相对 root）")
    parser.add_argument("--stats-file", default="", help="默认 runtime/fengji_ops_stats/{MARKET}_ops_stats.json")
    parser.add_argument("--state-file", default="", help="默认 runtime/fengji_ops_stats/{MARKET}_backfill_state.json")
    parser.add_argument("--reset", action="store_true", help="清空统计与导入状态后全量重灌")
    parser.add_argument("--dry-run", action="store_true", help="只打印将要导入的条数，不写入")
    args = parser.parse_args(list(argv) if argv is not None else None)

    root = Path(args.root)
    market = str(args.market or "UNKNOWN").strip().upper()
    closed_csv = Path(args.closed_csv) if args.closed_csv else (root / DEFAULT_CLOSED_CSV)
    if not closed_csv.is_absolute():
        closed_csv = root / closed_csv
    stats_file = Path(args.stats_file) if args.stats_file else stats_path_for(market, root / "runtime")
    if not stats_file.is_absolute():
        stats_file = root / stats_file
    state_file = Path(args.state_file) if args.state_file else (stats_file.parent / f"{market}_backfill_state.json")
    if not state_file.is_absolute():
        state_file = root / state_file

    rows = _read_csv(closed_csv)
    state = {} if args.reset else _load_state(state_file)
    imported = set(state.get("imported_keys") or [])

    # 台账里同一笔平仓可能被重复 append（历史上 state 写不进去时每轮重放），
    # 因此批次内先按 trade_key 去重，避免把同一笔 counted 多次、胜率虚高。
    unique: dict[str, dict[str, str]] = {}
    duplicates = 0
    for row in rows:
        key = _trade_key(row)
        if key in imported:
            continue
        if key in unique:
            duplicates += 1
            continue
        unique[key] = row
    pending = list(unique.values())
    print(
        f"closed_csv={closed_csv} rows={len(rows)} already_imported={len(imported)} "
        f"duplicate_rows={duplicates} new={len(pending)}"
    )

    if args.dry_run:
        for row in pending[:5]:
            print("  sample:", _to_close_event(row))
        print("DRY-RUN: no write")
        return 0

    if args.reset and stats_file.exists():
        stats_file.unlink()
        print(f"reset: removed {stats_file}")

    if pending:
        events = [build_close_event(_to_close_event(row)) for row in pending]
        stats = LiveOpsStats(stats_file, market)
        counted = stats.record(events)
        print(f"imported close events: {counted}/{len(events)}")
        state["imported_keys"] = sorted(imported | {_trade_key(row) for row in pending})
        state.setdefault("sources", {})[str(closed_csv)] = len(rows)
        state["updated_at"] = str(Path(closed_csv).name)
        _atomic_write(state_file, state)
    else:
        print("nothing new to import")

    print(_summarize(stats_file, market))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
