from __future__ import annotations

import argparse
import json
import math
import os
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))
if str(ROOT / "packages" / "fengji_core") not in sys.path:
    sys.path.insert(0, str(ROOT / "packages" / "fengji_core"))

from quant.ds01 import ds01_left_filter_pass, ds01_os_defense_missing
from quant.ds03 import resolve_ds03_attack
from quant.ds04 import make_ds04_signal
from quant.ds05 import make_ds05_signal
from quant.ds07 import attach_os_detail, make_ds07_signal, map_d1_to_h1_future
from quant.ds09 import assign_session_date, build_prev_day_boundary_map, make_ds09_signal
from quant.os_engine import FengJiOSIdentityEngine
from fengji_core.data import parse_tq_datetime_series, valid_futures_price_mask
from fengji_core.os_state_store import (
    build_os_detail_frame_stateful as _build_os_detail_frame_stateful,
    find_data_file,
    is_futures_market,
    os_state_path,
)


DEFAULT_SYMBOLS = [
    "BTCUSDT",
    "ETHUSDT",
    "SOLUSDT",
    "AVAXUSDT",
    "TRUMPUSDT",
    "RENDERUSDT",
    "IOUSDT",
    "TAOUSDT",
    "DASHUSDT",
    "LTCUSDT",
    "DOGEUSDT",
    "ADAUSDT",
    "APTUSDT",
    "LINKUSDT",
    "BNBUSDT",
    "ZECUSDT",
    "XRPUSDT",
    "HYPEUSDT",
    "ATHUSDT",
    "PEPEUSDT",
    "ARBUSDT",
    "OPUSDT",
    "SUIUSDT",
    "NEARUSDT",
    "INJUSDT",
    "WLDUSDT",
]

VALID_MARKETS = {"crypto", "futures"}


@dataclass
class RadarRow:
    symbol: str
    strategy_id: str
    timeframe: str
    side: str
    status: str
    setup: str
    current_price: float
    trigger_price: float
    distance_pct: float
    stop_price: float | None
    os_camp: str
    latest_time: str
    score: float
    reason: str
    setup_key: str = ""


def normalize_symbol(symbol: str) -> str:
    text = symbol.strip().upper().replace("-", "").replace("_", "")
    return text if text.endswith("USDT") else f"{text}USDT"


def split_symbols(text: str) -> list[str]:
    return [item.strip().upper() for item in str(text or "").split(",") if item.strip()]


def discover_futures_symbols(data_dir: Path) -> list[str]:
    """Discover domestic futures symbols from data/1d without duplicating USDT aliases."""
    one_day = data_dir / "1d"
    if not one_day.exists():
        return []
    symbols: set[str] = set()
    for path in one_day.glob("*.csv"):
        stem = path.stem.strip().upper().replace("-", "").replace("_", "")
        if not stem:
            continue
        symbols.add(stem.removesuffix("USDT"))
    return sorted(symbols)


def resolve_symbols(args: argparse.Namespace, market: str, data_dir: Path) -> list[str]:
    explicit = split_symbols(str(getattr(args, "symbols", "") or ""))
    if explicit:
        return [normalize_symbol(item) for item in explicit]
    if market == "futures":
        return [normalize_symbol(item) for item in discover_futures_symbols(data_dir)]
    return [normalize_symbol(item) for item in DEFAULT_SYMBOLS]


def resolve_market(args: argparse.Namespace, environ: dict[str, str] | None = None) -> str:
    explicit = str(getattr(args, "market", "") or "").strip().lower()
    if explicit in VALID_MARKETS:
        return explicit

    env = environ if environ is not None else os.environ
    from_env = str(env.get("FENGJI_MARKET", "") or "").strip().lower()
    if from_env in VALID_MARKETS:
        return from_env

    symbols = split_symbols(str(getattr(args, "symbols", "") or ""))
    if symbols:
        return "crypto" if all(symbol.endswith("USDT") for symbol in symbols) else "futures"

    data_hint = str(getattr(args, "data_dir", "") or "").lower()
    if "futures" in data_hint:
        return "futures"
    if "crypto" in data_hint:
        return "crypto"

    return "crypto"


def futures_session_placeholder_mask(frame: pd.DataFrame) -> pd.Series:
    """Drop closed-session placeholders, but keep valid zero-volume bars with price movement."""
    zero_volume = frame["volume"].fillna(0) <= 0
    ohlc_range = frame[["open", "high", "low", "close"]].max(axis=1) - frame[
        ["open", "high", "low", "close"]
    ].min(axis=1)
    return zero_volume & (ohlc_range.abs() <= 1e-12)


def load_ohlcv(path: Path, atr_window: int = 14, tail_rows: int = 0) -> pd.DataFrame:
    frame = pd.read_csv(path)
    frame.columns = [str(column).strip().lower() for column in frame.columns]
    if "date" not in frame.columns:
        for candidate in ["timestamp", "datetime", "time"]:
            if candidate in frame.columns:
                frame = frame.rename(columns={candidate: "date"})
                break
    if "date" not in frame.columns and len(frame.columns) >= 6:
        frame = frame.rename(columns={frame.columns[0]: "date"})
    required = ["date", "open", "high", "low", "close", "volume"]
    missing = [column for column in required if column not in frame.columns]
    if missing:
        raise ValueError(f"{path} missing columns: {missing}")
    frame = frame[required].copy()
    frame["date"] = parse_tq_datetime_series(frame["date"])
    max_reasonable_time = pd.Timestamp.now() + pd.Timedelta(days=1)
    frame = frame[frame["date"] <= max_reasonable_time]
    for column in ["open", "high", "low", "close", "volume"]:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    frame = frame.dropna(subset=["date", "open", "high", "low", "close"])
    if is_futures_market():
        frame = frame[
            (frame["date"] >= pd.Timestamp("2020-01-01"))
            & valid_futures_price_mask(frame)
        ]
        frame = frame[~futures_session_placeholder_mask(frame)]
    else:
        frame = frame[
            (frame["date"] >= pd.Timestamp("2020-01-01"))
            & (frame["high"] >= frame["low"])
            & (frame["close"] > 0)
        ]
    frame = frame.sort_values("date").drop_duplicates("date", keep="last")
    if tail_rows > 0 and len(frame) > tail_rows:
        frame = frame.tail(tail_rows).copy()
    prev_close = frame["close"].shift(1)
    ranges = pd.concat(
        [
            frame["high"] - frame["low"],
            (frame["high"] - prev_close).abs(),
            (frame["low"] - prev_close).abs(),
        ],
        axis=1,
    )
    frame["tr"] = ranges.max(axis=1)
    frame["atr"] = frame["tr"].rolling(atr_window).mean()
    return frame.reset_index(drop=True)


def build_os_detail_frame_stateful(
    df: pd.DataFrame,
    gap: int,
    state_path: Path | None = None,
    *,
    record_hardened_by_bar: bool = True,
) -> tuple[pd.DataFrame, FengJiOSIdentityEngine]:
    return _build_os_detail_frame_stateful(
        df,
        gap,
        state_path,
        attach_os_detail,
        record_hardened_by_bar=record_hardened_by_bar,
    )


def safe_float(value: Any) -> float | None:
    try:
        out = float(value)
    except Exception:
        return None
    if math.isnan(out):
        return None
    return out


def safe_int(value: Any) -> int | None:
    try:
        out = int(value)
    except Exception:
        return None
    return out


def camp_name(value: Any) -> str:
    try:
        camp = int(value)
    except Exception:
        return "neutral"
    if camp == 1:
        return "red"
    if camp == -1:
        return "blue"
    return "neutral"


def key_time(value: Any) -> str:
    ts = pd.to_datetime(value, errors="coerce")
    if pd.isna(ts):
        return str(value)
    return ts.strftime("%Y%m%d%H%M%S")


def distance_pct(side: str, current: float, trigger: float) -> float:
    if current <= 0 or math.isnan(current) or math.isnan(trigger):
        return math.nan
    if side == "long":
        return (trigger - current) / current
    return (current - trigger) / current


def status_from_price(side: str, high: float, low: float, trigger: float, base_status: str = "PENDING") -> str:
    if side == "long" and high >= trigger:
        return "TRIGGERED"
    if side == "short" and low <= trigger:
        return "TRIGGERED"
    return base_status


def os_defense_missing(camp: int, row: pd.Series) -> bool:
    return ds01_os_defense_missing(camp, row)


def make_row(
    rows: list[RadarRow],
    *,
    symbol: str,
    strategy_id: str,
    timeframe: str,
    side: str,
    status: str,
    setup: str,
    current_price: float,
    trigger_price: float,
    stop_price: float | None,
    os_camp: str,
    latest_time: Any,
    reason: str,
    setup_key: str = "",
) -> None:
    dist = distance_pct(side, current_price, trigger_price)
    if status == "CONFIRM_ON_CLOSE":
        score = 50.0
    elif status == "INVALIDATED":
        score = 80.0
    elif status.startswith("TRIGGERED"):
        score = 0.0
    else:
        score = max(dist, 0.0) if not math.isnan(dist) else 999.0
    rows.append(
        RadarRow(
            symbol=symbol,
            strategy_id=strategy_id,
            timeframe=timeframe,
            side=side,
            status=status,
            setup=setup,
            current_price=float(current_price),
            trigger_price=float(trigger_price),
            distance_pct=float(dist),
            stop_price=None if stop_price is None else float(stop_price),
            os_camp=os_camp,
            latest_time=str(latest_time),
            score=float(score),
            reason=reason,
            setup_key=str(setup_key or ""),
        )
    )


def latest_price(paths: dict[str, Path], atr_window: int) -> float:
    for tf in ["15m", "1h", "1d"]:
        p = paths.get(tf)
        if p and p.exists():
            df = load_ohlcv(p, atr_window=atr_window, tail_rows=5)
            if not df.empty:
                return float(df["close"].iloc[-1])
    return math.nan


def add_ds01(rows: list[RadarRow], symbol: str, d1: pd.DataFrame, d1_engine: Any, current: float) -> None:
    if len(d1) < 2:
        return
    i = len(d1) - 1
    prev = d1.iloc[i - 1]
    cur = d1.iloc[i]
    # DS01 is authorized by the last completed D1 OS state; the current D1 bar
    # is only used as the intraday price probe.  Using cur.active_* can let a
    # defense point confirmed today authorize yesterday's signal retroactively.
    camp = int(prev.get("camp", 0))
    visible = d1_engine.hardened_by_bar[max(0, i - 1)] if d1_engine.hardened_by_bar else []

    if camp == 1 and float(prev["close"]) > float(prev["open"]):
        trigger = float(prev["high"])
        left_price = float(cur["high"]) if float(cur["high"]) >= trigger else trigger
        left_ok, left_count = ds01_left_filter_pass(visible, i, left_price, False)
        status = status_from_price("long", float(cur["high"]), float(cur["low"]), trigger)
        reason_parts = [f"left_count={left_count}", f"left_check_price={left_price:.8g}"]
        if not left_ok:
            status = "BLOCKED_LEFT_LINES"
        if os_defense_missing(camp, prev):
            status = "BLOCKED_OS_INCOMPLETE"
            reason_parts.append("missing_red_ext")
        make_row(
            rows,
            symbol=symbol,
            strategy_id="DS01",
            timeframe="D1",
            side="long",
            status=status,
            setup="yesterday red-camp bullish stick; initial/add decided by position state",
            current_price=current,
            trigger_price=trigger,
            stop_price=float(prev["low"]),
            os_camp=camp_name(camp),
            latest_time=cur["date"],
            reason=", ".join(reason_parts),
            setup_key=f"{symbol}|DS01|LONG|signal={key_time(prev['date'])}|trigger={trigger:.10g}",
        )

    if camp == -1 and float(prev["close"]) < float(prev["open"]):
        trigger = float(prev["low"])
        left_price = float(cur["low"]) if float(cur["low"]) <= trigger else trigger
        left_ok, left_count = ds01_left_filter_pass(visible, i, left_price, False)
        status = status_from_price("short", float(cur["high"]), float(cur["low"]), trigger)
        reason_parts = [f"left_count={left_count}", f"left_check_price={left_price:.8g}"]
        if not left_ok:
            status = "BLOCKED_LEFT_LINES"
        if os_defense_missing(camp, prev):
            status = "BLOCKED_OS_INCOMPLETE"
            reason_parts.append("missing_blue_ext")
        make_row(
            rows,
            symbol=symbol,
            strategy_id="DS01",
            timeframe="D1",
            side="short",
            status=status,
            setup="yesterday blue-camp bearish stick; initial/add decided by position state",
            current_price=current,
            trigger_price=trigger,
            stop_price=float(prev["high"]),
            os_camp=camp_name(camp),
            latest_time=cur["date"],
            reason=", ".join(reason_parts),
            setup_key=f"{symbol}|DS01|SHORT|signal={key_time(prev['date'])}|trigger={trigger:.10g}",
        )


def add_ds03(rows: list[RadarRow], symbol: str, d1: pd.DataFrame, current: float) -> None:
    if len(d1) < 2:
        return
    i = len(d1) - 1
    cur = d1.iloc[i]
    prev = d1.iloc[i - 1]
    prev_camp = int(prev.get("camp", 0))
    attack = resolve_ds03_attack(d1, i)
    if attack is None:
        if prev_camp == 1:
            trigger = safe_float(prev.get("active_high"))
            attack_idx = safe_int(prev.get("red_peak_idx"))
            if trigger is None or os_defense_missing(prev_camp, prev):
                return
            side = "long"
            setup = "red camp break active high"
            stop = min(float(prev["low"]), float(cur["low"]))
            camp = "red"
            reason = f"prev_active_high={trigger:.8g}, attack_idx={attack_idx}"
        elif prev_camp == -1:
            trigger = safe_float(prev.get("active_low"))
            attack_idx = safe_int(prev.get("blue_peak_idx"))
            if trigger is None or os_defense_missing(prev_camp, prev):
                return
            side = "short"
            setup = "blue camp break active low"
            stop = max(float(prev["high"]), float(cur["high"]))
            camp = "blue"
            reason = f"prev_active_low={trigger:.8g}, attack_idx={attack_idx}"
        else:
            return
        if status_from_price(side, float(cur["high"]), float(cur["low"]), trigger) == "TRIGGERED":
            return
        setup_key = f"{symbol}|DS03|{side.upper()}|watch|trigger={trigger:.10g}"
    else:
        trigger = float(attack.entry_ref)
        attack_idx = int(attack.ref_idx)
        side = "long" if attack.side == 1 else "short"
        peak_key = attack.peak_key
        if attack.trigger_source == "fake_peak" and attack.side == 1:
            setup = "red camp break fake peak (starter bar only)"
            stop = min(float(prev["low"]), float(cur["low"]))
            camp = "red"
            cap = safe_float(prev.get("active_high"))
            cap_text = f"{cap:.8g}" if cap is not None else "nan"
            reason = (
                f"fake_peak={trigger:.8g}, true_peak_cap={cap_text}, attack_idx={attack_idx}, "
                f"defense_idx={safe_int(cur.get('red_ext_idx'))}, peak_key={peak_key}"
            )
        elif attack.trigger_source == "fake_peak":
            setup = "blue camp break fake peak (starter bar only)"
            stop = max(float(prev["high"]), float(cur["high"]))
            camp = "blue"
            cap = safe_float(prev.get("active_low"))
            cap_text = f"{cap:.8g}" if cap is not None else "nan"
            reason = (
                f"fake_peak={trigger:.8g}, true_peak_cap={cap_text}, attack_idx={attack_idx}, "
                f"defense_idx={safe_int(cur.get('blue_ext_idx'))}, peak_key={peak_key}"
            )
        elif attack.side == 1:
            setup = "red camp break true peak (starter bar only)"
            stop = min(float(prev["low"]), float(cur["low"]))
            camp = "red"
            reason = f"true_peak={trigger:.8g}, attack_idx={attack_idx}, peak_key={peak_key}"
        else:
            setup = "blue camp break true peak (starter bar only)"
            stop = max(float(prev["high"]), float(cur["high"]))
            camp = "blue"
            reason = f"true_peak={trigger:.8g}, attack_idx={attack_idx}, peak_key={peak_key}"
        setup_key = f"{symbol}|{peak_key}"

    make_row(
        rows,
        symbol=symbol,
        strategy_id="DS03",
        timeframe="D1",
        side=side,
        status=status_from_price(side, float(cur["high"]), float(cur["low"]), trigger),
        setup=setup,
        current_price=current,
        trigger_price=trigger,
        stop_price=stop,
        os_camp=camp,
        latest_time=cur["date"],
        reason=reason,
        setup_key=setup_key,
    )


def node_key(node: Any) -> tuple[int, int, str, float]:
    return (int(node.point_idx), int(node.confirm_idx), str(node.raw_type), float(node.price))


def new_hardened_nodes_at(hardened_by_bar: list[list[Any]], i: int) -> list[Any]:
    current = hardened_by_bar[i] if i < len(hardened_by_bar) else []
    previous = hardened_by_bar[i - 1] if i > 0 and i - 1 < len(hardened_by_bar) else []
    previous_keys = {node_key(node) for node in previous}
    return sorted(
        [node for node in current if node_key(node) not in previous_keys and int(node.confirm_idx) == i],
        key=lambda node: (node.point_idx, node.confirm_idx, node.raw_type),
    )


def ds06_initial_stop(df: pd.DataFrame, i: int, mode: str) -> float:
    start = max(0, i - 1)
    if mode == "LONG":
        return float(df["low"].iloc[start : i + 1].min())
    return float(df["high"].iloc[start : i + 1].max())


def latest_ds06_setup(df: pd.DataFrame, engine: Any) -> dict[str, Any] | None:
    turns_by_idx = {int(turn.idx): turn for turn in engine.turns}
    active: dict[str, Any] | None = None
    latest: dict[str, Any] | None = None

    for i in range(len(df)):
        if i in turns_by_idx:
            turn = turns_by_idx[i]
            if turn.turn == "BLUE_TO_RED":
                active = {"mode": "LONG", "state": "WAIT_D", "turn": turn}
            elif turn.turn == "RED_TO_BLUE":
                active = {"mode": "SHORT", "state": "WAIT_D", "turn": turn}
            else:
                active = None

        if active is None:
            continue

        mode = active["mode"]
        row = df.iloc[i]
        if mode == "LONG" and active["state"] == "WAIT_E":
            d_node = active["d_node"]
            if i > d_node.confirm_idx and float(row["high"]) > float(d_node.price):
                active = {"mode": mode, "state": "WAIT_D", "turn": active["turn"]}
        if mode == "SHORT" and active["state"] == "WAIT_E":
            d_node = active["d_node"]
            if i > d_node.confirm_idx and float(row["low"]) < float(d_node.price):
                active = {"mode": mode, "state": "WAIT_D", "turn": active["turn"]}

        for node in new_hardened_nodes_at(engine.hardened_by_bar, i):
            turn = active["turn"]
            state = active["state"]
            if mode == "LONG" and state == "WAIT_D" and node.raw_type == "HIGH" and node.point_idx > turn.idx and node.confirm_idx > turn.idx:
                active["d_node"] = node
                active["state"] = "WAIT_E"
                continue
            if mode == "SHORT" and state == "WAIT_D" and node.raw_type == "LOW" and node.point_idx > turn.idx and node.confirm_idx > turn.idx:
                active["d_node"] = node
                active["state"] = "WAIT_E"
                continue
            if mode == "LONG" and state == "WAIT_E":
                d_node = active["d_node"]
                if node.raw_type == "LOW" and node.point_idx > d_node.point_idx and node.point_idx > d_node.confirm_idx and float(d_node.price) > float(node.price):
                    active["e_node"] = node
                    active["state"] = "WAIT_F"
                continue
            if mode == "SHORT" and state == "WAIT_E":
                d_node = active["d_node"]
                if node.raw_type == "HIGH" and node.point_idx > d_node.point_idx and node.point_idx > d_node.confirm_idx and float(d_node.price) < float(node.price):
                    active["e_node"] = node
                    active["state"] = "WAIT_F"
                continue

        if active is None or active["state"] != "WAIT_F":
            continue
        d_node = active["d_node"]
        e_node = active["e_node"]
        if mode == "LONG" and i > e_node.confirm_idx and float(row["high"]) > float(d_node.price):
            latest = {
                "mode": mode,
                "status": "TRIGGERED",
                "i": i,
                "trigger": float(d_node.price),
                "stop": ds06_initial_stop(df, i, mode),
                "d_idx": int(d_node.point_idx),
                "e_idx": int(e_node.point_idx),
            }
            active = None
        elif mode == "SHORT" and i > e_node.confirm_idx and float(row["low"]) < float(d_node.price):
            latest = {
                "mode": mode,
                "status": "TRIGGERED",
                "i": i,
                "trigger": float(d_node.price),
                "stop": ds06_initial_stop(df, i, mode),
                "d_idx": int(d_node.point_idx),
                "e_idx": int(e_node.point_idx),
            }
            active = None

    if active is not None and active.get("state") == "WAIT_F":
        d_node = active["d_node"]
        e_node = active["e_node"]
        i = len(df) - 1
        mode = active["mode"]
        return {
            "mode": mode,
            "status": "PENDING",
            "i": i,
            "trigger": float(d_node.price),
            "stop": ds06_initial_stop(df, i, mode),
            "d_idx": int(d_node.point_idx),
            "e_idx": int(e_node.point_idx),
        }
    if latest is not None and int(latest.get("i", -1)) == len(df) - 1:
        return latest
    return None


def add_ds06(rows: list[RadarRow], symbol: str, d1: pd.DataFrame, d1_engine: Any, current: float) -> None:
    setup = latest_ds06_setup(d1, d1_engine)
    if setup is None:
        return
    side = "long" if setup["mode"] == "LONG" else "short"
    cur = d1.iloc[-1]
    make_row(
        rows,
        symbol=symbol,
        strategy_id="DS06",
        timeframe="D1",
        side=side,
        status=setup["status"],
        setup="revolution D/E complete, waiting external break",
        current_price=current,
        trigger_price=float(setup["trigger"]),
        stop_price=float(setup["stop"]),
        os_camp=camp_name(cur.get("camp", 0)),
        latest_time=cur["date"],
        reason=f"DS06 strict D/E/F state, d_idx={setup.get('d_idx')}, e_idx={setup.get('e_idx')}, stop=last2-bars",
        setup_key=f"{symbol}|DS06|{setup['mode']}|d={setup.get('d_idx')}|e={setup.get('e_idx')}|trigger={float(setup['trigger']):.10g}",
    )


def add_ds05(rows: list[RadarRow], symbol: str, d1: pd.DataFrame, current: float, extreme_atr_tol: float) -> None:
    if len(d1) < 5:
        return
    i = len(d1) - 1
    signal = make_ds05_signal(d1, i, extreme_atr_tol)
    if signal is None:
        return

    k2 = d1.iloc[signal.k2]
    k3 = d1.iloc[signal.k3]
    side = "long" if signal.side == 1 else "short"
    direction = "LONG" if signal.side == 1 else "SHORT"
    camp = "red" if signal.side == 1 else "blue"
    trigger = float(signal.entry_price)
    attack_ref = "k2_high" if signal.side == 1 else "k2_low"
    setup = (
        "red-camp finger: K2 possible extreme, K3 breaks K2 attack side"
        if signal.side == 1
        else "blue-camp finger: K2 possible extreme, K3 breaks K2 attack side"
    )
    make_row(
        rows,
        symbol=symbol,
        strategy_id="DS05",
        timeframe="D1",
        side=side,
        status=status_from_price(side, float(k3["high"]), float(k3["low"]), trigger),
        setup=setup,
        current_price=current,
        trigger_price=trigger,
        stop_price=float(signal.initial_stop),
        os_camp=camp,
        latest_time=k3["date"],
        reason=(
            f"k1={signal.k1}, k2={signal.k2}, k3={signal.k3}, "
            f"k2_possible_extreme={signal.k2_possible_extreme:.8g}, attack_ref={attack_ref}"
        ),
        setup_key=(
            f"{symbol}|DS05|{direction}|k2={key_time(k2['date'])}|"
            f"k3={key_time(k3['date'])}|trigger={trigger:.10g}"
        ),
    )


def add_ds04(rows: list[RadarRow], symbol: str, d1: pd.DataFrame, current: float) -> None:
    if len(d1) < 4:
        return
    k3_idx = len(d1) - 2
    signal = make_ds04_signal(d1, k3_idx)
    if signal is None or int(signal.activate_idx) != len(d1) - 1:
        return
    k1 = d1.iloc[signal.k1]
    k2 = d1.iloc[signal.k2]
    k3 = d1.iloc[signal.k3]
    k4 = d1.iloc[signal.activate_idx]
    side = "long" if signal.side == 1 else "short"
    trigger = float(k4["open"])
    setup = "yang-yin-yang reclaim, K4 open long" if signal.side == 1 else "yin-yang-yin reclaim, K4 open short"
    make_row(
        rows,
        symbol=symbol,
        strategy_id="DS04",
        timeframe="D1",
        side=side,
        status="PENDING",
        setup=setup,
        current_price=current,
        trigger_price=trigger,
        stop_price=float(signal.initial_stop),
        os_camp=camp_name(k3.get("camp", 0)),
        latest_time=k4["date"],
        reason=(
            f"k1={signal.k1}, k2={signal.k2}, k3={signal.k3}, k4={signal.activate_idx}, "
            f"reclaim_price={float(signal.reclaim_price):.8g}, k4_open={trigger:.8g}, "
            f"k1_date={key_time(k1['date'])}, k2_date={key_time(k2['date'])}, k3_date={key_time(k3['date'])}"
        ),
        setup_key=(
            f"{symbol}|DS04|{side.upper()}|k1={key_time(k1['date'])}|"
            f"k2={key_time(k2['date'])}|k3={key_time(k3['date'])}|k4={key_time(k4['date'])}|trigger={trigger:.10g}"
        ),
    )


def has_n(row: pd.Series) -> bool:
    return int(row.get("hardened_count", 0) or 0) >= 4


def add_ds07(rows: list[RadarRow], symbol: str, d1: pd.DataFrame, h1: pd.DataFrame, current: float) -> None:
    if len(h1) < 2 or d1.empty:
        return
    mapped = map_d1_to_h1_future(d1, h1)
    if len(mapped) < 2:
        return
    i = len(mapped) - 1
    cur = mapped.iloc[i]
    prev = mapped.iloc[i - 1]
    signal = make_ds07_signal(cur, i, set(), symbol=symbol, prev_row=prev, df=mapped)
    if signal is None:
        return

    side = "long" if signal.side == 1 else "short"
    direction = "LONG" if signal.side == 1 else "SHORT"
    trigger = float(signal.attack_price)
    stop = float(signal.defense_price)
    if side == "long" and stop >= max(float(cur["open"]), trigger):
        return
    if side == "short" and stop <= min(float(cur["open"]), trigger):
        return

    setup = (
        "D1 red + H1 red DS03 continuation"
        if signal.trigger_type == "LONG_CONTINUE"
        else "D1 blue + H1 blue DS03 continuation"
    )
    setup_key = f"{symbol}|DS07|{direction}|CONT|attack={signal.attack_idx}|defense={signal.defense_idx}|trigger={trigger:.10g}"
    if side == "long":
        status = "TRIGGERED" if float(cur["high"]) > trigger else "PENDING"
    else:
        status = "TRIGGERED" if float(cur["low"]) < trigger else "PENDING"
    make_row(
        rows,
        symbol=symbol,
        strategy_id="DS07",
        timeframe="H1",
        side=side,
        status=status,
        setup=setup,
        current_price=current,
        trigger_price=trigger,
        stop_price=stop,
        os_camp=f"D1={camp_name(signal.d1_camp)},H1={camp_name(signal.h1_camp)}",
        latest_time=cur["date"],
        reason=(
            f"prev_h1_camp={camp_name(signal.prev_h1_camp)}, ds03={signal.pattern}, "
            f"hardened_count={int(prev.get('hardened_count', 0) or 0)}, "
            f"attack_idx={signal.attack_idx}, defense_idx={signal.defense_idx}"
        ),
        setup_key=setup_key,
    )


def add_ds08(rows: list[RadarRow], symbol: str, h1: pd.DataFrame, h1_engine: Any, current: float) -> None:
    if len(h1) < 6:
        return
    hardened_by_bar = getattr(h1_engine, "hardened_by_bar", None) or []
    hardened_nodes = getattr(h1_engine, "hardened_nodes", None) or []
    if not hardened_nodes and not any(hardened_by_bar):
        return
    i = len(h1) - 1
    cur = h1.iloc[-1]
    if getattr(h1_engine, "hardened_by_bar", []) and i < len(h1_engine.hardened_by_bar):
        visible_nodes = h1_engine.hardened_by_bar[i]
    else:
        visible_nodes = h1_engine.hardened_nodes
    skeleton = sorted(visible_nodes, key=lambda node: (node.point_idx, node.confirm_idx))
    if len(skeleton) < 5:
        return
    nodes = skeleton[-5:]
    roles = ["P" if node.raw_type == "HIGH" else "V" for node in nodes]

    if roles == ["V", "P", "V", "P", "V"]:
        v1, p1, v2, p2, v3 = nodes
        if float(v3.price) > float(v2.price) > float(v1.price) and float(p2.price) > float(p1.price) and i > int(v3.confirm_idx):
            trigger = float(p2.price)
            stop = float(v3.price)
            wait_high = float(h1["high"].iloc[int(v3.point_idx) : int(v3.confirm_idx) + 1].max())
            prev_high = float(h1["high"].iloc[int(v3.confirm_idx) + 1 : i].max()) if int(v3.confirm_idx) + 1 <= i - 1 else -math.inf
            key = f"{symbol}|LONG|{int(v3.point_idx)}|{int(p2.point_idx)}|{trigger:.10g}"
            invalid_reason = ""
            if wait_high > trigger:
                invalid_reason = "wait_high_gt_trigger"
            elif prev_high > trigger:
                invalid_reason = "prev_high_gt_trigger"
            elif stop >= max(float(cur["open"]), trigger):
                invalid_reason = "invalid_stop"
            status = "INVALIDATED" if invalid_reason else ("TRIGGERED" if float(cur["high"]) > trigger else "PENDING")
            reason = f"roles={''.join(roles)}, key={key}, wait_high={wait_high:.8g}, prev_high={prev_high:.8g}"
            if invalid_reason:
                reason = f"{reason}, invalid={invalid_reason}"
            make_row(rows, symbol=symbol, strategy_id="DS08", timeframe="H1", side="long", status=status, setup="five-point long power seizure", current_price=current, trigger_price=trigger, stop_price=stop, os_camp=camp_name(cur.get("camp", 0)), latest_time=cur["date"], reason=reason, setup_key=key)

    if roles == ["P", "V", "P", "V", "P"]:
        p1, v1, p2, v2, p3 = nodes
        if float(p3.price) < float(p2.price) < float(p1.price) and float(v2.price) < float(v1.price) and i > int(p3.confirm_idx):
            trigger = float(v2.price)
            stop = float(p3.price)
            wait_low = float(h1["low"].iloc[int(p3.point_idx) : int(p3.confirm_idx) + 1].min())
            prev_low = float(h1["low"].iloc[int(p3.confirm_idx) + 1 : i].min()) if int(p3.confirm_idx) + 1 <= i - 1 else math.inf
            key = f"{symbol}|SHORT|{int(p3.point_idx)}|{int(v2.point_idx)}|{trigger:.10g}"
            invalid_reason = ""
            if wait_low < trigger:
                invalid_reason = "wait_low_lt_trigger"
            elif prev_low < trigger:
                invalid_reason = "prev_low_lt_trigger"
            elif stop <= min(float(cur["open"]), trigger):
                invalid_reason = "invalid_stop"
            status = "INVALIDATED" if invalid_reason else ("TRIGGERED" if float(cur["low"]) < trigger else "PENDING")
            reason = f"roles={''.join(roles)}, key={key}, wait_low={wait_low:.8g}, prev_low={prev_low:.8g}"
            if invalid_reason:
                reason = f"{reason}, invalid={invalid_reason}"
            make_row(rows, symbol=symbol, strategy_id="DS08", timeframe="H1", side="short", status=status, setup="five-point short power seizure", current_price=current, trigger_price=trigger, stop_price=stop, os_camp=camp_name(cur.get("camp", 0)), latest_time=cur["date"], reason=reason, setup_key=key)


def replay_ds09_session(m15: pd.DataFrame, boundary_map: dict[pd.Timestamp, dict[str, Any]], symbol: str) -> tuple[dict[str, Any] | None, pd.Series | None, Any]:
    """Replay today's M15 session; return day_state, last bar, optional entry signal on last bar."""
    if m15.empty or "session_date" not in m15.columns:
        return None, None, None
    session_date = pd.to_datetime(m15.iloc[-1]["session_date"]).normalize()
    if session_date not in boundary_map:
        return None, None, None
    day_state: dict[str, Any] = {
        **boundary_map[session_date],
        "lock_idx": None,
        "consumed": False,
        "attack_idx": None,
        "attack_price": None,
        "defense_idx": None,
        "defense_price": None,
    }
    last_row: pd.Series | None = None
    last_signal = None
    for i, row in m15.iterrows():
        if pd.to_datetime(row["session_date"]).normalize() != session_date:
            continue
        last_row = row
        if day_state.get("consumed", False):
            break
        if day_state.get("lock_idx") is None:
            boundary = float(day_state["boundary"])
            if day_state["mode"] == "LONG" and float(row["high"]) > boundary:
                day_state["lock_idx"] = int(i)
            elif day_state["mode"] == "SHORT" and float(row["low"]) < boundary:
                day_state["lock_idx"] = int(i)
        else:
            signal = make_ds09_signal(row, day_state, symbol=symbol)
            if signal is not None:
                last_signal = signal
    return day_state, last_row, last_signal


def add_ds09(rows: list[RadarRow], symbol: str, d1: pd.DataFrame, m15: pd.DataFrame, current: float) -> None:
    if d1.empty or m15.empty or "camp" not in d1.columns:
        return
    boundary_map = build_prev_day_boundary_map(d1)
    if not boundary_map:
        return
    futures = is_futures_market()
    m15_sess = assign_session_date(m15, d1, futures=futures)
    if m15_sess.empty:
        return
    day_state, cur, signal = replay_ds09_session(m15_sess, boundary_map, symbol)
    if day_state is None or cur is None:
        return

    mode = str(day_state["mode"])
    side = "long" if mode == "LONG" else "short"
    d1_camp = int(day_state["d1_camp"])
    os_camp = f"D1={camp_name(d1_camp)},M15={camp_name(int(cur.get('camp', 0)))}"

    if signal is not None:
        trigger = float(signal.entry_ref)
        stop = float(signal.initial_stop)
        status = status_from_price(side, float(cur["high"]), float(cur["low"]), trigger)
        make_row(
            rows,
            symbol=symbol,
            strategy_id="DS09",
            timeframe="M15",
            side=side,
            status=status,
            setup=str(signal.pattern),
            current_price=current,
            trigger_price=trigger,
            stop_price=stop,
            os_camp=os_camp,
            latest_time=cur["date"],
            reason=(
                f"session={signal.session_date}, lock={signal.lock_idx}, attack={signal.attack_idx}@{signal.attack_price:.8g}, "
                f"defense={signal.defense_idx}@{signal.defense_price:.8g}, boundary={signal.d1_boundary:.8g}"
            ),
            setup_key=str(signal.key),
        )
        return

    if day_state.get("consumed", False):
        return

    if day_state.get("defense_idx") is not None and day_state.get("attack_price") is not None:
        trigger = float(day_state["attack_price"])
        stop = float(day_state["defense_price"])
        if side == "long" and float(stop) >= max(float(cur["open"]), trigger):
            return
        if side == "short" and float(stop) <= min(float(cur["open"]), trigger):
            return
        session_date = pd.to_datetime(cur["session_date"]).normalize()
        setup_key = (
            f"{symbol}|DS09|{mode}|{session_date}|"
            f"lock={day_state.get('lock_idx')}|def={day_state.get('defense_idx')}|{trigger:.10g}"
        )
        status = status_from_price(side, float(cur["high"]), float(cur["low"]), trigger)
        make_row(
            rows,
            symbol=symbol,
            strategy_id="DS09",
            timeframe="M15",
            side=side,
            status=status,
            setup="DS09 second attack after M15 defense extreme",
            current_price=current,
            trigger_price=trigger,
            stop_price=stop,
            os_camp=os_camp,
            latest_time=cur["date"],
            reason=(
                f"lock_idx={day_state.get('lock_idx')}, attack_idx={day_state.get('attack_idx')}, "
                f"defense_idx={day_state.get('defense_idx')}, boundary={day_state.get('boundary'):.8g}"
            ),
            setup_key=setup_key,
        )


def add_shape_watch(rows: list[RadarRow], symbol: str, strategy_id: str, timeframe: str, current: float, latest_time: Any, camp: Any) -> None:
    make_row(
        rows,
        symbol=symbol,
        strategy_id=strategy_id,
        timeframe=timeframe,
        side="long",
        status="CONFIRM_ON_CLOSE",
        setup=f"{strategy_id} shape strategy requires K-line close confirmation",
        current_price=current,
        trigger_price=current,
        stop_price=None,
        os_camp=camp_name(camp),
        latest_time=latest_time,
        reason="radar placeholder; not a live price trigger yet",
    )


def analyze_symbol(data_dir: Path, symbol: str, args: argparse.Namespace) -> list[RadarRow]:
    clean = normalize_symbol(symbol)
    paths = {tf: find_data_file(data_dir, clean, tf) for tf in ["1d", "1h", "15m"]}
    if not paths["1d"].exists():
        return []
    current = latest_price(paths, args.atr_window)
    state_dir = str(args.os_state_dir or "").strip()
    # Runtime state is bounded by the agreed monitoring windows; full-history
    # intraday state grows too large and is not the live monitoring contract.
    d1_tail = max(int(args.daily_tail or 0), 1095)
    h1_tail = max(int(args.h1_tail or 0), 2400)
    m15_tail = max(int(getattr(args, "m15_tail", 0) or 0), 960)
    d1_raw = load_ohlcv(paths["1d"], args.atr_window, d1_tail)
    d1_state = os_state_path(state_dir, clean, "1d") if state_dir else None
    d1, d1_engine = build_os_detail_frame_stateful(d1_raw, args.gap, d1_state, record_hardened_by_bar=True)
    rows: list[RadarRow] = []
    add_ds01(rows, clean, d1, d1_engine, current)
    add_ds03(rows, clean, d1, current)
    add_ds04(rows, clean, d1, current)
    add_ds05(rows, clean, d1, current, args.extreme_atr_tol)
    add_ds06(rows, clean, d1, d1_engine, current)
    if paths["1h"].exists():
        h1_raw = load_ohlcv(paths["1h"], args.atr_window, h1_tail)
        h1_state = os_state_path(state_dir, clean, "1h") if state_dir else None
        h1, h1_engine = build_os_detail_frame_stateful(h1_raw, args.gap, h1_state, record_hardened_by_bar=False)
        add_ds07(rows, clean, d1, h1, current)
        add_ds08(rows, clean, h1, h1_engine, current)
    if paths["15m"].exists():
        m15_raw = load_ohlcv(paths["15m"], args.atr_window, m15_tail)
        m15_state = os_state_path(state_dir, clean, "15m") if state_dir else None
        m15, _ = build_os_detail_frame_stateful(m15_raw, args.gap, m15_state, record_hardened_by_bar=False)
        add_ds09(rows, clean, d1, m15, current)
    for strategy_id in ["DS02"]:
        add_shape_watch(rows, clean, strategy_id, "D1", current, d1.iloc[-1]["date"], d1.iloc[-1].get("camp", 0))
    return rows


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="FengJi total pattern market radar and pending-trigger preview.")
    parser.add_argument("--data-dir", default="data")
    parser.add_argument("--symbols", default="", help="Comma separated symbols. Empty means crypto defaults or futures data/1d discovery.")
    parser.add_argument("--out-dir", default="runtime/fengji_radar")
    parser.add_argument("--atr-window", type=int, default=14)
    parser.add_argument("--gap", type=int, default=3)
    parser.add_argument("--top-n", type=int, default=80)
    parser.add_argument("--daily-tail", type=int, default=1095, help="日线固化窗口（默认 1095≈3 年）")
    parser.add_argument("--h1-tail", type=int, default=2400, help="小时线固化窗口（默认 2400）")
    parser.add_argument("--m15-tail", type=int, default=960, help="15 分钟固化窗口（默认 960）")
    parser.add_argument("--os-state-dir", default="runtime/fengji_os_state")
    parser.add_argument("--extreme-atr-tol", type=float, default=0.80)
    parser.add_argument(
        "--market",
        choices=["auto", "crypto", "futures"],
        default="auto",
        help="Market mode for data loading and OS state paths.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    market = resolve_market(args)
    os.environ["FENGJI_MARKET"] = market
    data_dir = Path(args.data_dir)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    symbols = resolve_symbols(args, market, data_dir)
    if not symbols:
        raise SystemExit(f"No symbols resolved for market={market} data_dir={data_dir}")
    rows: list[RadarRow] = []
    for symbol in symbols:
        try:
            rows.extend(analyze_symbol(data_dir, symbol, args))
        except Exception as exc:
            make_row(
                rows,
                symbol=normalize_symbol(symbol),
                strategy_id="ERROR",
                timeframe="",
                side="long",
                status="ERROR",
                setup="radar failed",
                current_price=0.0,
                trigger_price=0.0,
                stop_price=None,
                os_camp="unknown",
                latest_time="",
                reason=str(exc),
            )
    payload = [asdict(row) for row in rows]
    frame = pd.DataFrame(payload)
    if not frame.empty:
        frame = frame.sort_values(["score", "status", "symbol", "strategy_id"]).head(args.top_n)
    frame.to_csv(out_dir / "radar.csv", index=False, encoding="utf-8-sig")
    (out_dir / "radar.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(frame.to_string(index=False) if not frame.empty else "No radar rows.")
    print(f"Saved: {out_dir / 'radar.csv'}")


if __name__ == "__main__":
    main()
