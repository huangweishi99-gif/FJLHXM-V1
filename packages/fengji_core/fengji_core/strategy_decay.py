"""策略衰退（alpha decay）检测：近期表现 vs 历史基线，**纯只读告警**。

为什么需要：策略失效通常不是断崖而是缓慢衰减。没有监控就会一直跑着一个正在
流血的定式。实时统计层（``live_ops_stats``）已经留下最近 N 笔平仓明细，本模块
据此对比「近期窗口」与「历史基线」，显著下滑时给出分级告警。

设计约束：**只观测、不干预** —— 本模块不修改任何交易状态，也不改下单/仓位；
是否据此停用策略由人决定（或后续接入带影子验证的自动降权）。

判定口径（保守，优先避免误报）：
- 近期样本 < ``MIN_RECENT`` 或基线样本 < ``MIN_BASELINE`` 一律不判定（证据不足）；
- 胜率绝对下滑 >= ``WR_DROP`` → warn；
- 近期 avg_r <= 0 且胜率显著下滑 → severe；
- 近期 avg_r 跌到基线的 ``R_RATIO`` 以下 → warn。
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Iterable, Mapping

from fengji_core.context_score import bucket_p_value

DEFAULT_WINDOW = 30
MIN_RECENT = 10
MIN_BASELINE = 30
WR_DROP = 0.15
R_RATIO = 0.5


def _now_text() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _aggregate(items: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    rows = list(items or [])
    r_values = [float(row["r"]) for row in rows if row.get("r") is not None]
    nets = [float(row.get("net_pnl") or 0.0) for row in rows]
    wins = int(sum(int(row.get("win") or 0) for row in rows))
    count = len(rows)
    return {
        "count": count,
        "wins": wins,
        "stops": int(sum(int(row.get("stop") or 0) for row in rows)),
        "win_rate": (wins / count) if count else None,
        "avg_r": (sum(r_values) / len(r_values)) if r_values else None,
        "avg_net": (sum(nets) / count) if count else None,
    }


def _bucket_totals(stats: Mapping[str, Any], prefix: str) -> dict[str, Any]:
    """把某策略名下所有桶的累计量汇总（prefix 为 strategy_id 开头匹配）。"""
    total = {"count": 0, "wins": 0.0, "r_sum": 0.0, "r_n": 0, "net_sum": 0.0}
    for key, bucket in (stats.get("buckets") or {}).items():
        if not str(key).upper().startswith(prefix.upper()):
            continue
        total["count"] += int(bucket.get("count") or bucket.get("closes") or 0)
        total["wins"] += float(bucket.get("wins") or 0.0)
        total["r_sum"] += float(bucket.get("r_sum") or 0.0)
        total["r_n"] += int(bucket.get("r_n") or 0)
        total["net_sum"] += float(bucket.get("net_sum") or 0.0)
    return total


def evaluate_strategy(
    stats: Mapping[str, Any],
    strategy: str,
    *,
    window: int = DEFAULT_WINDOW,
) -> dict[str, Any]:
    """单个策略的衰退评估：近期 window 笔 vs 之前的全部历史。"""
    recent_rows = [
        row
        for row in (stats.get("recent") or [])
        if str(row.get("strategy_id") or "").upper() == strategy.upper()
    ][-window:]
    recent = _aggregate(recent_rows)

    totals = _bucket_totals(stats, strategy)
    baseline_count = int(totals["count"]) - int(recent["count"])
    baseline_wins = float(totals["wins"]) - float(recent["wins"])
    baseline_r_n = int(totals["r_n"]) - sum(1 for row in recent_rows if row.get("r") is not None)
    baseline_r_sum = float(totals["r_sum"]) - sum(float(row["r"]) for row in recent_rows if row.get("r") is not None)
    baseline = {
        "count": baseline_count,
        "wins": baseline_wins,
        "win_rate": (baseline_wins / baseline_count) if baseline_count > 0 else None,
        "avg_r": (baseline_r_sum / baseline_r_n) if baseline_r_n > 0 else None,
        "avg_net": ((float(totals["net_sum"]) - float(recent["avg_net"] or 0.0) * int(recent["count"])) / baseline_count)
        if baseline_count > 0
        else None,
    }

    out: dict[str, Any] = {
        "strategy": strategy.upper(),
        "recent": recent,
        "baseline": baseline,
        "level": None,
        "reasons": [],
        "p_value": None,
        "enough_evidence": False,
    }
    if int(recent["count"]) < MIN_RECENT or baseline_count < MIN_BASELINE:
        out["reasons"].append(
            f"证据不足(近期 {int(recent['count'])}/{MIN_RECENT}，基线 {baseline_count}/{MIN_BASELINE})"
        )
        return out
    out["enough_evidence"] = True

    recent_wr = float(recent["win_rate"])
    base_wr = float(baseline["win_rate"])
    recent_r = recent["avg_r"]
    base_r = baseline["avg_r"]
    drop = base_wr - recent_wr
    out["p_value"] = bucket_p_value(float(recent["wins"]), int(recent["count"]), baseline=base_wr)

    if drop >= WR_DROP:
        out["reasons"].append(f"胜率下滑 {drop:.0%}（{base_wr:.0%} → {recent_wr:.0%}）")
    if base_r is not None and base_r > 0 and recent_r is not None and recent_r <= base_r * R_RATIO:
        out["reasons"].append(f"avg_r 跌至基线 {recent_r / base_r:.0%}（{base_r:.2f} → {recent_r:.2f}）")
    if recent_r is not None and recent_r <= 0 and drop >= WR_DROP:
        out["level"] = "severe"
        out["reasons"].append("近期期望已转负，建议停用并复核定式")
    elif out["reasons"]:
        out["level"] = "warn"
    return out


def detect(
    stats: Mapping[str, Any],
    *,
    strategies: Iterable[str] | None = None,
    window: int = DEFAULT_WINDOW,
) -> dict[str, Any]:
    """对统计快照做全量衰退检测，返回结构化报告。"""
    names = [str(name).upper() for name in strategies] if strategies else sorted(
        {str(row.get("strategy_id") or "").upper() for row in (stats.get("recent") or []) if row.get("strategy_id")}
    )
    results = [evaluate_strategy(stats, name, window=window) for name in names]
    alerts = [item for item in results if item.get("level")]
    return {
        "generated_at": _now_text(),
        "market": stats.get("market"),
        "window": window,
        "strategies": len(results),
        "alerts": alerts,
        "healthy": [item for item in results if not item.get("level") and item.get("enough_evidence")],
        "insufficient": [item for item in results if not item.get("enough_evidence")],
    }


def format_report(report: Mapping[str, Any]) -> str:
    """人类可读摘要（日志/飞书用）。"""
    lines = [
        f"[strategy-decay] market={report.get('market')} window={report.get('window')} "
        f"strategies={report.get('strategies')} alerts={len(report.get('alerts') or [])}"
    ]
    for item in report.get("alerts") or []:
        reasons = "；".join(item.get("reasons") or [])
        lines.append(f"  {item['level'].upper()} {item['strategy']}: {reasons}")
    return "\n".join(lines)
