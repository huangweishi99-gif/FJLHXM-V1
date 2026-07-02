"""挂单监控的动态止损刷新：复用 backtest 里的 update_dsXX_stop 逻辑。

每次挂单监控轮询时调用 ``refresh_position_stop``，按持仓 strategy_id 找到
对应的回测止损追踪规则（DS01-DS09 各异），把 ``position['current_stop']``
向有利方向推进。这样实盘离场策略与回测/宪法保持一致。
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from fengji_core.data import parse_tq_datetime_series, valid_futures_price_mask
from fengji_core.ds07 import attach_os_detail
from fengji_core.os_state_store import (
    build_os_detail_frame_stateful as _build_stateful,
    find_data_file,
    is_futures_market,
    os_state_path,
)


TIMEFRAME_BY_STRATEGY: dict[str, str] = {
    "DS01": "1d",
    "DS02": "1d",
    "DS03": "1d",
    "DS04": "1d",
    "DS05": "1d",
    "DS06": "1d",
    "DS07": "1h",
    "DS08": "1h",
    "DS09": "15m",
}

# D1/H1 定式止损必须等对应周期 K 线收盘确认；15m 仍可用最新 bar。
STOP_REQUIRES_COMPLETED_BAR: frozenset[str] = frozenset({"1d", "1h"})

TAIL_BY_TIMEFRAME: dict[str, int] = {"15m": 960, "1h": 2400, "1d": 1095}


def stop_bar_requires_completed_close(timeframe: str) -> bool:
    return str(timeframe or "").strip().lower() in STOP_REQUIRES_COMPLETED_BAR


def _finite_number(value: Any) -> bool:
    try:
        return pd.notna(value) and float(value) > 0
    except (TypeError, ValueError):
        return False


def futures_session_placeholder_mask(frame: pd.DataFrame) -> pd.Series:
    """Closed-session placeholders are flat zero-volume bars, not all zero-volume bars."""
    zero_volume = frame["volume"].fillna(0) <= 0
    ohlc_range = frame[["open", "high", "low", "close"]].max(axis=1) - frame[
        ["open", "high", "low", "close"]
    ].min(axis=1)
    return zero_volume & (ohlc_range.abs() <= 1e-12)


def _normalize_ohlcv(df: pd.DataFrame, atr_window: int = 14) -> pd.DataFrame:
    df = df.copy()
    df.columns = [str(c).strip().lower() for c in df.columns]
    if "date" not in df.columns:
        for cand in ("timestamp", "datetime", "time"):
            if cand in df.columns:
                df = df.rename(columns={cand: "date"})
                break
    required = ["date", "open", "high", "low", "close", "volume"]
    for col in required:
        if col not in df.columns:
            return pd.DataFrame()
    df = df[required].copy()
    df["date"] = parse_tq_datetime_series(df["date"])
    for col in ["open", "high", "low", "close", "volume"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df = df.dropna(subset=["date", "open", "high", "low", "close"])
    mask = df["date"] >= pd.Timestamp("2020-01-01")
    mask &= df["date"] <= pd.Timestamp.now() + pd.Timedelta(days=1)
    for col in ["open", "high", "low", "close"]:
        mask &= df[col].map(_finite_number)
    mask &= df["high"] >= df[["open", "close", "low"]].max(axis=1)
    mask &= df["low"] <= df[["open", "close", "high"]].min(axis=1)
    if is_futures_market():
        mask &= valid_futures_price_mask(df)
    df = df.loc[mask].copy()
    if is_futures_market() and not df.empty:
        df = df.loc[~futures_session_placeholder_mask(df)].copy()
    df = df.sort_values("date").drop_duplicates("date", keep="last").reset_index(drop=True)
    prev_close = df["close"].shift(1)
    tr = pd.concat(
        [df["high"] - df["low"], (df["high"] - prev_close).abs(), (df["low"] - prev_close).abs()],
        axis=1,
    )
    df["tr"] = tr.max(axis=1)
    df["atr"] = df["tr"].rolling(atr_window).mean()
    return df


def _apply_update(strategy_id: str, work_pos: dict, df_os: pd.DataFrame, engine) -> dict:
    if df_os.empty:
        return work_pos
    last_idx = len(df_os) - 1
    row = df_os.iloc[last_idx]
    side = int(work_pos.get("side", 0) or 0)

    if strategy_id == "DS01":
        work_pos["stop"] = float(row["low"]) if side == 1 else float(row["high"])
        return work_pos
    if strategy_id == "DS02":
        from fengji_core.ds02 import update_ds02_stop
        return update_ds02_stop(work_pos, row)
    if strategy_id == "DS03":
        from fengji_core.ds03 import update_ds03_stop
        return update_ds03_stop(work_pos, df_os, last_idx)
    if strategy_id == "DS04":
        from fengji_core.ds04 import update_ds04_stop
        return update_ds04_stop(work_pos, row)
    if strategy_id == "DS05":
        from fengji_core.ds05 import update_ds05_stop
        return update_ds05_stop(work_pos, row)
    if strategy_id == "DS06":
        from fengji_core.ds06 import update_ds06_stop
        return update_ds06_stop(work_pos, df_os, last_idx)
    if strategy_id == "DS07":
        from fengji_core.ds07 import update_ds07_stop
        return update_ds07_stop(work_pos, row)
    if strategy_id == "DS08":
        from fengji_core.ds08 import update_ds08_stop
        return update_ds08_stop(work_pos, list(engine.hardened_nodes))
    if strategy_id == "DS09":
        from fengji_core.ds09 import update_ds09_stop
        return update_ds09_stop(work_pos, row)
    return work_pos


def _resolve_current_stop(position: dict[str, Any]) -> float | None:
    for key in ("current_stop", "initial_stop", "stop_price", "stop"):
        value = position.get(key)
        if value is None:
            continue
        try:
            out = float(value)
        except (TypeError, ValueError):
            continue
        if out != 0.0:
            return out
    return None


def refresh_position_stop(
    position: dict[str, Any],
    *,
    symbol: str,
    data_dir: Path,
    os_state_dir: Path | str | None,
    gap: int = 3,
) -> dict[str, Any]:
    """根据 position[strategy_id] 调对应 update_dsXX_stop 推进 current_stop。

    只允许向有利方向（多头上抬、空头下压）更新；失败时静默保留原 stop。
    """
    sid = str(position.get("strategy_id", "")).strip().upper()
    if sid not in TIMEFRAME_BY_STRATEGY:
        return position
    side = int(position.get("side", 0) or 0)
    if side not in (1, -1):
        return position

    tf = TIMEFRAME_BY_STRATEGY[sid]
    csv_path = find_data_file(Path(data_dir), symbol, tf)
    if not csv_path.exists():
        return position
    try:
        raw = pd.read_csv(csv_path)
    except Exception:
        return position
    df = _normalize_ohlcv(raw)
    if df.empty:
        return position
    tail = TAIL_BY_TIMEFRAME.get(tf, 1095)
    if len(df) > tail:
        df = df.tail(tail).reset_index(drop=True)

    state_path = None
    if os_state_dir:
        state_path = os_state_path(Path(os_state_dir), symbol, tf)
    record_hb = tf == "1d"
    try:
        df_os, engine = _build_stateful(df, gap, state_path, attach_os_detail, record_hardened_by_bar=record_hb)
    except Exception:
        return position

    cur = _resolve_current_stop(position)
    if cur is None:
        return position

    work = {"side": side, "stop": cur, "strategy_id": sid}
    work = _apply_update(sid, work, df_os, engine)
    try:
        new_stop = float(work.get("stop", cur))
    except (TypeError, ValueError):
        return position

    advanced = (side == 1 and new_stop > cur) or (side == -1 and new_stop < cur)
    if not advanced:
        return position
    position["current_stop"] = new_stop
    position["stop_source"] = str(work.get("stop_source", f"trail_{sid}"))
    position["stop_updated_at"] = pd.Timestamp.now(tz="Asia/Shanghai").strftime("%Y-%m-%d %H:%M:%S")
    return position
