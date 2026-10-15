"""定式开仓上下文「分桶 + 信号强弱打分」的轻量纯逻辑（离线与实时共用同一口径）。

背景：``context_stats.py`` 面向离线批处理，依赖 pandas / OS 引擎等重模块，不适合
被常驻监控进程（5s 轮询）直接 import。本模块只保留与 DataFrame 无关的纯计算：
分桶键构建、贝叶斯平滑胜率、样本置信度、信号评分与分级。

口径唯一性：离线聚合（``context_stats.aggregate_bucket_stats``）与实时统计
（``live_ops_stats``）都调用这里的 ``score_bucket_row``，避免同一套胜率/评分公式
在两处实现产生漂移。
"""
from __future__ import annotations

import json
import math
import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Mapping

import numpy as np

# 注意：已配置市场（FUTURES/CRYPTO/A_STOCK）的阈值以 data/context_market_calibration.json
# 为准（2026-06-16 校准产物），下面的常量只是无配置时的兜底。
#
# 30 个样本的胜率标准误约 ±9pp，而分桶维度 6 个、桶数动辄上千 —— 在多桶里挑
# 「胜率最高」本质是多重载检验下的过拟合。因此：
#   1) 分级只看胜率的 **Wilson 置信下界**（保守分），不用点估计；
#   2) 供决策（排序/仓位）使用的桶另设更严的门槛，见 ACTIONABLE_MIN_SAMPLES。
MIN_BUCKET_SAMPLES = 30
# 足以支撑交易决策（而非仅展示）的最小样本：低于此值一律视为「证据不足」
ACTIONABLE_MIN_SAMPLES = 80
DEFAULT_PRIOR = 0.5
DEFAULT_PRIOR_STRENGTH = 10
# 胜率置信下界的 z 值（1.96 ≈ 95% 单侧下界）
DEFAULT_Z = 1.96

# V1 分桶维度：枚举直接作键；连续字段按固定阈值切桶
BUCKET_SPECS: list[tuple[str, str]] = [
    ("camp", "enum"),
    ("camp_confirmed", "enum"),
    ("dist_active_high_atr", "atr_dist"),
    ("bar_direction", "enum"),
    ("position_in_range_20", "range_pos"),
    ("market_regime_vol", "enum"),
]

STRATEGY_EXTRA_BUCKETS: dict[str, list[str]] = {
    "DS03": ["peak_key"],
    "DS07": ["h1_merge_type"],
    "DS09": ["boundary_side"],
}

TIER_STRONG = 0.65
TIER_MEDIUM = 0.45
DEFAULT_SCORE_WEIGHTS = {"w_wr": 0.45, "w_r": 0.35, "w_conf": 0.20}


@dataclass(frozen=True)
class BucketProfile:
    name: str
    fields: tuple[tuple[str, str], ...]
    strategy_extras: dict[str, list[str]]
    atr_mode: str = "default"


DEFAULT_BUCKET_PROFILE = BucketProfile("v1", tuple(BUCKET_SPECS), STRATEGY_EXTRA_BUCKETS)

FUTURES_V2_BUCKET_PROFILE = BucketProfile(
    "futures_v2",
    (
        ("camp_confirmed", "enum"),
        ("dist_active_high_atr", "atr_dist"),
        ("bar_direction", "enum"),
    ),
    {"DS03": ["peak_key"]},
    atr_mode="coarse2",
)

BUCKET_PROFILES: dict[str, BucketProfile] = {
    "v1": DEFAULT_BUCKET_PROFILE,
    "futures_v2": FUTURES_V2_BUCKET_PROFILE,
}


def _default_market_calibration() -> dict[str, float | int | bool]:
    return {
        "activate": True,
        "tier_strong": TIER_STRONG,
        "tier_medium": TIER_MEDIUM,
        "min_bucket_samples": MIN_BUCKET_SAMPLES,
        **DEFAULT_SCORE_WEIGHTS,
    }


def _candidate_calibration_paths() -> list[Path]:
    paths: list[Path] = []
    env_path = os.getenv("FENGJI_CONTEXT_CALIBRATION")
    if env_path:
        paths.append(Path(env_path))
    cwd_path = Path.cwd() / "data" / "context_market_calibration.json"
    paths.append(cwd_path)
    for parent in Path(__file__).resolve().parents:
        paths.append(parent / "data" / "context_market_calibration.json")
    return paths


@lru_cache(maxsize=1)
def load_market_calibrations() -> dict[str, Any]:
    for path in _candidate_calibration_paths():
        if path.exists():
            try:
                return json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError as exc:
                raise ValueError(f"invalid context market calibration json: {path}") from exc
    return {"default": _default_market_calibration(), "markets": {}}


def market_calibration(market: str | None) -> dict[str, float | int | bool | str]:
    raw = load_market_calibrations()
    default = _default_market_calibration()
    default.update(raw.get("default") or {})
    market_key = (market or "").upper()
    market_cfg = (raw.get("markets") or {}).get(market_key) or {}
    if market_cfg.get("activate") is False:
        return default
    cfg = {**default, **market_cfg}
    for key in ("w_wr", "w_r", "w_conf", "tier_strong", "tier_medium"):
        cfg[key] = float(cfg[key])
    cfg["min_bucket_samples"] = int(cfg["min_bucket_samples"])
    cfg["activate"] = bool(cfg.get("activate", True))
    if "bucket_profile" in market_cfg:
        cfg["bucket_profile"] = str(market_cfg["bucket_profile"])
    return cfg


def bucket_profile_for_market(market: str | None) -> BucketProfile:
    cfg = market_calibration(market)
    name = str(cfg.get("bucket_profile") or "v1")
    return BUCKET_PROFILES.get(name, DEFAULT_BUCKET_PROFILE)


def bucket_atr_dist(value: Any) -> str:
    val = float(value) if value is not None and not (isinstance(value, float) and np.isnan(value)) else float("nan")
    if np.isnan(val):
        return "UNKNOWN"
    if val <= 0.5:
        return "NEAR"
    if val <= 1.5:
        return "MID"
    return "FAR"


def bucket_range_pos(value: Any) -> str:
    val = float(value) if value is not None and not (isinstance(value, float) and np.isnan(value)) else float("nan")
    if np.isnan(val):
        return "UNKNOWN"
    if val <= 0.33:
        return "LOW"
    if val <= 0.66:
        return "MID"
    return "HIGH"


def bucketize_value(field: str, kind: str, value: Any) -> str:
    if kind == "enum":
        if value is None or (isinstance(value, float) and np.isnan(value)):
            return "UNKNOWN"
        return str(value)
    if kind == "atr_dist":
        return bucket_atr_dist(value)
    if kind == "range_pos":
        return bucket_range_pos(value)
    return str(value) if value is not None else "UNKNOWN"


def bucketize_for_profile(field: str, kind: str, value: Any, profile: BucketProfile) -> str:
    if field == "dist_active_high_atr" and profile.atr_mode == "coarse2":
        base = bucket_atr_dist(value)
        if base in ("NEAR", "MID"):
            return "NEAR_MID"
        if base == "FAR":
            return "FAR"
        return "UNKNOWN"
    return bucketize_value(field, kind, value)


def build_bucket_key(
    row: dict[str, Any],
    strategy_id: str,
    market: str | None = None,
) -> str:
    """按市场分桶配置构建桶键；上下文字段缺失时落 UNKNOWN（实时链路常见）。"""
    market_key = str(market or row.get("market") or "").upper()
    profile = bucket_profile_for_market(market_key or None)
    parts = [str(strategy_id)]
    for field, kind in profile.fields:
        parts.append(f"{field}={bucketize_for_profile(field, kind, row.get(field), profile)}")
    for extra in profile.strategy_extras.get(strategy_id, []):
        val = row.get(extra)
        if val is not None and not (isinstance(val, float) and np.isnan(val)) and str(val).strip():
            parts.append(f"{extra}={val}")
    return "|".join(parts)


def smoothed_rate(successes: float, total: float, prior: float = DEFAULT_PRIOR, strength: float = DEFAULT_PRIOR_STRENGTH) -> float:
    if total <= 0:
        return prior
    return (successes + prior * strength) / (total + strength)


def wilson_lower_bound(successes: float, total: float, z: float = DEFAULT_Z) -> float:
    """胜率的 Wilson 置信下界：小样本稳健，优于 p ± z·sqrt(p(1-p)/n) 正态近似。

    分桶样本少时下界会显著低于点估计，正好用于抑制「小样本高胜率」的假 STRONG。
    """
    if total <= 0:
        return 0.0
    n = float(total)
    p = float(successes) / n
    denom = 1.0 + z * z / n
    centre = p + z * z / (2.0 * n)
    margin = z * math.sqrt(p * (1.0 - p) / n + z * z / (4.0 * n * n))
    return max(0.0, (centre - margin) / denom)


def score_bucket_row(*, count: int, wins: float, avg_r: float, market: str | None = None) -> dict[str, Any]:
    """单桶打分：离线聚合与实时统计共用，保证口径一致。

    count=0 时胜率/评分退化为先验值，分级为 INSUFFICIENT_DATA（与离线一致）。

    输出两个分：
    - ``signal_score``：点估计（平滑胜率），用于展示与对比；
    - ``signal_score_conservative``：把平滑胜率换成 **Wilson 置信下界**，分级只看
      它 —— 样本不足时下界会明显低于点估计，避免小样本噪声被误判成 STRONG。
    """
    cfg = market_calibration(market)
    count_i = int(count)
    win_rate = float(wins) / count_i if count_i > 0 else 0.0
    win_rate_smoothed = smoothed_rate(float(wins), float(count_i))
    win_rate_ci_low = wilson_lower_bound(float(wins), float(count_i))
    avg_r_smoothed = float(avg_r or 0.0)
    sample_confidence = min(1.0, count_i / float(cfg["min_bucket_samples"]))

    def _compose(win_component: float) -> float:
        return float(
            np.clip(
                float(cfg["w_wr"]) * win_component
                + float(cfg["w_r"]) * float(np.clip(avg_r_smoothed, -1.0, 2.0)) / 2.0
                + float(cfg["w_conf"]) * sample_confidence,
                0.0,
                1.0,
            )
        )

    signal_score = _compose(win_rate_smoothed)
    conservative = _compose(win_rate_ci_low)
    return {
        "count": count_i,
        "wins": float(wins),
        "win_rate": win_rate,
        "win_rate_smoothed": win_rate_smoothed,
        "win_rate_ci_low": win_rate_ci_low,
        "avg_r_smoothed": avg_r_smoothed,
        "sample_confidence": sample_confidence,
        "signal_score": signal_score,
        "signal_score_conservative": conservative,
        "signal_tier": classify_tier(conservative, count_i, market=market),
    }


def benjamini_hochberg(pvalues: list[float], alpha: float = 0.05) -> list[bool]:
    """BH（FDR）多重检验校正：返回每个 p 值是否显著（控制错误发现率）。

    分桶维度多 → 桶数上千 → 逐个检验一定会出现假阳性。挑选「优质桶」前应先过
    这一步，否则选出来的是噪声。p 值可用 ``bucket_p_value`` 计算。
    """
    n = len(pvalues)
    if n == 0:
        return []
    order = sorted(range(n), key=lambda i: pvalues[i])
    threshold_idx = -1
    for rank, idx in enumerate(order, start=1):
        if pvalues[idx] <= alpha * rank / n:
            threshold_idx = rank
    cutoff = set(order[:threshold_idx])
    return [i in cutoff for i in range(n)]


def bucket_p_value(wins: float, count: int, baseline: float = 0.5) -> float:
    """单桶胜率相对基线（默认抛硬币）的二项检验双尾 p 值（正态近似）。

    这是多重检验校正的输入；样本很小时 p 值不可靠，故与 MIN_BUCKET_SAMPLES 配合用。
    """
    if count <= 0:
        return 1.0
    p = float(wins) / float(count)
    se = math.sqrt(max(baseline * (1.0 - baseline), 1e-12) / float(count))
    z = (p - baseline) / se
    # 双尾正态近似
    return float(math.erfc(abs(z) / math.sqrt(2.0)))


def is_actionable(
    row: Mapping[str, Any],
    *,
    min_samples: int | None = None,
    baseline: float = 0.5,
) -> bool:
    """该桶统计是否**足以支撑交易决策**（排序/仓位），而不只是展示。

    双重门槛，任一不满足即不可用：
    - 样本数 >= min_samples（默认 ACTIONABLE_MIN_SAMPLES=80，远高于展示用的 30）；
    - 胜率 **置信下界** > baseline（默认抛硬币 0.5）——下界而非点估计，避免
      小样本高胜率的假信号被拿去下单。

    这是「统计可信度」与「统计驱动决策」之间的闸门：展示可以宽松，下单必须严格。
    """
    floor = int(min_samples if min_samples is not None else ACTIONABLE_MIN_SAMPLES)
    count = int(row.get("count") or 0)
    if count < floor:
        return False
    ci_low = row.get("win_rate_ci_low")
    if ci_low is None:
        ci_low = wilson_lower_bound(float(row.get("wins") or 0.0), float(count))
    return float(ci_low) > baseline


def classify_tier(score: float, count: int, *, market: str | None = None) -> str:
    cfg = market_calibration(market)
    if count < int(cfg["min_bucket_samples"]):
        return "INSUFFICIENT_DATA"
    if score >= float(cfg["tier_strong"]):
        return "STRONG"
    if score >= float(cfg["tier_medium"]):
        return "MEDIUM"
    return "WEAK"
