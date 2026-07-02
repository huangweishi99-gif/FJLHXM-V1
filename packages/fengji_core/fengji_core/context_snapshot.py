"""定式开仓上下文快照：从 accepted trade + OS frame 提取 L0–L4 特征向量。

只读峰极 OS 输出与 OHLCV，禁止用 raw high/low 冒充峰/极。
"""
from __future__ import annotations

import os
from typing import Any

import numpy as np
import pandas as pd

ENGINE_VERSION = os.getenv("FENGJI_ENGINE_VERSION", "fengji_core")

L3_COLUMNS_BY_STRATEGY: dict[str, list[str]] = {
    "DS01": ["pattern", "trigger_bar_role", "left30_segment_count", "stick_break_type"],
    "DS02": ["pattern"],
    "DS03": ["pattern", "peak_key", "trigger_source", "ref_idx", "signal_camp"],
    "DS04": ["pattern", "k1_k2_k3_role", "sandwich_width_atr"],
    "DS05": ["pattern", "k2_extreme_candidate", "finger_distance_atr"],
    "DS06": ["pattern", "def_state", "expansion_peak_idx", "stop_rule"],
    "DS07": ["pattern", "d1_camp_auth", "h1_merge_type", "attack_idx", "defense_idx"],
    "DS08": ["pattern", "power_seizure_stage", "denial_confirmed", "attack_idx", "defense_idx"],
    "DS09": ["pattern", "boundary_side", "first_attack_done", "second_attack_ready"],
    "TOTAL": ["pattern", "conflict_strategies", "strategy_priority"],
}


def _safe_float(value: Any, default: float = float("nan")) -> float:
    try:
        if value is None or (isinstance(value, float) and np.isnan(value)):
            return default
        if isinstance(value, str) and not value.strip():
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_int(value: Any, default: int = -1) -> int:
    try:
        if value is None or (isinstance(value, float) and np.isnan(value)):
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def _first_existing(row: dict[str, Any] | pd.Series, keys: list[str], default: Any = None) -> Any:
    for key in keys:
        if key in row and row[key] is not None and not (isinstance(row[key], float) and np.isnan(row[key])):
            if isinstance(row[key], str) and not str(row[key]).strip():
                continue
            return row[key]
    return default


def _camp_age_bars(df: pd.DataFrame, idx: int) -> int | None:
    if idx < 0 or idx >= len(df) or "camp" not in df.columns:
        return None
    camp = df.iloc[idx]["camp"]
    age = 1
    for j in range(idx - 1, -1, -1):
        if df.iloc[j]["camp"] != camp:
            break
        age += 1
    return age


def _turn_phase(row: pd.Series) -> str:
    pending = row.get("pending_turn")
    if pending is None or (isinstance(pending, float) and np.isnan(pending)):
        return "NONE"
    text = str(pending).strip().upper()
    if not text or text in {"0", "FALSE", "NONE", "NAN"}:
        return "NONE"
    if "CONFIRM" in text:
        return "CONFIRMED"
    return "CONFIRMING"


def _gap_type(df: pd.DataFrame, idx: int) -> str:
    if idx <= 0:
        return "NONE"
    prev_close = _safe_float(df.iloc[idx - 1]["close"])
    open_price = _safe_float(df.iloc[idx]["open"])
    if np.isnan(prev_close) or np.isnan(open_price):
        return "NONE"
    if open_price > prev_close:
        return "UP"
    if open_price < prev_close:
        return "DOWN"
    return "NONE"


def _ensure_atr(df: pd.DataFrame, window: int = 14) -> pd.DataFrame:
    out = df.copy()
    if "atr" in out.columns and out["atr"].notna().any():
        return out
    prev_close = out["close"].shift(1)
    tr = pd.concat(
        [
            out["high"] - out["low"],
            (out["high"] - prev_close).abs(),
            (out["low"] - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    out["atr"] = tr.rolling(window, min_periods=1).mean()
    return out


def compute_l2_features(df: pd.DataFrame, idx: int) -> dict[str, Any]:
    """L2 K 线形态特征（单根 + 序列 + 波动）。"""
    row = df.iloc[idx]
    o = _safe_float(row["open"])
    h = _safe_float(row["high"])
    l = _safe_float(row["low"])
    c = _safe_float(row["close"])
    rng = max(h - l, 1e-12)
    body = abs(c - o)
    upper = h - max(o, c)
    lower = min(o, c) - l

    atr = _safe_float(row.get("atr"))
    range_atr = rng / atr if atr and not np.isnan(atr) and atr > 0 else float("nan")

    left = max(0, idx - 19)
    window = df.iloc[left : idx + 1]
    atr_window = window["atr"].dropna() if "atr" in window.columns else pd.Series(dtype=float)
    atr_percentile_20 = float("nan")
    if not atr_window.empty and not np.isnan(atr):
        atr_percentile_20 = float((atr_window <= atr).mean())

    range_low = _safe_float(window["low"].min())
    range_high = _safe_float(window["high"].max())
    position_in_range_20 = float("nan")
    if range_high > range_low:
        position_in_range_20 = (c - range_low) / (range_high - range_low)

    bull = 0
    bear = 0
    for j in range(idx, -1, -1):
        bar = df.iloc[j]
        if _safe_float(bar["close"]) >= _safe_float(bar["open"]):
            if bear:
                break
            bull += 1
        else:
            if bull:
                break
            bear += 1

    vol_ratio_20 = float("nan")
    if "volume" in df.columns:
        vol = _safe_float(row.get("volume"), 0.0)
        vol_mean = window["volume"].astype(float).replace(0, np.nan).mean()
        if vol_mean and not np.isnan(vol_mean):
            vol_ratio_20 = vol / vol_mean

    return {
        "body_ratio": body / rng,
        "upper_shadow_ratio": upper / rng,
        "lower_shadow_ratio": lower / rng,
        "bar_direction": "BULL" if c >= o else "BEAR",
        "range_atr": range_atr,
        "atr_percentile_20": atr_percentile_20,
        "gap_type": _gap_type(df, idx),
        "consecutive_bull": bull,
        "consecutive_bear": bear,
        "position_in_range_20": position_in_range_20,
        "vol_ratio_20": vol_ratio_20,
    }


def compute_l1_os_features(df: pd.DataFrame, idx: int) -> dict[str, Any]:
    """L1 峰极 OS 结构特征（来自 os_engine 输出列）。"""
    row = df.iloc[idx]
    atr = _safe_float(row.get("atr"))
    active_high = _safe_float(row.get("active_high"))
    active_low = _safe_float(row.get("active_low"))
    close = _safe_float(row.get("close"))

    dist_high = float("nan")
    dist_low = float("nan")
    if atr and not np.isnan(atr) and atr > 0:
        if not np.isnan(active_high):
            dist_high = (active_high - close) / atr
        if not np.isnan(active_low):
            dist_low = (close - active_low) / atr

    hardened_count = _safe_int(row.get("hardened_count"), 0)
    left = max(0, idx - 29)
    segment_count_left_30 = hardened_count  # 近似：当前硬化节点数

    last_peak_kind = "NONE"
    red_peak_idx = _safe_int(row.get("red_peak_idx"), -1)
    blue_peak_idx = _safe_int(row.get("blue_peak_idx"), -1)
    if red_peak_idx == idx:
        last_peak_kind = "RED_PEAK"
    elif blue_peak_idx == idx:
        last_peak_kind = "BLUE_PEAK"

    last_extreme_kind = "NONE"
    red_ext_idx = _safe_int(row.get("red_ext_idx"), -1)
    blue_ext_idx = _safe_int(row.get("blue_ext_idx"), -1)
    if red_ext_idx == idx:
        last_extreme_kind = "RED_EXT"
    elif blue_ext_idx == idx:
        last_extreme_kind = "BLUE_EXT"

    failed_high_idx = _safe_int(row.get("last_failed_high_idx"), -1)
    failed_low_idx = _safe_int(row.get("last_failed_low_idx"), -1)

    return {
        "camp": row.get("camp"),
        "camp_confirmed": row.get("camp_confirmed"),
        "camp_age_bars": _camp_age_bars(df, idx),
        "turn_phase": _turn_phase(row),
        "active_high": active_high,
        "active_low": active_low,
        "dist_active_high_atr": dist_high,
        "dist_active_low_atr": dist_low,
        "red_ext_price": _safe_float(row.get("red_ext_price")),
        "blue_ext_price": _safe_float(row.get("blue_ext_price")),
        "red_ext_idx": red_ext_idx if red_ext_idx >= 0 else None,
        "blue_ext_idx": blue_ext_idx if blue_ext_idx >= 0 else None,
        "segment_count_left_30": segment_count_left_30,
        "last_peak_kind": last_peak_kind,
        "last_extreme_kind": last_extreme_kind,
        "is_fake_peak": failed_high_idx == idx,
        "is_fake_extreme": failed_high_idx == idx or failed_low_idx == idx,
    }


def extract_l3_fields(trade: dict[str, Any] | pd.Series, strategy_id: str) -> dict[str, Any]:
    """L3 定式专属字段：优先 trade 列，其次 setup_key 解析。"""
    out: dict[str, Any] = {}
    for column in L3_COLUMNS_BY_STRATEGY.get(strategy_id, ["pattern"]):
        value = _first_existing(trade, [column])
        if value is not None:
            out[column] = value
    setup_key = str(_first_existing(trade, ["setup_key"], "") or "")
    if strategy_id == "DS03" and setup_key and "peak_key" not in out:
        # 常见格式：SYMBOL|DS03|peak_key|side
        parts = setup_key.split("|")
        if len(parts) >= 3:
            out.setdefault("peak_key", parts[2])
    return out


def compute_l4_execution(trade: dict[str, Any] | pd.Series, df: pd.DataFrame, idx: int) -> dict[str, Any]:
    """L4 执行上下文：止损距离、RR、会话桶。"""
    entry_price = _safe_float(_first_existing(trade, ["entry_price"]))
    initial_stop = _safe_float(_first_existing(trade, ["initial_stop", "stop", "defense_price"]))
    side = _safe_int(_first_existing(trade, ["side"], 1), 1)
    atr = _safe_float(df.iloc[idx].get("atr"))

    stop_distance_atr = float("nan")
    if atr and not np.isnan(atr) and atr > 0 and not np.isnan(initial_stop):
        stop_distance_atr = abs(entry_price - initial_stop) / atr

    rr_at_entry = float("nan")
    risk = abs(entry_price - initial_stop)
    if risk > 0:
        reward = risk * 2.0  # V1 占位：2R 目标，待各定式 exit 规则细化
        rr_at_entry = reward / risk

    trigger_ref = _safe_float(_first_existing(trade, ["entry_ref", "trigger_price"], entry_price))
    trigger_distance_pct = float("nan")
    if trigger_ref and not np.isnan(trigger_ref) and trigger_ref != 0:
        trigger_distance_pct = abs(entry_price - trigger_ref) / abs(trigger_ref)

    session_bucket = "UNKNOWN"
    if "date" in df.columns:
        ts = pd.to_datetime(df.iloc[idx]["date"], errors="coerce")
        if not pd.isna(ts):
            hour = ts.hour
            if 9 <= hour < 15:
                session_bucket = "DAY"
            elif hour >= 21 or hour < 3:
                session_bucket = "NIGHT"
            else:
                session_bucket = "OTHER"

    market_regime_vol = "NORM"
    atr_pct = compute_l2_features(df, idx).get("atr_percentile_20")
    if isinstance(atr_pct, float):
        if atr_pct >= 0.75:
            market_regime_vol = "HIGH"
        elif atr_pct <= 0.25:
            market_regime_vol = "LOW"

    return {
        "trigger_distance_pct": trigger_distance_pct,
        "stop_distance_atr": stop_distance_atr,
        "rr_at_entry": rr_at_entry,
        "session_bucket": session_bucket,
        "market_regime_vol": market_regime_vol,
        "side": side,
    }


def compute_r_multiple(trade: dict[str, Any] | pd.Series) -> float:
    entry = _safe_float(_first_existing(trade, ["entry_price"]))
    stop = _safe_float(_first_existing(trade, ["initial_stop", "stop"]))
    net = _safe_float(_first_existing(trade, ["net", "net_pnl", "crypto_net_pnl"], 0.0), 0.0)
    side = _safe_int(_first_existing(trade, ["side"], 1), 1)
    risk = abs(entry - stop)
    if risk <= 0 or np.isnan(risk):
        return float("nan")
    directional = net if side >= 0 else -net
    return directional / risk


def trade_id_for(trade: dict[str, Any] | pd.Series, symbol: str, strategy_id: str) -> str:
    setup_key = str(_first_existing(trade, ["setup_key", "candidate_id"], "") or "")
    entry_time = _first_existing(trade, ["entry_time", "entry_date"], "")
    trade_no = _first_existing(trade, ["portfolio_trade_no", "trade_no", "source_trade_no"], "")
    return f"{symbol}|{strategy_id}|{entry_time}|{trade_no}|{setup_key}"


def snapshot_from_trade(
    trade: dict[str, Any] | pd.Series,
    os_df: pd.DataFrame,
    *,
    market: str,
    symbol: str,
    timeframe: str,
    engine_version: str = ENGINE_VERSION,
) -> dict[str, Any] | None:
    """为单笔 accepted trade 生成上下文快照。"""
    idx = _safe_int(_first_existing(trade, ["entry_idx"]), -1)
    if idx < 0 or idx >= len(os_df):
        return None

    strategy_id = str(_first_existing(trade, ["strategy_id"], "UNKNOWN")).upper()
    os_df = _ensure_atr(os_df)

    entry_time = _first_existing(trade, ["entry_time", "entry_date"])
    exit_time = _first_existing(trade, ["exit_time", "exit_date"])
    entry_idx = idx
    exit_idx = _safe_int(_first_existing(trade, ["exit_idx"]), -1)
    holding_bars = (exit_idx - entry_idx) if exit_idx >= entry_idx >= 0 else None

    l0 = {
        "trade_id": trade_id_for(trade, symbol, strategy_id),
        "setup_key": _first_existing(trade, ["setup_key"], ""),
        "strategy_id": strategy_id,
        "market": market,
        "symbol": symbol,
        "timeframe": timeframe,
        "entry_time": entry_time,
        "exit_time": exit_time,
        "entry_idx": entry_idx,
        "exit_idx": exit_idx if exit_idx >= 0 else None,
        "entry_price": _safe_float(_first_existing(trade, ["entry_price", "avg_entry_price"])),
        "exit_price": _safe_float(_first_existing(trade, ["exit_price"])),
        "initial_stop": _safe_float(_first_existing(trade, ["initial_stop", "stop"])),
        "exit_reason": _first_existing(trade, ["exit_reason", "reason"], ""),
        "net_pnl": _safe_float(_first_existing(trade, ["net", "net_pnl", "crypto_net_pnl"], 0.0), 0.0),
        "r_multiple": compute_r_multiple(trade),
        "holding_bars": holding_bars,
        "engine_version": engine_version,
    }

    snapshot = {}
    snapshot.update(l0)
    snapshot.update(compute_l1_os_features(os_df, idx))
    snapshot.update(compute_l2_features(os_df, idx))
    snapshot.update(extract_l3_fields(trade, strategy_id))
    snapshot.update(compute_l4_execution(trade, os_df, idx))
    return snapshot


def build_snapshots(
    trades_df: pd.DataFrame,
    os_df: pd.DataFrame,
    *,
    market: str,
    symbol: str,
    timeframe: str,
    engine_version: str = ENGINE_VERSION,
) -> pd.DataFrame:
    """批量生成上下文快照。"""
    if trades_df.empty:
        return pd.DataFrame()
    rows: list[dict[str, Any]] = []
    for _, trade in trades_df.iterrows():
        snap = snapshot_from_trade(
            trade,
            os_df,
            market=market,
            symbol=symbol,
            timeframe=timeframe,
            engine_version=engine_version,
        )
        if snap:
            rows.append(snap)
    return pd.DataFrame(rows)
