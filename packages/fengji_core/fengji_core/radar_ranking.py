"""雷达信号的**期望值排序**（可关闭、可影子对比）。

现状问题：``fengji_total_radar`` 按 ``score`` 排序取 top-n，而该 score 其实是
「距触发的远近」（TRIGGERED=0 / CONFIRM_ON_CLOSE=50 / INVALIDATED=80，其余=距离%）。
离触发近与收益高低没有因果关系 —— 选出来的是「最可能马上成交的」，不是「最值得做的」。

本模块提供按**历史期望 R** 排序的能力：
- 期望 = 桶/策略的历史平均 R（``avg_r``），并按样本置信度**收缩**
  （``sample_confidence``）——样本不足的高 R 不会被顶到前面，避免小样本噪声。
- 统计不足（``is_actionable`` 为 False）的信号不给正期望，退回按距离排序，
  保证「没有证据时不改变原有行为」。
- 支持**影子对比**：只输出与实际排序的差异，不改动任何输出文件。

统计源兼容两种：
- 实时：``live_ops_stats`` 写出的 ``runtime/fengji_ops_stats/{MARKET}_ops_stats.json``
- 离线：``context_bucket_stats.csv``（``context_stats`` 产出）

注意：上下文分桶字段（camp / ATR 距离等）目前没随信号带出来，精确桶匹配率很低，
所以默认退化为 **strategy 级**统计（键为 strategy_id）。等上下文快照打通后，
同一套代码可直接用桶级统计。
"""
from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Mapping

from fengji_core.context_score import ACTIONABLE_MIN_SAMPLES, is_actionable

# 样本不足以支撑决策时，期望值按此系数收缩后仍可能为正，故显式置为「无正期望」
NO_EXPECTANCY = None

# 判定「证据充分的负期望」所用样本门槛，与决策闸门同一套（避免两套数字）
NEGATIVE_MIN_SAMPLES = ACTIONABLE_MIN_SAMPLES


def load_bucket_stats(path: str | Path) -> dict[str, dict[str, Any]]:
    """加载桶统计，统一成 {bucket_key: {...指标...}}。支持 JSON（实时）与 CSV（离线）。"""
    source = Path(path)
    if not source.exists():
        return {}
    if source.suffix.lower() == ".json":
        try:
            data = json.loads(source.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}
        return {str(key): dict(value) for key, value in (data.get("buckets") or {}).items()}
    out: dict[str, dict[str, Any]] = {}
    with source.open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            key = str(row.get("bucket_key") or "")
            if not key:
                continue
            entry = dict(row)
            for numeric in ("count", "wins", "avg_r", "avg_net", "win_rate", "win_rate_smoothed", "win_rate_ci_low", "sample_confidence", "signal_score"):
                if entry.get(numeric) not in (None, ""):
                    try:
                        entry[numeric] = float(entry[numeric])
                    except ValueError:
                        entry[numeric] = None
                else:
                    entry[numeric] = None
            out[key] = entry
    return out


def _strategy_of(key: str, entry: Mapping[str, Any]) -> str:
    explicit = str(entry.get("strategy_id") or "").strip().upper()
    if explicit:
        return explicit
    return str(key).split("|")[0].strip().upper()


def strategy_level_stats(stats: Mapping[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """把桶统计按 strategy 汇总（按样本数加权），用于上下文缺失时的降级匹配。"""
    agg: dict[str, dict[str, float]] = {}
    for key, entry in stats.items():
        name = _strategy_of(key, entry)
        slot = agg.setdefault(name, {"count": 0.0, "r_weighted": 0.0, "wins": 0.0, "conf_weighted": 0.0})
        count = float(entry.get("count") or 0.0)
        slot["count"] += count
        slot["wins"] += float(entry.get("wins") or 0.0)
        avg_r = entry.get("avg_r")
        if avg_r is not None:
            slot["r_weighted"] += float(avg_r) * count
        conf = entry.get("sample_confidence")
        if conf is not None:
            slot["conf_weighted"] += float(conf) * count
    out: dict[str, dict[str, Any]] = {}
    for name, slot in agg.items():
        count = slot["count"]
        out[name] = {
            "strategy_id": name,
            "count": int(count),
            "wins": slot["wins"],
            "avg_r": (slot["r_weighted"] / count) if count else None,
            "win_rate": (slot["wins"] / count) if count else None,
            "sample_confidence": (slot["conf_weighted"] / count) if count else 0.0,
        }
    return out


def expectancy_for(entry: Mapping[str, Any] | None) -> float | None:
    """保守期望 R：历史 avg_r 按样本置信度收缩；统计不可信时返回 None（即不给正期望）。"""
    if not entry:
        return NO_EXPECTANCY
    avg_r = entry.get("avg_r")
    if avg_r is None:
        return NO_EXPECTANCY
    try:
        value = float(avg_r)
    except (TypeError, ValueError):
        return NO_EXPECTANCY
    conf = float(entry.get("sample_confidence") or 0.0)
    # 置信度不足（样本太少）→ 期望被压到接近 0，仍可能为正；这里用 is_actionable 兜底
    if not is_actionable({**entry, "count": int(entry.get("count") or 0)}):
        return NO_EXPECTANCY
    return value * conf


def negative_evidence(entry: Mapping[str, Any] | None, *, min_samples: int | None = None) -> bool:
    """证据充分的**负期望**：样本足够且历史平均结果为负。

    与 ``is_actionable`` 刻意分开：后者要求胜率置信下界 > 0.5，回答的是「够不够格
    做多」；而「证据充分地在亏钱」同样是可执行的信息 —— 实测海外 DS01 有 272 笔
    样本、胜率 24.6%、avg_r=-0.21，按原逻辑它只是「没有正期望」，仍与「无证据的
    新策略」同级按距离排，于是继续被优先推荐。
    判负优先用 R（可比），R 缺失（国内台账没有 initial_stop）时用 avg_net。
    """
    if not entry:
        return False
    floor = int(min_samples if min_samples is not None else NEGATIVE_MIN_SAMPLES)
    if int(entry.get("count") or 0) < floor:
        return False
    for field in ("avg_r", "avg_net"):
        raw = entry.get(field)
        if raw is None or raw == "":
            continue
        try:
            return float(raw) < 0.0
        except (TypeError, ValueError):
            continue
    return False


def annotate_rows(
    payload: list[dict[str, Any]],
    stats: Mapping[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    """给每行补 ``expectancy``（None 表示无统计证据）。优先桶级，缺失时降级 strategy 级。

    同时补 ``negative``：样本足够且历史为负 → 排序时垫到「无证据」之后。
    """
    by_strategy = strategy_level_stats(stats)
    annotated: list[dict[str, Any]] = []
    for row in payload:
        item = dict(row)
        strategy = str(item.get("strategy_id") or "").strip().upper()
        entry = stats.get(str(item.get("bucket_key") or "")) or by_strategy.get(strategy)
        item["expectancy"] = expectancy_for(entry)
        item["negative"] = negative_evidence(entry)
        item["stats_count"] = int(entry.get("count") or 0) if entry else 0
        annotated.append(item)
    return annotated


def _sort_key(row: Mapping[str, Any]) -> tuple:
    """排序键三档：正期望 → 无证据（按距离，保持原行为）→ **证据充分的负期望**。"""
    exp = row.get("expectancy")
    score = float(row.get("score") or 0.0)
    symbol = str(row.get("symbol") or "")
    if exp is not None:
        return (0, -float(exp), score, symbol)
    if row.get("negative"):
        return (2, 0.0, score, symbol)
    return (1, 0.0, score, symbol)


def rank_rows(
    payload: list[dict[str, Any]],
    stats: Mapping[str, dict[str, Any]],
    *,
    top_n: int | None = None,
) -> list[dict[str, Any]]:
    """按期望值排序（保守期望降序，无证据者按距离垫后），取 top_n。"""
    ranked = sorted(annotate_rows(payload, stats), key=_sort_key)
    return ranked[:top_n] if top_n else ranked


def shadow_compare(
    payload: list[dict[str, Any]],
    stats: Mapping[str, dict[str, Any]],
    *,
    top_n: int,
) -> dict[str, Any]:
    """影子对比：只报告「按距离」与「按期望」两种 top-n 的差异，不改任何输出。"""
    by_distance = sorted(payload, key=lambda row: (float(row.get("score") or 0.0), str(row.get("symbol") or "")))[:top_n]
    by_expectancy = rank_rows(payload, stats, top_n=top_n)

    def _keys(rows: list[dict[str, Any]]) -> list[str]:
        return [f"{row.get('symbol')}|{row.get('strategy_id')}|{row.get('status')}" for row in rows]

    distance_keys = _keys(by_distance)
    expectancy_keys = _keys(by_expectancy)
    annotated = annotate_rows(payload, stats)
    negatives = sorted(
        {
            f"{row.get('strategy_id')}(n={row.get('stats_count')})"
            for row in annotated
            if row.get("negative")
        }
    )
    return {
        "top_n": top_n,
        "scored_rows": sum(1 for row in annotated if row.get("expectancy") is not None),
        "negative_rows": sum(1 for row in annotated if row.get("negative")),
        "negative_strategies": negatives,
        "enter": [key for key in expectancy_keys if key not in distance_keys],
        "exit": [key for key in distance_keys if key not in expectancy_keys],
        "expectancy_top": [
            {
                "symbol": row.get("symbol"),
                "strategy_id": row.get("strategy_id"),
                "status": row.get("status"),
                "score": row.get("score"),
                "expectancy": row.get("expectancy"),
                "stats_count": row.get("stats_count"),
            }
            for row in by_expectancy[:10]
        ],
    }


def format_shadow_report(report: Mapping[str, Any]) -> str:
    lines = [
        f"[shadow-rank] top_n={report.get('top_n')} 有统计证据的信号={report.get('scored_rows')}",
        f"  换入(按期望上位)={len(report.get('enter') or [])} 换出={len(report.get('exit') or [])}",
        f"  负期望降权={report.get('negative_rows')} "
        f"策略={','.join(report.get('negative_strategies') or []) or '无'}",
    ]
    for key in (report.get("enter") or [])[:10]:
        lines.append(f"    + {key}")
    for key in (report.get("exit") or [])[:10]:
        lines.append(f"    - {key}")
    return "\n".join(lines)
