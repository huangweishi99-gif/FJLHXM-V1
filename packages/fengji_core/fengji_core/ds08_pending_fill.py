"""DS08 挂单：setup_key 滞后检测 + entry_fill 成交（执行层，不改定式逻辑）。"""
from __future__ import annotations

import time
from pathlib import Path
from typing import Any

import pandas as pd

from fengji_core.ds08 import DS08Signal, entry_fill, make_ds08_signal
from fengji_core.ds07 import attach_os_detail
from fengji_core.fill_supervision import (
    parse_ds08_setup_key,
    pending_price_fill_ok,
    resolve_setup_bar_index,
    validate_ds08_setup_from_key,
)
from fengji_core.os_state_store import build_os_detail_frame_stateful, find_data_file, os_state_path
from fengji_core.runtime_stop_updater import TAIL_BY_TIMEFRAME, _normalize_ohlcv

_OS_FRAME_CACHE: dict[tuple[str, str, str, int], tuple[float, pd.DataFrame, Any]] = {}
_OS_FRAME_CACHE_TTL_SEC = 45.0
DEFAULT_DS08_MAX_LAG_BARS = 1


def _side_int(side: Any) -> int:
    return 1 if str(side or "").lower() == "long" else -1


def load_ds08_h1_os_frame(
    symbol: str,
    data_dir: Path,
    os_state_dir: Path | str | None,
    *,
    gap: int = 3,
) -> tuple[pd.DataFrame, Any]:
    cache_key = (
        str(symbol).upper(),
        str(Path(data_dir).resolve()),
        str(os_state_dir or ""),
        int(gap),
    )
    now = time.monotonic()
    cached = _OS_FRAME_CACHE.get(cache_key)
    if cached is not None and now - cached[0] < _OS_FRAME_CACHE_TTL_SEC:
        return cached[1], cached[2]

    csv_path = find_data_file(Path(data_dir), symbol, "1h")
    if not csv_path.exists():
        return pd.DataFrame(), None
    try:
        raw = pd.read_csv(csv_path)
    except Exception:
        return pd.DataFrame(), None
    df = _normalize_ohlcv(raw)
    if df.empty:
        return df, None
    tail = TAIL_BY_TIMEFRAME.get("1h", 2400)
    if len(df) > tail:
        df = df.tail(tail).reset_index(drop=True)
    state_path = os_state_path(Path(os_state_dir), symbol, "1h") if os_state_dir else None
    try:
        result = build_os_detail_frame_stateful(
            df,
            gap,
            state_path,
            attach_os_detail,
            record_hardened_by_bar=True,
        )
    except Exception:
        return pd.DataFrame(), None
    _OS_FRAME_CACHE[cache_key] = (now, result[0], result[1])
    return result


def _ds08_setup_keys_match(order_key: str, expected_key: str) -> bool:
    left = parse_ds08_setup_key(order_key)
    right = parse_ds08_setup_key(expected_key)
    if left is None or right is None:
        return str(order_key).strip() == str(expected_key).strip()
    if left["side"] != right["side"]:
        return False
    if int(left["defense_idx"]) != int(right["defense_idx"]):
        return False
    if int(left["attack_idx"]) != int(right["attack_idx"]):
        return False
    lt = float(left["trigger_price"])
    rt = float(right["trigger_price"])
    scale = max(abs(lt), abs(rt), 1e-12)
    return abs(lt - rt) <= scale * 0.001


def check_ds08_setup_key_stale_from_os(
    order: dict[str, Any],
    symbol: str,
    os_df: pd.DataFrame,
    engine: Any,
) -> dict[str, Any] | None:
    """挂单仍 ACTIVE 时复核 setup_key；滞后或结构失效则撤销，避免 ATH 类 stale fill。"""
    setup_key = str(order.get("setup_key") or "").strip()
    parsed = parse_ds08_setup_key(setup_key)
    if parsed is None or os_df.empty or engine is None:
        return None

    side = _side_int(order.get("side"))
    if parsed["side"] != side:
        return {
            "stale": True,
            "reason": "ds08_setup_side_mismatch",
            "setup_key": setup_key,
        }

    i = resolve_setup_bar_index(order, os_df, "")
    if i is None:
        return None

    hardened = getattr(engine, "hardened_by_bar", None) or []
    skeleton = hardened[i] if i < len(hardened) else []
    sym_clean = str(symbol).upper().replace("USDT", "")
    static_issues, checks = validate_ds08_setup_from_key(
        os_df,
        skeleton,
        i,
        parsed,
        side,
        symbol=sym_clean,
    )

    hard = [x for x in static_issues if "roles" in x or "skeleton" in x]
    if hard:
        return {
            "stale": True,
            "reason": "ds08_structure_invalidated",
            "setup_bar_idx": i,
            "issues": hard[:3],
            "setup_key": setup_key,
        }

    expected = str(checks.get("expected_setup_key") or "")
    if expected and not _ds08_setup_keys_match(setup_key, expected):
        stale = checks.get("setup_key_idx_stale") or {}
        return {
            "stale": True,
            "reason": "ds08_setup_key_stale",
            "setup_bar_idx": i,
            "setup_key": setup_key,
            "expected_setup_key": expected,
            "key_idx": stale.get("key"),
            "setup_bar_idx_pair": stale.get("setup_bar"),
        }

    if checks.get("setup_key_idx_stale"):
        stale = checks["setup_key_idx_stale"]
        return {
            "stale": True,
            "reason": "ds08_setup_key_idx_stale",
            "setup_bar_idx": i,
            "setup_key": setup_key,
            "expected_setup_key": expected,
            "key_idx": stale.get("key"),
            "setup_bar_idx_pair": stale.get("setup_bar"),
        }

    return None


def check_ds08_setup_key_stale(
    order: dict[str, Any],
    symbol: str,
    data_dir: Path,
    os_state_dir: Path | str | None,
    *,
    gap: int = 3,
) -> dict[str, Any] | None:
    os_df, engine = load_ds08_h1_os_frame(symbol, data_dir, os_state_dir, gap=gap)
    return check_ds08_setup_key_stale_from_os(order, symbol, os_df, engine)


def _safe_float(value: Any) -> float | None:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    if pd.isna(out):
        return None
    return out


def _signal_matches_order(sig: DS08Signal, order: dict[str, Any]) -> bool:
    order_key = str(order.get("setup_key") or "").strip()
    if not order_key:
        return False
    if sig.key == order_key:
        return True
    return _ds08_setup_keys_match(order_key, sig.key)


def find_first_ds08_activation_bar(
    os_df: pd.DataFrame,
    engine: Any,
    order: dict[str, Any],
    symbol: str,
) -> tuple[int, DS08Signal] | None:
    """H1 上首次出现与挂单 setup_key 一致的 DS08 信号。"""
    if os_df.empty or engine is None:
        return None
    hardened = getattr(engine, "hardened_by_bar", None) or []
    sym = str(symbol).upper().replace("USDT", "")
    used: set[str] = set()
    first: tuple[int, DS08Signal] | None = None
    for i in range(len(os_df)):
        skeleton = hardened[i] if i < len(hardened) else []
        sig = make_ds08_signal(os_df, i, skeleton, used, symbol=sym)
        if sig is not None:
            if first is None and _signal_matches_order(sig, order):
                first = (i, sig)
            used.add(sig.key)
    return first


def find_missed_ds08_activation(
    os_df: pd.DataFrame,
    engine: Any,
    order: dict[str, Any],
    symbol: str,
    *,
    max_lag_bars: int = DEFAULT_DS08_MAX_LAG_BARS,
) -> dict[str, Any] | None:
    """激活棍已在更早 H1 收盘成立且超出允许滞后窗口 → 不得再用 ticker 补成交。"""
    first = find_first_ds08_activation_bar(os_df, engine, order, symbol)
    if first is None:
        return None
    act_i, sig = first
    last_i = len(os_df) - 1
    if last_i - act_i <= int(max_lag_bars):
        return None
    row = os_df.iloc[act_i]
    return {
        "stale": True,
        "reason": "ds08_activation_bar_missed",
        "activation_bar_idx": int(act_i),
        "activation_bar_time": str(pd.to_datetime(row["date"])),
        "entry_fill_calc": float(entry_fill(row, sig)),
        "max_lag_bars": int(max_lag_bars),
        "last_bar_idx": int(last_i),
    }


def resolve_ds08_pending_fill_from_os_df(
    order: dict[str, Any],
    symbol: str,
    os_df: pd.DataFrame,
    engine: Any,
    *,
    live_price: float | None = None,
    max_lag_bars: int = DEFAULT_DS08_MAX_LAG_BARS,
) -> dict[str, Any] | None:
    """DS08 模拟成交：仅在 H1 激活棍窗口内，用 entry_fill 落账（不用 Binance 现价）。"""
    if os_df.empty or engine is None:
        return None

    missed = find_missed_ds08_activation(
        os_df, engine, order, symbol, max_lag_bars=max_lag_bars
    )
    if missed is not None:
        return missed

    first = find_first_ds08_activation_bar(os_df, engine, order, symbol)
    if first is None:
        return None

    act_i, sig = first
    last_i = len(os_df) - 1
    if last_i - act_i > int(max_lag_bars):
        return None

    trigger = _safe_float(order.get("trigger_price")) or float(sig.entry_ref)
    side = _side_int(order.get("side"))
    if live_price is not None:
        if not pending_price_fill_ok(side, float(trigger), float(live_price)):
            return None

    row = os_df.iloc[act_i]
    stop = _safe_float(order.get("stop_price"))
    initial_stop = float(sig.initial_stop)
    if stop is not None and stop > 0:
        initial_stop = float(stop)
    return {
        "fill_price": float(entry_fill(row, sig)),
        "initial_stop": initial_stop,
        "activation_bar_idx": int(act_i),
        "activation_bar_time": str(pd.to_datetime(row["date"])),
        "entry_ref": float(sig.entry_ref),
        "price_source": "ds08_entry_fill",
    }


def resolve_ds08_pending_fill(
    order: dict[str, Any],
    symbol: str,
    data_dir: Path,
    os_state_dir: Path | str | None,
    *,
    live_price: float | None = None,
    gap: int = 3,
    max_lag_bars: int = DEFAULT_DS08_MAX_LAG_BARS,
) -> dict[str, Any] | None:
    os_df, engine = load_ds08_h1_os_frame(symbol, data_dir, os_state_dir, gap=gap)
    return resolve_ds08_pending_fill_from_os_df(
        order,
        symbol,
        os_df,
        engine,
        live_price=live_price,
        max_lag_bars=max_lag_bars,
    )
