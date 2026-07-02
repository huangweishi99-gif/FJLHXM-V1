"""DS03 挂单成交解析：仅攻击棍突破时刻入场（执行层，不改定式逻辑）。"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from fengji_core.ds03 import entry_fill, make_ds03_signal, resolve_ds03_attack
from fengji_core.ds07 import attach_os_detail
from fengji_core.os_state_store import build_os_detail_frame_stateful, find_data_file, os_state_path
from fengji_core.runtime_stop_updater import TAIL_BY_TIMEFRAME, _normalize_ohlcv


def is_ds03_watch_setup_key(setup_key: str) -> bool:
    return "|watch|" in str(setup_key or "").casefold()


def peak_key_from_setup_key(setup_key: str, symbol: str) -> str | None:
    sk = str(setup_key or "").strip()
    sym = str(symbol or "").strip().upper()
    prefix = f"{sym}|"
    if not sk.startswith(prefix):
        return None
    if is_ds03_watch_setup_key(sk):
        return None
    body = sk[len(prefix) :]
    if body.startswith("DS03|") and ("|true_peak|" in body or "|fake_peak|" in body):
        return body
    return None


def _price_close(a: float, b: float, *, tol_ratio: float = 0.001) -> bool:
    aa = float(a)
    bb = float(b)
    if aa == bb:
        return True
    scale = max(abs(aa), abs(bb), 1e-12)
    return abs(aa - bb) <= scale * tol_ratio


def _side_int(side: Any) -> int:
    return 1 if str(side or "").lower() == "long" else -1


def load_ds03_d1_os_frame(
    symbol: str,
    data_dir: Path,
    os_state_dir: Path | str | None,
    *,
    gap: int = 3,
) -> pd.DataFrame:
    csv_path = find_data_file(Path(data_dir), symbol, "1d")
    if not csv_path.exists():
        return pd.DataFrame()
    try:
        raw = pd.read_csv(csv_path)
    except Exception:
        return pd.DataFrame()
    df = _normalize_ohlcv(raw)
    if df.empty:
        return df
    tail = TAIL_BY_TIMEFRAME.get("1d", 1095)
    if len(df) > tail:
        df = df.tail(tail).reset_index(drop=True)
    state_path = os_state_path(Path(os_state_dir), symbol, "1d") if os_state_dir else None
    try:
        df_os, _ = build_os_detail_frame_stateful(
            df,
            gap,
            state_path,
            attach_os_detail,
            record_hardened_by_bar=True,
        )
    except Exception:
        return pd.DataFrame()
    return df_os


def attack_matches_order(order: dict[str, Any], attack: Any, symbol: str) -> bool:
    if attack is None:
        return False
    if int(attack.side) != _side_int(order.get("side")):
        return False
    trigger = order.get("trigger_price")
    if trigger is None:
        return False
    if not _price_close(float(attack.entry_ref), float(trigger)):
        return False
    expected_peak = peak_key_from_setup_key(str(order.get("setup_key", "")), symbol)
    if expected_peak is not None and str(attack.peak_key) != expected_peak:
        return False
    return True


def find_attack_bar_index(os_df: pd.DataFrame, order: dict[str, Any], symbol: str) -> int | None:
    if os_df.empty:
        return None
    i = len(os_df) - 1
    attack = resolve_ds03_attack(os_df, i)
    if attack is not None and attack_matches_order(order, attack, symbol):
        return i
    return None


def find_missed_attack_bar_index(os_df: pd.DataFrame, order: dict[str, Any], symbol: str) -> int | None:
    """攻击棍已在更早 D1 收盘成立，但未成交 → 不得再用 ticker 补成交。"""
    if len(os_df) < 2:
        return None
    for i in range(len(os_df) - 2, -1, -1):
        attack = resolve_ds03_attack(os_df, i)
        if attack is not None and attack_matches_order(order, attack, symbol):
            return i
    return None


def _attack_fill_payload(
    os_df: pd.DataFrame,
    bar_idx: int,
    order: dict[str, Any],
    symbol: str,
    *,
    price_source: str,
) -> dict[str, Any] | None:
    attack = resolve_ds03_attack(os_df, bar_idx)
    if attack is None or not attack_matches_order(order, attack, symbol):
        return None
    signal = make_ds03_signal(os_df, bar_idx)
    if signal is None:
        return None
    row = os_df.iloc[bar_idx]
    stop = safe_float(order.get("stop_price"))
    initial_stop = float(signal.initial_stop)
    if stop is not None and stop > 0:
        initial_stop = float(stop)
    return {
        "fill_price": float(entry_fill(row, signal)),
        "initial_stop": initial_stop,
        "attack_bar_idx": int(bar_idx),
        "attack_bar_time": str(pd.to_datetime(row["date"])),
        "peak_key": str(signal.peak_key),
        "trigger_source": str(signal.trigger_source),
        "price_source": price_source,
    }


def resolve_intraday_watch_breakout(
    os_df: pd.DataFrame,
    order: dict[str, Any],
    symbol: str,
    live_price: float,
) -> dict[str, Any] | None:
    """攻击棍 D1 尚未写入 CSV 时，在突破一刻用现价落账（仅 watch 预挂单）。"""
    if not is_ds03_watch_setup_key(str(order.get("setup_key", ""))):
        return None
    side = _side_int(order.get("side"))
    trigger = float(order["trigger_price"])
    if side == 1 and live_price < trigger:
        return None
    if side == -1 and live_price > trigger:
        return None

    latest = os_df.iloc[-1]
    if side == 1:
        if int(latest.get("camp", 0) or 0) != 1:
            return None
        active = latest.get("active_high")
        if active is None or pd.isna(active) or not _price_close(float(active), trigger):
            return None
        if float(latest["high"]) > trigger:
            return None
        fill_price = max(float(live_price), trigger)
        initial_stop = min(float(latest["low"]), float(live_price))
    else:
        if int(latest.get("camp", 0) or 0) != -1:
            return None
        active = latest.get("active_low")
        if active is None or pd.isna(active) or not _price_close(float(active), trigger):
            return None
        if float(latest["low"]) < trigger:
            return None
        fill_price = min(float(live_price), trigger)
        initial_stop = max(float(latest["high"]), float(live_price))

    stop = safe_float(order.get("stop_price"))
    if stop is not None and stop > 0:
        initial_stop = float(stop)

    return {
        "fill_price": fill_price,
        "initial_stop": initial_stop,
        "attack_bar_idx": len(os_df) - 1,
        "attack_bar_time": str(pd.to_datetime(latest["date"])),
        "peak_key": "",
        "trigger_source": "watch_intraday_breakout",
        "price_source": "ds03_intraday_breakout",
    }


def safe_float(value: Any) -> float | None:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    if pd.isna(out):
        return None
    return out


def watch_trigger_stale_vs_attack(os_df: pd.DataFrame, order: dict[str, Any]) -> dict[str, Any] | None:
    """watch 预挂 trigger 与当前 D1 攻击棍 entry_ref 不一致时不得 intraday 成交。"""
    if not is_ds03_watch_setup_key(str(order.get("setup_key", ""))):
        return None
    if os_df.empty:
        return None
    i = len(os_df) - 1
    attack = resolve_ds03_attack(os_df, i)
    if attack is None:
        return None
    if int(attack.side) != _side_int(order.get("side")):
        return None
    trigger = order.get("trigger_price")
    if trigger is None:
        row = os_df.iloc[i]
        return {
            "stale": True,
            "missed_attack_bar_idx": int(i),
            "missed_attack_bar_time": str(pd.to_datetime(row["date"])),
            "reason": "ds03_watch_trigger_stale",
        }
    if not _price_close(float(attack.entry_ref), float(trigger)):
        row = os_df.iloc[i]
        return {
            "stale": True,
            "missed_attack_bar_idx": int(i),
            "missed_attack_bar_time": str(pd.to_datetime(row["date"])),
            "reason": "ds03_watch_trigger_stale",
            "expected_trigger": float(attack.entry_ref),
            "watch_trigger": float(trigger),
        }
    return None


def resolve_ds03_pending_fill_from_os_df(
    order: dict[str, Any],
    symbol: str,
    os_df: pd.DataFrame,
    *,
    live_price: float | None = None,
) -> dict[str, Any] | None:
    """解析 DS03 是否可在本轮成交（OS 帧已就绪）。返回 stale 时调用方应撤销挂单。"""
    if os_df.empty:
        return None

    missed = find_missed_attack_bar_index(os_df, order, symbol)
    if missed is not None:
        row = os_df.iloc[missed]
        return {
            "stale": True,
            "missed_attack_bar_idx": int(missed),
            "missed_attack_bar_time": str(pd.to_datetime(row["date"])),
            "reason": "ds03_attack_bar_missed",
        }

    attack_idx = find_attack_bar_index(os_df, order, symbol)
    if attack_idx is not None:
        payload = _attack_fill_payload(
            os_df,
            attack_idx,
            order,
            symbol,
            price_source="ds03_attack_bar",
        )
        if payload is not None:
            return payload

    if live_price is not None:
        stale_watch = watch_trigger_stale_vs_attack(os_df, order)
        if stale_watch is not None:
            return stale_watch
        intraday = resolve_intraday_watch_breakout(os_df, order, symbol, float(live_price))
        if intraday is not None:
            return intraday

    return None


def resolve_ds03_pending_fill(
    order: dict[str, Any],
    symbol: str,
    data_dir: Path,
    os_state_dir: Path | str | None,
    *,
    live_price: float | None = None,
    gap: int = 3,
) -> dict[str, Any] | None:
    os_df = load_ds03_d1_os_frame(symbol, data_dir, os_state_dir, gap=gap)
    return resolve_ds03_pending_fill_from_os_df(order, symbol, os_df, live_price=live_price)
