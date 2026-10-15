"""实时操作统计（旁路、可观测）：按 strategy × market × bucket_key 增量聚合。

解决的问题：两端监控每次挂单/成交/平仓/跳过/撤单都写了 ``events.jsonl`` 流水，但
运行中只有计数打印，**没有胜率、R 倍数、滑点、成交率、止损命中率的聚合**；而
``context_stats`` 的分桶胜率与信号评分只在离线批处理里算，实时链路拿不到。

本模块在每轮监控结束时批量增量更新一份 JSON 统计，口径与离线完全一致：
- 分桶键：``context_score.build_bucket_key``（上下文缺失时落 UNKNOWN，退化为
  strategy × market 粒度，未来接入上下文即可自动细化）。
- 胜负与 count 以**平仓**为准（同离线 accepted_trades），win/avg_r 直接可比。
- 评分：``context_score.score_bucket_row``（贝叶斯平滑 + 置信度 + 分级），与离线
  ``aggregate_bucket_stats`` 共用同一实现，不产生口径漂移。

设计约束（**零交易风险**）：
- 纯旁路：所有统计写入失败只告警、不抛异常，绝不改变下单/仓位/跳过逻辑。
- 每轮只做一次「读-改-写」，文件锁 + 原子替换，崩溃不会写坏统计文件。
- 应急开关：``FENGJI_LIVE_OPS_STATS=0`` 直接关闭。
"""
from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Mapping

from fengji_core.context_score import build_bucket_key, score_bucket_row

KILL_SWITCH_ENV = "FENGJI_LIVE_OPS_STATS"
STATS_DIR_NAME = "fengji_ops_stats"

# 统计口径版本：结构变更时递增，便于消费方识别
SCHEMA_VERSION = 1

# 保留最近多少笔平仓明细：用于「近期 vs 历史基线」的策略衰退检测（见 strategy_decay）
RECENT_LIMIT = 200


def _now_text() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def enabled(default: bool = True) -> bool:
    raw = os.getenv(KILL_SWITCH_ENV)
    if raw is None:
        return default
    return raw.strip().lower() not in {"0", "false", "off", "no", "disabled"}


def stats_path_for(market: str, runtime_dir: str | Path) -> Path:
    key = str(market or "UNKNOWN").strip().upper()
    return Path(runtime_dir) / STATS_DIR_NAME / f"{key}_ops_stats.json"


def _safe_float(value: Any) -> float | None:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    if out != out:  # NaN
        return None
    return out


def _side_sign(value: Any) -> int:
    """把 side 归一化成 +1(多)/-1(空)/0(未知)。"""
    num = _safe_float(value)
    if num is not None:
        if num > 0:
            return 1
        if num < 0:
            return -1
        return 0
    text = str(value or "").strip().lower()
    if text in {"long", "buy", "多", "多头", "1"}:
        return 1
    if text in {"short", "sell", "空", "空头", "-1"}:
        return -1
    return 0


def _is_stop_exit(record: Mapping[str, Any]) -> bool:
    for key in ("exit_reason", "reason", "close_reason"):
        text = str(record.get(key) or "").strip().lower()
        if "stop" in text:
            return True
    return False


def _r_multiple(record: Mapping[str, Any]) -> float | None:
    """R = 方向 * (出场 - 入场) / |入场 - 初始止损|；缺字段返回 None。"""
    entry = _safe_float(record.get("entry_price"))
    exit_price = _safe_float(record.get("exit_price"))
    stop = _safe_float(record.get("initial_stop"))
    if stop is None:
        stop = _safe_float(record.get("current_stop"))
    if stop is None:
        stop = _safe_float(record.get("stop_price"))
    if entry is None or exit_price is None or stop is None:
        return None
    denom = abs(entry - stop)
    if denom <= 0:
        return None
    side = _side_sign(record.get("side"))
    if side == 0:
        side = 1 if exit_price >= entry else -1
    return side * (exit_price - entry) / denom


def _slippage(record: Mapping[str, Any]) -> float | None:
    """不利滑点（正=不利）：方向 * (成交价 - 挂单触发价) / 挂单触发价。"""
    fill = _safe_float(record.get("fill_price"))
    trigger = _safe_float(record.get("trigger_price"))
    if trigger is None:
        trigger = _safe_float(record.get("entry_price"))
    if fill is None or trigger is None or trigger <= 0:
        return None
    side = _side_sign(record.get("side"))
    if side == 0:
        return abs(fill - trigger) / trigger
    return side * (fill - trigger) / trigger


def build_fill_event(record: Mapping[str, Any], *, context: Mapping[str, Any] | None = None) -> dict[str, Any]:
    return {"event_type": "fill", **dict(record), "context": dict(context or {})}


def build_close_event(
    record: Mapping[str, Any],
    *,
    position: Mapping[str, Any] | None = None,
    context: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    merged = dict(record)
    if position:
        # 平仓记录里常缺止损/方向，从持仓补齐以便算 R 与止损命中
        for key in ("initial_stop", "current_stop", "stop_price", "side", "entry_price"):
            if merged.get(key) in (None, "") and position.get(key) not in (None, ""):
                merged[key] = position[key]
    return {"event_type": "close", **merged, "context": dict(context or {})}


def build_blocked_event(record: Mapping[str, Any], *, context: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """跳过/撤单：作为成交率的分母，不计入胜负。"""
    event_type = str(record.get("event_type") or "").strip().lower()
    if event_type not in {"skip", "cancel", "cancelled"}:
        event_type = "skip"
    return {"event_type": event_type, **dict(record), "context": dict(context or {})}


def _empty_bucket() -> dict[str, Any]:
    return {
        "fills": 0,
        "closes": 0,
        "wins": 0,
        "stops": 0,
        "skips": 0,
        "cancels": 0,
        "r_sum": 0.0,
        "r_n": 0,
        "net_sum": 0.0,
        "slip_sum": 0.0,
        "slip_n": 0,
    }


def _derive(bucket: dict[str, Any], market: str) -> dict[str, Any]:
    """由累加量派生可消费指标；count/wins/avg_r 与离线 accepted_trades 同口径。"""
    closes = int(bucket["closes"])
    fills = int(bucket["fills"])
    blocked = int(bucket["skips"]) + int(bucket["cancels"])
    r_n = int(bucket["r_n"])
    slip_n = int(bucket["slip_n"])
    scored = score_bucket_row(count=closes, wins=float(bucket["wins"]), avg_r=(bucket["r_sum"] / r_n if r_n else 0.0), market=market)
    out = dict(bucket)
    out.update(
        {
            "count": closes,
            "win_rate": scored["win_rate"],
            "win_rate_smoothed": scored["win_rate_smoothed"],
            "avg_r": (bucket["r_sum"] / r_n) if r_n else None,
            "avg_net": (bucket["net_sum"] / closes) if closes else None,
            "fill_rate": (fills / (fills + blocked)) if (fills + blocked) else None,
            "stop_rate": (bucket["stops"] / closes) if closes else None,
            "avg_slippage": (bucket["slip_sum"] / slip_n) if slip_n else None,
            "sample_confidence": scored["sample_confidence"],
            "signal_score": scored["signal_score"],
            "signal_tier": scored["signal_tier"],
        }
    )
    return out


try:  # 跨平台文件锁
    import fcntl

    def _lock(handle) -> None:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)

    def _unlock(handle) -> None:
        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)

except ImportError:  # pragma: no cover - Windows 分支
    import msvcrt

    def _lock(handle) -> None:
        handle.seek(0)
        msvcrt.locking(handle.fileno(), msvcrt.LK_LOCK, 1)

    def _unlock(handle) -> None:
        handle.seek(0)
        msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)


class LiveOpsStats:
    """增量聚合器：读-改-写一份 JSON 统计（文件锁 + 原子替换）。"""

    def __init__(self, path: str | Path, market: str, *, active: bool | None = None) -> None:
        self.path = Path(path)
        self.market = str(market or "UNKNOWN").strip().upper()
        self.active = enabled() if active is None else active

    def _load(self) -> dict[str, Any]:
        if not self.path.exists():
            return {"market": self.market, "schema_version": SCHEMA_VERSION, "events_total": 0, "buckets": {}, "recent": []}
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {"market": self.market, "schema_version": SCHEMA_VERSION, "events_total": 0, "buckets": {}, "recent": []}
        if not isinstance(data, dict) or not isinstance(data.get("buckets"), dict):
            return {"market": self.market, "schema_version": SCHEMA_VERSION, "events_total": 0, "buckets": {}, "recent": []}
        data.setdefault("market", self.market)
        data.setdefault("events_total", 0)
        return data

    @staticmethod
    def _bucket_key(event: Mapping[str, Any], market: str) -> str:
        strategy = str(event.get("strategy_id") or event.get("strategy") or "UNKNOWN").strip().upper()
        context = event.get("context") or {}
        try:
            return build_bucket_key(dict(context), strategy, market)
        except Exception:  # 分桶失败不应影响统计可用性
            return f"{strategy}|bucket=UNKNOWN"

    def _apply(self, data: dict[str, Any], event: Mapping[str, Any]) -> bool:
        event_type = str(event.get("event_type") or "").strip().lower()
        if event_type not in {"fill", "close", "skip", "cancel", "cancelled"}:
            return False
        key = self._bucket_key(event, self.market)
        bucket = data["buckets"].setdefault(key, _empty_bucket())
        for field in _empty_bucket():
            bucket.setdefault(field, bucket.get(field, _empty_bucket()[field]))

        if event_type == "fill":
            bucket["fills"] += 1
            slip = _slippage(event)
            if slip is not None:
                bucket["slip_sum"] += slip
                bucket["slip_n"] += 1
        elif event_type == "close":
            bucket["closes"] += 1
            net = _safe_float(event.get("net_pnl"))
            if net is not None:
                bucket["net_sum"] += net
                if net > 0:
                    bucket["wins"] += 1
            if _is_stop_exit(event):
                bucket["stops"] += 1
            r_val = _r_multiple(event)
            if r_val is not None:
                bucket["r_sum"] += r_val
                bucket["r_n"] += 1
            # 平仓明细（滚动窗口）：供 strategy_decay 做「近期 vs 基线」衰退检测
            data.setdefault("recent", []).append(
                {
                    "time": _now_text(),
                    "strategy_id": str(event.get("strategy_id") or "UNKNOWN").strip().upper(),
                    "bucket": key,
                    "symbol": str(event.get("symbol") or ""),
                    "net_pnl": net if net is not None else 0.0,
                    "r": r_val,
                    "win": int(bool(net is not None and net > 0)),
                    "stop": int(_is_stop_exit(event)),
                }
            )
        elif event_type == "skip":
            bucket["skips"] += 1
        else:
            bucket["cancels"] += 1
        return True

    def record(self, events: Iterable[Mapping[str, Any]]) -> int:
        """批量记录一轮事件；返回计入统计的事件数。任何失败都只告警不抛出。"""
        if not self.active:
            return 0
        items = list(events or [])
        if not items:
            return 0
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            lock_path = self.path.with_suffix(self.path.suffix + ".lock")
            with lock_path.open("a+") as lock_handle:
                _lock(lock_handle)
                try:
                    data = self._load()
                    counted = 0
                    for event in items:
                        counted += int(self._apply(data, event))
                    data["events_total"] = int(data.get("events_total", 0)) + counted
                    data["market"] = self.market
                    data["schema_version"] = SCHEMA_VERSION
                    data["updated_at"] = _now_text()
                    data["buckets"] = {key: _derive(bucket, self.market) for key, bucket in data["buckets"].items()}
                    data["totals"] = self._totals(data["buckets"])
                    data["recent"] = list(data.get("recent") or [])[-RECENT_LIMIT:]
                    self._atomic_write(data)
                    return counted
                finally:
                    _unlock(lock_handle)
        except Exception as exc:  # 旁路：统计绝不影响交易主流程
            print(f"[live_ops_stats] skipped stats update: {exc}", flush=True)
            return 0

    def _totals(self, buckets: dict[str, dict[str, Any]]) -> dict[str, Any]:
        total = _empty_bucket()
        for bucket in buckets.values():
            for field in total:
                total[field] = total[field] + bucket.get(field, _empty_bucket()[field])
        return _derive(total, self.market)

    def _atomic_write(self, data: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_name = tempfile.mkstemp(prefix=self.path.name + ".", suffix=".tmp", dir=str(self.path.parent))
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(data, handle, ensure_ascii=False, indent=2, default=str)
            os.replace(tmp_name, self.path)
        except Exception:
            try:
                os.unlink(tmp_name)
            except OSError:
                pass
            raise

    def snapshot(self) -> dict[str, Any]:
        return self._load()


def record_round(
    runtime_dir: str | Path,
    market: str,
    *,
    fills: Iterable[Mapping[str, Any]] = (),
    closes: Iterable[tuple[Mapping[str, Any], Mapping[str, Any] | None]] = (),
    blocked: Iterable[Mapping[str, Any]] = (),
    path: str | Path | None = None,
) -> int:
    """便捷入口：一轮监控结束后统计本轮全部事件（旁路，失败只告警）。"""
    if not enabled():
        return 0
    stats = LiveOpsStats(path or stats_path_for(market, runtime_dir), market)
    events: list[dict[str, Any]] = [build_fill_event(item) for item in fills or []]
    events += [build_close_event(record, position=position) for record, position in closes or []]
    events += [build_blocked_event(item) for item in blocked or []]
    return stats.record(events)
