"""Post-fill supervision: re-audit simulated opens against FengJi pattern rules."""
from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from fengji_core.ds01 import (
    ds01_left_filter_pass,
    ds01_os_defense_missing,
    entry_fill,
)
from fengji_core.ds03 import entry_fill as ds03_entry_fill, make_ds03_signal, resolve_ds03_attack
from fengji_core.ds03_pending_fill import is_ds03_watch_setup_key
from fengji_core.ds05 import make_ds05_signal
from fengji_core.ds08 import entry_fill as ds08_entry_fill
from fengji_core.ds08 import make_ds08_signal, node_role
from fengji_core.ds07 import attach_os_detail, make_ds07_signal, map_d1_to_h1_future
from fengji_core.os_engine import FengJiOSIdentityEngine

RED = 1
BLUE = -1


@dataclass
class FillAuditResult:
    strategy_id: str
    symbol: str
    side: str
    entry_date: str
    verdict: str  # valid | invalid | needs-data | skipped | exec_gap
    issues: list[str] = field(default_factory=list)
    checks: dict[str, Any] = field(default_factory=dict)
    order_id: str = ""
    setup_key: str = ""
    fill_time: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_os_detail_frame(df: pd.DataFrame, gap: int = 3) -> tuple[pd.DataFrame, FengJiOSIdentityEngine]:
    engine = FengJiOSIdentityEngine(gap=gap, record_hardened_by_bar=True).run(df)
    return attach_os_detail(df.copy(), engine), engine


# 与 fengji_total_radar.py --daily-tail / --h1-tail / --m15-tail 默认一致
RADAR_OHLCV_TAIL_ROWS = {"1d": 1095, "1h": 2400, "15m": 960}


def apply_radar_ohlcv_tail(df: pd.DataFrame, timeframe: str) -> pd.DataFrame:
    """对齐雷达固化窗口，使 setup_key 中的 bar index 与监督重算一致。"""
    tf = str(timeframe or "1d").strip().lower()
    tail = RADAR_OHLCV_TAIL_ROWS.get(tf, 0)
    if tail <= 0 or len(df) <= tail:
        return df.reset_index(drop=True)
    return df.tail(tail).copy().reset_index(drop=True)


def parse_side(value: str | int | None) -> int | None:
    if value is None:
        return None
    if isinstance(value, int):
        return 1 if value > 0 else -1 if value < 0 else None
    text = str(value).strip().lower()
    if text in {"long", "buy", "1", "bull"}:
        return 1
    if text in {"short", "sell", "-1", "bear"}:
        return -1
    return None


def side_label(side: int) -> str:
    return "long" if side == 1 else "short"


def normalize_entry_date(value: Any) -> pd.Timestamp | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    text = str(value).strip()
    if not text:
        return None
    if " " in text:
        text = text.split(" ", 1)[0]
    try:
        return pd.to_datetime(text).normalize()
    except (TypeError, ValueError):
        return None


def infer_is_add(record: dict[str, Any]) -> bool:
    if record.get("is_add") is True:
        return True
    setup = str(record.get("setup", "")).lower()
    if "add" in setup or "续棍" in setup:
        return True
    risk = str(record.get("risk_rule", "")).lower()
    return "add" in risk


def _price_close(a: float, b: float, tol_ratio: float = 0.002) -> bool:
    tol = max(1e-6, abs(a) * tol_ratio)
    return abs(a - b) <= tol


DEFAULT_EXEC_GAP_FILE = "runtime/fill_exec_gap_acknowledged.json"


def load_exec_gap_order_ids(path: Path | str | None = None) -> set[str]:
    """已登记 EXEC_GAP 的 order_id（结构 valid、执行偏差，不计入 invalid_new）。"""
    if path is None:
        path = Path(DEFAULT_EXEC_GAP_FILE)
    else:
        path = Path(path)
    if not path.exists():
        return set()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return set()
    out: set[str] = set()
    if isinstance(payload, dict):
        for oid in payload.get("order_ids") or []:
            if oid:
                out.add(str(oid))
        for row in payload.get("entries") or []:
            if isinstance(row, dict) and row.get("order_id"):
                out.add(str(row["order_id"]))
    elif isinstance(payload, list):
        for item in payload:
            if isinstance(item, str):
                out.add(item)
            elif isinstance(item, dict) and item.get("order_id"):
                out.add(str(item["order_id"]))
    return out


def parse_signal_date_from_setup_key(setup_key: str) -> pd.Timestamp | None:
    match = re.search(r"signal=(\d{14})", str(setup_key))
    if not match:
        return None
    try:
        return pd.to_datetime(match.group(1), format="%Y%m%d%H%M%S")
    except (TypeError, ValueError):
        return None


def parse_trigger_from_setup_key(setup_key: str) -> float | None:
    match = re.search(r"trigger=([\d.eE+-]+)", str(setup_key))
    if not match:
        return None
    try:
        return float(match.group(1))
    except (TypeError, ValueError):
        return None


def resolve_ds01_pending_trigger(
    *,
    is_add: bool,
    trigger_calc: float,
    trigger_price: float | None,
    setup_key: str,
) -> float:
    """Pending fill audit trigger: add/续棍 uses order trigger, not stale signal-bar calc."""
    key_trigger = parse_trigger_from_setup_key(setup_key)
    if trigger_price is not None:
        tp = float(trigger_price)
        if is_add or not _price_close(trigger_calc, tp):
            return tp
    if key_trigger is not None and (is_add or not _price_close(trigger_calc, key_trigger)):
        return key_trigger
    return trigger_calc


def resolve_fill_entry_date(record: dict[str, Any]) -> Any:
    """Prefer explicit bar_time; else fill event time; else setup_key signal date."""
    for key in ("bar_time", "entry_date"):
        val = record.get(key)
        if val is not None and str(val).strip() and str(val).lower() != "none":
            return val
    fill_time = str(record.get("time", "")).strip()
    if fill_time:
        return fill_time
    signal = parse_signal_date_from_setup_key(str(record.get("setup_key", "")))
    if signal is not None:
        return signal + pd.Timedelta(days=1)
    return None


def find_bar_index_for_timestamp(os_df: pd.DataFrame, ts: pd.Timestamp) -> int | None:
    dates = pd.to_datetime(os_df["date"])
    exact = os_df.index[dates == ts]
    if len(exact) > 0:
        return int(exact[-1])
    day = ts.normalize()
    same_day = os_df.index[dates.dt.normalize() == day]
    if len(same_day) > 0:
        return int(same_day[-1])
    return None


def resolve_ds01_bar_indices(os_df: pd.DataFrame, record: dict[str, Any]) -> tuple[int, int, pd.Timestamp] | None:
    """Return (signal_idx, entry_idx, entry_day) for DS01 audit."""
    setup_key = str(record.get("setup_key", ""))
    signal_ts = parse_signal_date_from_setup_key(setup_key)
    if signal_ts is not None:
        signal_i = find_bar_index_for_timestamp(os_df, signal_ts)
        if signal_i is not None:
            entry_i = signal_i + 1
            if entry_i < len(os_df):
                entry_day = pd.to_datetime(os_df.iloc[entry_i]["date"]).normalize()
                return signal_i, entry_i, entry_day

    entry_day = normalize_entry_date(resolve_fill_entry_date(record))
    if entry_day is None:
        return None
    entry_i = find_entry_bar_index(os_df, entry_day)
    if entry_i is None or entry_i < 1:
        return None
    return entry_i - 1, entry_i, entry_day


def trigger_bar_fill_ok(record: dict[str, Any], side: int, trigger_price: float, cur: pd.Series) -> bool:
    """Use trigger-bar OHLC from fill event when fill came from intraday bar."""
    high = record.get("bar_high")
    low = record.get("bar_low")
    if high is None or low is None:
        return entry_fill(cur, side, trigger_price) is not None
    probe = pd.Series(
        {
            "open": record.get("bar_open", record.get("fill_price", cur.get("open"))),
            "high": float(high),
            "low": float(low),
            "close": record.get("fill_price", high if side == 1 else low),
        }
    )
    return entry_fill(probe, side, trigger_price) is not None


def find_entry_bar_index(os_df: pd.DataFrame, entry_date: pd.Timestamp) -> int | None:
    dates = pd.to_datetime(os_df["date"]).dt.normalize()
    matches = os_df.index[dates == entry_date]
    if len(matches) == 0:
        return None
    return int(matches[-1])


def _explicit_attack_bar_idx(record: dict[str, Any]) -> int | None:
    raw = record.get("attack_bar_idx")
    if raw is None:
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def _setup_snapshot_attack_idx(record: dict[str, Any]) -> int | None:
    reason = str(record.get("reason") or "")
    match = re.search(r"attack_idx=(\d+)", reason)
    if match:
        return int(match.group(1))
    setup_key = str(record.get("setup_key") or "")
    match = re.search(r"idx=(\d+)", setup_key)
    if match:
        return int(match.group(1))
    return None


def resolve_ds03_entry_bar_index(
    os_df: pd.DataFrame,
    entry_day: pd.Timestamp | None,
    record: dict[str, Any],
    fill_time: str,
) -> int | None:
    """Map DS03 entry to attack bar; tolerate D1 csv lag vs intraday fill_time."""
    # attack_bar_idx is relative to the OS tail at fill time; new D1 bars shift indices.
    # Prefer stable attack_bar_time for post-fill supervision replay.
    attack_time = str(record.get("attack_bar_time") or "").strip()
    if attack_time:
        hit = find_bar_index_for_fill_time(os_df, attack_time)
        if hit is not None:
            return hit

    explicit = _explicit_attack_bar_idx(record)
    if explicit is not None and 0 <= explicit < len(os_df):
        return explicit

    for candidate in (fill_time, record.get("bar_time"), record.get("time")):
        text = str(candidate or "").strip()
        if not text:
            continue
        hit = find_bar_index_for_fill_time(os_df, text)
        if hit is not None:
            return hit

    if entry_day is not None:
        hit = find_entry_bar_index(os_df, entry_day)
        if hit is not None:
            return hit

    setup_idx = _setup_snapshot_attack_idx(record)
    if setup_idx is not None and 0 <= setup_idx < len(os_df):
        return setup_idx
    return None


def infer_record_timeframe(record: dict[str, Any]) -> str:
    tf = str(record.get("timeframe") or "D1").strip().upper()
    if tf in {"H1", "1H", "60M"}:
        return "1h"
    if tf in {"M15", "15M"}:
        return "15m"
    return "1d"


def parse_ds07_setup_key(setup_key: str) -> dict[str, Any] | None:
    """INJUSDT|DS07|SHORT|CONT|attack=2392|defense=2395|trigger=4.15"""
    parts = str(setup_key).split("|")
    if len(parts) < 7 or parts[1].upper() != "DS07":
        return None
    side_text = parts[2].strip().upper()
    side = 1 if side_text == "LONG" else -1 if side_text == "SHORT" else None
    if side is None:
        return None
    attack_m = re.search(r"attack=(\d+)", setup_key)
    defense_m = re.search(r"defense=(\d+)", setup_key)
    trigger_m = re.search(r"trigger=([\d.eE+-]+)", setup_key)
    if not attack_m or not defense_m or not trigger_m:
        return None
    try:
        return {
            "side": side,
            "attack_idx": int(attack_m.group(1)),
            "defense_idx": int(defense_m.group(1)),
            "trigger_price": float(trigger_m.group(1)),
        }
    except (TypeError, ValueError):
        return None


def parse_ds05_setup_key(setup_key: str) -> dict[str, Any] | None:
    """PEPEUSDT|DS05|SHORT|k2=YYYYMMDDHHMMSS|k3=...|trigger=..."""
    parts = str(setup_key).split("|")
    if len(parts) < 6 or parts[1].upper() != "DS05":
        return None
    side_text = parts[2].strip().upper()
    side = 1 if side_text == "LONG" else -1 if side_text == "SHORT" else None
    if side is None:
        return None
    k2_m = re.search(r"k2=(\d{14})", setup_key)
    k3_m = re.search(r"k3=(\d{14})", setup_key)
    trigger_m = re.search(r"trigger=([\d.eE+-]+)", setup_key)
    if not k2_m or not k3_m or not trigger_m:
        return None
    try:
        return {
            "side": side,
            "k2_time": k2_m.group(1),
            "k3_time": k3_m.group(1),
            "trigger_price": float(trigger_m.group(1)),
        }
    except (TypeError, ValueError):
        return None


def compact_key_time_matches_bar(key_time: str, row: pd.Series) -> bool:
    try:
        key_ts = pd.to_datetime(str(key_time), format="%Y%m%d%H%M%S")
        row_ts = pd.to_datetime(row.get("date"))
    except (TypeError, ValueError):
        return False
    return key_ts.normalize() == row_ts.normalize()


def parse_ds08_setup_key(setup_key: str) -> dict[str, Any] | None:
    """Radar/setup_key: LONG|defense_v3|attack_p2|trigger  SHORT|defense_p3|attack_v2|trigger"""
    parts = str(setup_key).split("|")
    if len(parts) < 5:
        return None
    side_text = parts[1].strip().upper()
    side = 1 if side_text == "LONG" else -1 if side_text == "SHORT" else None
    if side is None:
        return None
    try:
        return {
            "side": side,
            "defense_idx": int(parts[2]),
            "attack_idx": int(parts[3]),
            "trigger_price": float(parts[4]),
        }
    except (TypeError, ValueError):
        return None


def pending_price_fill_ok(side: int, trigger: float, fill_price: float, tol_ratio: float = 0.002) -> bool:
    tol = max(1e-6, abs(trigger) * tol_ratio)
    if side == 1:
        return float(fill_price) >= float(trigger) - tol
    return float(fill_price) <= float(trigger) + tol


def resolve_setup_bar_index(record: dict[str, Any], os_df: pd.DataFrame, fill_time: str) -> int | None:
    latest = record.get("latest_time")
    if latest is not None and str(latest).strip():
        ts = pd.to_datetime(latest)
        i = find_bar_index_for_timestamp(os_df, ts)
        if i is not None:
            return i
    return find_bar_index_for_fill_time(os_df, fill_time or str(record.get("time", "")))



def validate_ds08_setup_from_key(
    df: pd.DataFrame,
    skeleton: list,
    i: int,
    parsed: dict[str, Any],
    side: int,
    symbol: str,
) -> tuple[list[str], dict[str, Any]]:
    """挂单成交监督：在 setup bar 用 last-5 硬化点核对结构/触发价；setup_key 索引仅作参考。"""
    issues: list[str] = []
    checks: dict[str, Any] = {"setup_bar_idx": i}
    trigger_key = float(parsed["trigger_price"])

    if i >= len(df) or len(skeleton) < 5:
        issues.append("insufficient hardened skeleton at setup bar")
        return issues, checks

    tail5 = sorted(skeleton[-5:], key=lambda node: (node.point_idx, node.confirm_idx))
    roles = [node_role(node) for node in tail5]
    checks["last5_roles"] = roles
    checks["last5_idx"] = [int(n.point_idx) for n in tail5]

    if side == 1:
        if roles != ["V", "P", "V", "P", "V"]:
            issues.append(f"last-5 skeleton roles {roles} != VPVPV for LONG")
            return issues, checks
        _v1, _p1, _v2, attack_node, defense_node = tail5
    else:
        if roles != ["P", "V", "P", "V", "P"]:
            issues.append(f"last-5 skeleton roles {roles} != PVPVP for SHORT")
            return issues, checks
        _p1, _v1, _p2, attack_node, defense_node = tail5

    attack_idx = int(attack_node.point_idx)
    defense_idx = int(defense_node.point_idx)
    trigger_calc = float(attack_node.price)
    stop_calc = float(defense_node.price)
    checks.update(
        {
            "attack_idx": attack_idx,
            "defense_idx": defense_idx,
            "trigger_calc": trigger_calc,
            "stop_calc": stop_calc,
            "attack_role": node_role(attack_node),
            "defense_role": node_role(defense_node),
        }
    )

    if not _price_close(trigger_calc, trigger_key, tol_ratio=0.01):
        issues.append(f"setup trigger mismatch last5={trigger_calc} key={trigger_key}")

    key_idx = (int(parsed["defense_idx"]), int(parsed["attack_idx"]))
    calc_idx = (defense_idx, attack_idx)
    if key_idx != calc_idx:
        checks["setup_key_idx_stale"] = {"key": key_idx, "setup_bar": calc_idx}

    expected_key = f"{symbol}|{'LONG' if side == 1 else 'SHORT'}|{defense_idx}|{attack_idx}|{trigger_calc:.10g}"
    checks["expected_setup_key"] = expected_key

    return issues, checks


def find_bar_index_for_fill_time(os_df: pd.DataFrame, fill_time: str) -> int | None:
    if not fill_time or not str(fill_time).strip():
        return None
    ts = pd.to_datetime(fill_time)
    dates = pd.to_datetime(os_df["date"])
    at_or_before = os_df.index[dates <= ts]
    if len(at_or_before) == 0:
        return None
    return int(at_or_before[-1])


def audit_ds03_fill(
    *,
    side: int,
    record: dict[str, Any],
    os_df: pd.DataFrame,
    symbol: str = "",
    order_id: str = "",
    setup_key: str = "",
    fill_time: str = "",
) -> FillAuditResult:
    entry_day = normalize_entry_date(resolve_fill_entry_date(record))
    base = FillAuditResult(
        strategy_id="DS03",
        symbol=symbol,
        side=side_label(side),
        entry_date=str(entry_day.date()) if entry_day is not None else "",
        verdict="needs-data",
        order_id=order_id,
        setup_key=setup_key,
        fill_time=fill_time,
    )
    if entry_day is None:
        base.issues.append("missing entry_date")
        return base
    i = resolve_ds03_entry_bar_index(os_df, entry_day, record, fill_time)
    if i is None:
        base.issues.append(f"entry date {entry_day.date()} not in D1 csv")
        return base
    entry_day = pd.to_datetime(os_df.iloc[i]["date"]).normalize()
    base.entry_date = str(entry_day.date())

    camp = int(os_df.iloc[i].get("camp", 0) or 0)
    camp_need = RED if side == 1 else BLUE
    trigger = record.get("trigger_price")
    stop = record.get("stop_price")
    issues: list[str] = []
    attack = resolve_ds03_attack(os_df, i)
    if camp != camp_need:
        issues.append(f"camp={camp} expected={camp_need}")
    if attack is None:
        issues.append("resolve_ds03_attack returned None on entry bar")
    else:
        if attack.side != side:
            issues.append(f"attack.side={attack.side} expected {side}")
        trig_calc = float(attack.entry_ref)
        if trigger is not None and not _price_close(trig_calc, float(trigger), tol_ratio=0.01):
            issues.append(f"trigger mismatch calc={trig_calc} fill={trigger}")
        signal = make_ds03_signal(os_df, i)
        checks: dict[str, Any] = {
            "entry_bar_idx": i,
            "camp": camp,
            "trigger_calc": trig_calc,
            "trigger_source": attack.trigger_source,
            "pattern": attack.pattern,
        }
        if signal is not None:
            expected_fill = float(ds03_entry_fill(os_df.iloc[i], signal))
            checks["entry_fill_calc"] = expected_fill
            fill_price = record.get("fill_price")
            if fill_price is not None and not _price_close(expected_fill, float(fill_price), tol_ratio=0.01):
                issues.append(f"fill_price mismatch entry_fill calc={expected_fill} got={fill_price}")
        base.checks = checks

    base.issues = issues
    base.verdict = "valid" if not issues else "invalid"
    if stop is not None and base.checks:
        base.checks["stop_fill"] = float(stop)
    return base


def audit_ds08_fill(
    *,
    side: int,
    record: dict[str, Any],
    os_df: pd.DataFrame,
    engine: FengJiOSIdentityEngine,
    symbol: str = "",
    order_id: str = "",
    setup_key: str = "",
    fill_time: str = "",
) -> FillAuditResult:
    parsed = parse_ds08_setup_key(setup_key)
    base = FillAuditResult(
        strategy_id="DS08",
        symbol=symbol,
        side=side_label(side),
        entry_date=str(record.get("latest_time") or record.get("bar_time") or fill_time or ""),
        verdict="needs-data",
        order_id=order_id,
        setup_key=setup_key,
        fill_time=fill_time,
    )
    if parsed is None:
        base.issues.append("unparseable DS08 setup_key")
        return base

    if order_id and order_id in load_exec_gap_order_ids():
        base.verdict = "exec_gap"
        base.issues = ["EXEC_GAP acknowledged (legacy execution vs entry_fill)"]
        return base

    i = resolve_setup_bar_index(record, os_df, fill_time)
    if i is None:
        base.issues.append("setup/latest_time not mappable to H1 bar index")
        return base

    skeleton = engine.hardened_by_bar[i] if i < len(engine.hardened_by_bar) else []
    trigger = record.get("trigger_price")
    stop = record.get("stop_price")
    fill_price = record.get("fill_price")
    issues: list[str] = []

    if parsed["side"] != side:
        issues.append(f"setup side={parsed['side']} fill side={side}")

    static_issues, base.checks = validate_ds08_setup_from_key(
        os_df, skeleton, i, parsed, side, symbol=symbol.split("|")[0] if "|" in symbol else symbol
    )
    issues.extend(static_issues)

    sym_clean = str(symbol).split("|")[0] if "|" in str(symbol) else str(symbol)
    signal = make_ds08_signal(os_df, i, skeleton, set(), symbol=sym_clean)
    if signal is not None:
        base.checks["signal_key"] = signal.key
        base.checks["pattern"] = signal.pattern
        if signal.side != side:
            issues.append(f"signal.side={signal.side} expected {side}")
        if not _price_close(signal.entry_ref, parsed["trigger_price"], tol_ratio=0.01):
            issues.append(f"live signal trigger mismatch calc={signal.entry_ref} key={parsed['trigger_price']}")
        if trigger is not None and not _price_close(signal.entry_ref, float(trigger), tol_ratio=0.01):
            issues.append(f"trigger mismatch calc={signal.entry_ref} fill={trigger}")
        if stop is not None and not _price_close(signal.initial_stop, float(stop), tol_ratio=0.01):
            issues.append(f"stop mismatch calc={signal.initial_stop} fill={stop}")
        row = os_df.iloc[i]
        entry_fill_calc = float(ds08_entry_fill(row, signal))
        base.checks["entry_fill_calc"] = entry_fill_calc
        price_source = str(record.get("price_source") or "").strip().lower()
        if fill_price is not None:
            if price_source == "ds08_entry_fill":
                if not _price_close(entry_fill_calc, float(fill_price), tol_ratio=0.01):
                    issues.append(
                        f"fill_price mismatch entry_fill calc={entry_fill_calc} got={fill_price}"
                    )
    elif stop is not None and base.checks.get("stop_calc") is not None:
        if not _price_close(float(base.checks["stop_calc"]), float(stop), tol_ratio=0.01):
            issues.append(f"stop mismatch calc={base.checks['stop_calc']} fill={stop}")

    if fill_price is not None and trigger is not None:
        trig = float(trigger)
        if not pending_price_fill_ok(side, trig, float(fill_price)):
            issues.append(f"fill_price={fill_price} does not satisfy trigger={trig} for pending fill")
        elif base.checks:
            base.checks["pending_fill_ok"] = True

    stale_key = base.checks.get("setup_key_idx_stale")
    if stale_key and base.checks.get("pending_fill_ok"):
        hard = [x for x in issues if "roles" in x or "skeleton" in x or "unparseable" in x]
        if not hard:
            base.issues = [
                f"DS08 setup_key stale key={stale_key.get('key')} setup_bar={stale_key.get('setup_bar')}; pending fill OK"
            ]
            base.verdict = "skipped"
            return base

    if (
        signal is not None
        and fill_price is not None
        and base.checks.get("entry_fill_calc") is not None
        and not issues
    ):
        ef = float(base.checks["entry_fill_calc"])
        price_source = str(record.get("price_source") or "").strip().lower()
        if price_source != "ds08_entry_fill" and not _price_close(ef, float(fill_price), tol_ratio=0.01):
            base.issues = [
                f"DS08 exec gap: entry_fill={ef} fill={fill_price} source={price_source or 'binance'}"
            ]
            base.verdict = "exec_gap"
            return base

    base.issues = issues
    base.verdict = "valid" if not issues else "invalid"
    return base


def audit_ds05_fill(
    *,
    side: int,
    record: dict[str, Any],
    os_df: pd.DataFrame,
    symbol: str = "",
    order_id: str = "",
    setup_key: str = "",
    fill_time: str = "",
) -> FillAuditResult:
    parsed = parse_ds05_setup_key(setup_key)
    base = FillAuditResult(
        strategy_id="DS05",
        symbol=symbol,
        side=side_label(side),
        entry_date=str(record.get("latest_time") or record.get("bar_time") or fill_time or ""),
        verdict="needs-data",
        order_id=order_id,
        setup_key=setup_key,
        fill_time=fill_time,
    )
    if parsed is None:
        base.issues.append("unparseable DS05 setup_key")
        return base
    if parsed["side"] != side:
        base.issues.append(f"setup side={parsed['side']} fill side={side}")
        return base

    i = resolve_setup_bar_index(record, os_df, fill_time)
    if i is None:
        base.issues.append("setup/latest_time not mappable to D1 bar index")
        return base

    signal = make_ds05_signal(os_df, i)
    issues: list[str] = []
    checks: dict[str, Any] = {"setup_bar_idx": i}
    if i < len(os_df):
        checks["setup_bar_date"] = str(os_df.iloc[i].get("date"))
    checks["setup_key_k2"] = parsed["k2_time"]
    checks["setup_key_k3"] = parsed["k3_time"]
    if signal is None:
        issues.append("make_ds05_signal returned None at setup bar")
    else:
        checks.update(
            {
                "signal_side": signal.side,
                "entry_calc": float(signal.entry_price),
                "stop_calc": float(signal.initial_stop),
                "k1": signal.k1,
                "k2": signal.k2,
                "k3": signal.k3,
            }
        )
        if signal.side != side:
            issues.append(f"signal.side={signal.side} expected {side}")
        if not _price_close(signal.entry_price, parsed["trigger_price"], tol_ratio=0.01):
            issues.append(f"trigger mismatch calc={signal.entry_price} key={parsed['trigger_price']}")
        trigger = record.get("trigger_price")
        stop = record.get("stop_price")
        if trigger is not None and not _price_close(signal.entry_price, float(trigger), tol_ratio=0.01):
            issues.append(f"trigger mismatch calc={signal.entry_price} fill={trigger}")
        if stop is not None and not _price_close(signal.initial_stop, float(stop), tol_ratio=0.01):
            issues.append(f"stop mismatch calc={signal.initial_stop} fill={stop}")

    fill_price = record.get("fill_price")
    trigger = record.get("trigger_price") or (signal.entry_price if signal else parsed["trigger_price"])
    if fill_price is not None and trigger is not None:
        if not pending_price_fill_ok(side, float(trigger), float(fill_price)):
            issues.append(f"fill_price={fill_price} does not satisfy trigger={trigger}")
        else:
            checks["pending_fill_ok"] = True

    if signal is None and checks.get("pending_fill_ok") and i < len(os_df):
        if compact_key_time_matches_bar(parsed["k3_time"], os_df.iloc[i]):
            base.checks = checks
            base.issues = [
                "DS05 setup not reproducible from final D1 bar; pending fill OK"
            ]
            base.verdict = "skipped"
            return base

    base.checks = checks
    base.issues = issues
    base.verdict = "valid" if not issues else "invalid"
    return base


def audit_ds07_fill(
    *,
    side: int,
    record: dict[str, Any],
    h1_os_df: pd.DataFrame,
    d1_os_df: pd.DataFrame,
    symbol: str = "",
    order_id: str = "",
    setup_key: str = "",
    fill_time: str = "",
    market: str = "crypto",
) -> FillAuditResult:
    parsed = parse_ds07_setup_key(setup_key)
    base = FillAuditResult(
        strategy_id="DS07",
        symbol=symbol,
        side=side_label(side),
        entry_date=str(record.get("latest_time") or record.get("bar_time") or fill_time or ""),
        verdict="needs-data",
        order_id=order_id,
        setup_key=setup_key,
        fill_time=fill_time,
    )
    if parsed is None:
        base.issues.append("unparseable DS07 setup_key")
        return base
    if parsed["side"] != side:
        base.issues.append(f"setup side={parsed['side']} fill side={side}")
        return base
    if d1_os_df is None or d1_os_df.empty or h1_os_df is None or h1_os_df.empty:
        base.issues.append("missing D1/H1 OS frame for DS07")
        return base

    if market in {"domestic", "futures"}:
        from fengji_core.ds07 import map_d1_to_h1_natural_day

        mapped = map_d1_to_h1_natural_day(d1_os_df, h1_os_df)
    else:
        mapped = map_d1_to_h1_future(d1_os_df, h1_os_df)
    if len(mapped) < 2:
        base.issues.append("insufficient mapped H1 rows for DS07")
        return base

    i = resolve_setup_bar_index(record, mapped, fill_time)
    if i is None:
        i = len(mapped) - 1
    if i < 1:
        base.issues.append("setup bar too early for DS07")
        return base

    cur = mapped.iloc[i]
    prev = mapped.iloc[i - 1]
    sym_clean = str(symbol).upper().replace("USDT", "")
    signal = make_ds07_signal(cur, i, set(), symbol=sym_clean, prev_row=prev, df=mapped)
    issues: list[str] = []
    checks: dict[str, Any] = {"setup_bar_idx": i}
    if signal is None:
        issues.append("make_ds07_signal returned None at setup bar")
    else:
        checks.update(
            {
                "attack_idx": int(signal.attack_idx),
                "defense_idx": int(signal.defense_idx),
                "entry_calc": float(signal.entry_ref),
                "stop_calc": float(signal.initial_stop),
                "attack_key": signal.attack_key,
            }
        )
        if signal.side != side:
            issues.append(f"signal.side={signal.side} expected {side}")
        key_idx = (parsed["attack_idx"], parsed["defense_idx"])
        calc_idx = (int(signal.attack_idx), int(signal.defense_idx))
        if key_idx != calc_idx:
            checks["setup_key_idx_stale"] = {"key": key_idx, "setup_bar": calc_idx}
        if not _price_close(signal.entry_ref, parsed["trigger_price"], tol_ratio=0.01):
            issues.append(f"trigger mismatch calc={signal.entry_ref} key={parsed['trigger_price']}")
        trigger = record.get("trigger_price")
        stop = record.get("stop_price")
        if trigger is not None and not _price_close(signal.entry_ref, float(trigger), tol_ratio=0.01):
            issues.append(f"trigger mismatch calc={signal.entry_ref} fill={trigger}")
        if stop is not None and not _price_close(signal.initial_stop, float(stop), tol_ratio=0.01):
            issues.append(f"stop mismatch calc={signal.initial_stop} fill={stop}")

    fill_price = record.get("fill_price")
    trigger = record.get("trigger_price") or parsed["trigger_price"]
    if fill_price is not None and trigger is not None:
        if not pending_price_fill_ok(side, float(trigger), float(fill_price)):
            issues.append(f"fill_price={fill_price} does not satisfy trigger={trigger}")
        elif checks:
            checks["pending_fill_ok"] = True

    stale_key = checks.get("setup_key_idx_stale")
    if stale_key and checks.get("pending_fill_ok"):
        hard = [x for x in issues if "signal.side" in x or "unparseable" in x or "missing" in x]
        if not hard:
            base.checks = checks
            base.issues = [
                f"DS07 setup_key stale key={stale_key.get('key')} setup_bar={stale_key.get('setup_bar')}; pending fill OK"
            ]
            base.verdict = "skipped"
            return base

    base.checks = checks
    base.issues = issues
    base.verdict = "valid" if not issues else "invalid"
    return base


def audit_ds01_fill(
    *,
    side: int,
    entry_date: Any,
    trigger_price: float | None,
    stop_price: float | None,
    left_count: int | None,
    os_df: pd.DataFrame,
    engine: FengJiOSIdentityEngine,
    is_add: bool = False,
    fill_price: float | None = None,
    symbol: str = "",
    order_id: str = "",
    setup_key: str = "",
    fill_time: str = "",
    record: dict[str, Any] | None = None,
) -> FillAuditResult:
    """Re-audit one DS01 open using prev-bar OS camp (aligned with radar add_ds01)."""
    indices = resolve_ds01_bar_indices(os_df, record or {"setup_key": setup_key, "bar_time": entry_date}) if record or setup_key else None
    if indices is not None:
        signal_i, i, entry_day = indices
    else:
        entry_day = normalize_entry_date(entry_date)
        signal_i = None
        i = None

    base = FillAuditResult(
        strategy_id="DS01",
        symbol=symbol,
        side=side_label(side),
        entry_date=str(entry_day.date()) if entry_day is not None else str(entry_date),
        verdict="needs-data",
        order_id=order_id,
        setup_key=setup_key,
        fill_time=fill_time,
    )
    if entry_day is None:
        base.issues.append("missing entry_date")
        return base

    if i is None:
        i = find_entry_bar_index(os_df, entry_day)
    if i is None:
        base.issues.append(f"entry date {entry_day.date()} not in D1 csv")
        return base
    if i < 1:
        base.verdict = "invalid"
        base.issues.append("no previous bar for signal stick")
        return base

    if signal_i is None:
        signal_i = i - 1
    prev = os_df.iloc[signal_i]
    cur = os_df.iloc[i]
    camp = int(prev.get("camp", 0) or 0)
    camp_need = RED if side == 1 else BLUE
    trigger_calc = float(prev["high"] if side == 1 else prev["low"])
    stop_calc = float(prev["low"] if side == 1 else prev["high"])
    visible = engine.hardened_by_bar[max(0, i - 1)] if engine.hardened_by_bar else []

    if side == 1:
        left_price = float(cur["high"]) if float(cur["high"]) >= trigger_calc else trigger_calc
    else:
        left_price = float(cur["low"]) if float(cur["low"]) <= trigger_calc else trigger_calc
    left_ok, left_count_calc = ds01_left_filter_pass(visible, i, left_price, is_add)
    rec = record or {}
    pending_trigger = resolve_ds01_pending_trigger(
        is_add=is_add,
        trigger_calc=trigger_calc,
        trigger_price=float(trigger_price) if trigger_price is not None else None,
        setup_key=setup_key,
    )
    fill_ok = trigger_bar_fill_ok(rec, side, pending_trigger, cur)
    if not fill_ok and fill_price is not None:
        fill_ok = pending_price_fill_ok(side, pending_trigger, float(fill_price))

    issues: list[str] = []
    if camp != camp_need:
        issues.append(f"signal_camp={camp} expected={camp_need}")
    if ds01_os_defense_missing(camp, prev):
        issues.append("os_defense_missing_on_signal_bar")
    if side == 1 and not (float(prev["close"]) > float(prev["open"])):
        issues.append("signal bar not bullish")
    if side == -1 and not (float(prev["close"]) < float(prev["open"])):
        issues.append("signal bar not bearish")
    if not fill_ok:
        issues.append("entry_fill=False on entry bar OHLC")
    if not is_add and not left_ok:
        issues.append(f"left30 fail count={left_count_calc}")
    if trigger_price is not None and not is_add and not _price_close(trigger_calc, float(trigger_price), tol_ratio=0.01):
        issues.append(f"trigger mismatch calc={trigger_calc} fill={trigger_price}")
    if is_add and trigger_price is not None and not _price_close(pending_trigger, float(trigger_price), tol_ratio=0.01):
        issues.append(f"add trigger mismatch pending={pending_trigger} fill={trigger_price}")
    if stop_price is not None and not is_add and not _price_close(stop_calc, float(stop_price), tol_ratio=0.01):
        issues.append(f"stop mismatch calc={stop_calc} fill={stop_price}")
    if left_count is not None and not is_add and int(left_count) != left_count_calc:
        issues.append(f"left_count mismatch fill={left_count} calc={left_count_calc}")

    base.checks = {
        "entry_bar_idx": i,
        "signal_bar_idx": signal_i,
        "signal_date": str(prev["date"]),
        "signal_camp": camp,
        "trigger_calc": trigger_calc,
        "stop_calc": stop_calc,
        "left_price": left_price,
        "left_count_calc": left_count_calc,
        "left_ok": left_ok,
        "fill_ok": fill_ok,
        "pending_trigger": pending_trigger,
        "is_add": is_add,
        "fill_price": fill_price,
        "trigger_bar_timeframe": rec.get("timeframe") or rec.get("bar", {}).get("timeframe") if isinstance(rec.get("bar"), dict) else rec.get("timeframe"),
    }
    base.issues = issues
    base.verdict = "valid" if not issues else "invalid"
    return base


def audit_fill_record(
    record: dict[str, Any],
    os_df: pd.DataFrame,
    engine: FengJiOSIdentityEngine,
    *,
    d1_os_df: pd.DataFrame | None = None,
    market: str = "crypto",
) -> FillAuditResult:
    strategy = str(record.get("strategy_id", record.get("strategy", ""))).upper()
    symbol = str(record.get("symbol", ""))
    order_id = str(record.get("order_id", ""))
    setup_key = str(record.get("setup_key", ""))
    fill_time = str(record.get("time", ""))

    if strategy == "DS03":
        side = parse_side(record.get("side"))
        if side is None:
            return FillAuditResult(
                strategy_id="DS03",
                symbol=symbol,
                side=str(record.get("side", "")),
                entry_date=str(record.get("bar_time", "")),
                verdict="needs-data",
                issues=["unrecognized side"],
                order_id=order_id,
                setup_key=setup_key,
                fill_time=fill_time,
            )
        legacy_ps = str(record.get("price_source") or "").strip()
        setup_key_str = str(record.get("setup_key") or "")
        if legacy_ps == "ds03_intraday_breakout":
            return FillAuditResult(
                strategy_id="DS03",
                symbol=symbol,
                side=side_label(side),
                entry_date=str(record.get("bar_time", "")),
                verdict="skipped",
                issues=["ds03 intraday watch execution (not attack-bar entry_fill)"],
                order_id=order_id,
                setup_key=setup_key,
                fill_time=fill_time,
            )
        if legacy_ps != "ds03_attack_bar" and _explicit_attack_bar_idx(record) is None:
            return FillAuditResult(
                strategy_id="DS03",
                symbol=symbol,
                side=side_label(side),
                entry_date=str(record.get("bar_time", "")),
                verdict="skipped",
                issues=[f"legacy DS03 execution price_source={legacy_ps or 'unknown'} (pre attack-bar deploy)"],
                order_id=order_id,
                setup_key=setup_key,
                fill_time=fill_time,
            )
        if is_ds03_watch_setup_key(setup_key_str) and legacy_ps != "ds03_attack_bar":
            return FillAuditResult(
                strategy_id="DS03",
                symbol=symbol,
                side=side_label(side),
                entry_date=str(record.get("bar_time", "")),
                verdict="skipped",
                issues=[f"DS03 watch execution price_source={legacy_ps or 'unknown'} (not attack-bar entry_fill)"],
                order_id=order_id,
                setup_key=setup_key,
                fill_time=fill_time,
            )
        if is_ds03_watch_setup_key(setup_key_str):
            entry_day = normalize_entry_date(resolve_fill_entry_date(record))
            if entry_day is not None:
                idx = resolve_ds03_entry_bar_index(os_df, entry_day, record, fill_time)
                if idx is not None:
                    attack = resolve_ds03_attack(os_df, idx)
                    trig = record.get("trigger_price")
                    if attack is not None and trig is not None and not _price_close(
                        float(attack.entry_ref), float(trig)
                    ):
                        return FillAuditResult(
                            strategy_id="DS03",
                            symbol=symbol,
                            side=side_label(side),
                            entry_date=str(entry_day.date()),
                            verdict="skipped",
                            issues=["DS03 watch trigger stale vs attack-bar entry_ref (non attack-bar fill)"],
                            order_id=order_id,
                            setup_key=setup_key,
                            fill_time=fill_time,
                        )
        return audit_ds03_fill(
            side=side,
            record=record,
            os_df=os_df,
            symbol=symbol,
            order_id=order_id,
            setup_key=setup_key,
            fill_time=fill_time,
        )

    if strategy == "DS08":
        side = parse_side(record.get("side"))
        if side is None:
            return FillAuditResult(
                strategy_id="DS08",
                symbol=symbol,
                side=str(record.get("side", "")),
                entry_date=str(record.get("bar_time", "")),
                verdict="needs-data",
                issues=["unrecognized side"],
                order_id=order_id,
                setup_key=setup_key,
                fill_time=fill_time,
            )
        return audit_ds08_fill(
            side=side,
            record=record,
            os_df=os_df,
            engine=engine,
            symbol=symbol,
            order_id=order_id,
            setup_key=setup_key,
            fill_time=fill_time,
        )

    if strategy == "DS05":
        side = parse_side(record.get("side"))
        if side is None:
            return FillAuditResult(
                strategy_id="DS05",
                symbol=symbol,
                side=str(record.get("side", "")),
                entry_date=str(record.get("bar_time", "")),
                verdict="needs-data",
                issues=["unrecognized side"],
                order_id=order_id,
                setup_key=setup_key,
                fill_time=fill_time,
            )
        return audit_ds05_fill(
            side=side,
            record=record,
            os_df=os_df,
            symbol=symbol,
            order_id=order_id,
            setup_key=setup_key,
            fill_time=fill_time,
        )

    if strategy == "DS07":
        side = parse_side(record.get("side"))
        if side is None:
            return FillAuditResult(
                strategy_id="DS07",
                symbol=symbol,
                side=str(record.get("side", "")),
                entry_date=str(record.get("bar_time", "")),
                verdict="needs-data",
                issues=["unrecognized side"],
                order_id=order_id,
                setup_key=setup_key,
                fill_time=fill_time,
            )
        return audit_ds07_fill(
            side=side,
            record=record,
            h1_os_df=os_df,
            d1_os_df=d1_os_df,
            symbol=symbol,
            order_id=order_id,
            setup_key=setup_key,
            fill_time=fill_time,
            market=market,
        )

    if strategy != "DS01":
        return FillAuditResult(
            strategy_id=strategy or "UNKNOWN",
            symbol=symbol,
            side=str(record.get("side", "")),
            entry_date=str(record.get("bar_time", record.get("entry_date", ""))),
            verdict="skipped",
            issues=[f"supervision not implemented for {strategy}"],
            order_id=order_id,
            setup_key=setup_key,
            fill_time=fill_time,
        )

    side = parse_side(record.get("side"))
    if side is None:
        return FillAuditResult(
            strategy_id="DS01",
            symbol=symbol,
            side=str(record.get("side", "")),
            entry_date=str(record.get("bar_time", "")),
            verdict="needs-data",
            issues=["unrecognized side"],
            order_id=order_id,
            setup_key=setup_key,
            fill_time=fill_time,
        )

    entry_date = resolve_fill_entry_date(record)
    trigger = record.get("trigger_price")
    stop = record.get("stop_price")
    left = record.get("left_count")
    fill_price = record.get("fill_price")

    return audit_ds01_fill(
        side=side,
        entry_date=entry_date,
        trigger_price=float(trigger) if trigger is not None else None,
        stop_price=float(stop) if stop is not None else None,
        left_count=int(left) if left is not None and str(left) != "" else None,
        os_df=os_df,
        engine=engine,
        is_add=infer_is_add(record),
        fill_price=float(fill_price) if fill_price is not None else None,
        symbol=symbol,
        order_id=order_id,
        setup_key=setup_key,
        fill_time=fill_time,
        record=record,
    )


def load_d1_csv(path: str | Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    if "timestamp" in df.columns and "date" not in df.columns:
        df = df.rename(columns={"timestamp": "date"})
    df["date"] = pd.to_datetime(df["date"])
    return df.sort_values("date").reset_index(drop=True)


_D1_FOLDER_PRIORITY = {"overseas_1d": 0, "1d": 1, "futures_1d": 1, "crypto_okx": 2}


def _d1_csv_last_bar(path: Path) -> datetime | None:
    try:
        df = pd.read_csv(path)
    except (OSError, pd.errors.EmptyDataError, ValueError):
        return None
    if df.empty:
        return None
    col = "date" if "date" in df.columns else ("timestamp" if "timestamp" in df.columns else df.columns[0])
    series = pd.to_datetime(df[col], errors="coerce")
    last = series.max()
    if pd.isna(last):
        return None
    ts = pd.Timestamp(last)
    return ts.to_pydatetime()


def _pick_freshest_csv(candidates: list[Path]) -> Path | None:
    """Prefer the CSV whose last bar is newest; tie-break by folder priority (live 1d > legacy okx)."""
    existing = [p for p in candidates if p.is_file()]
    if not existing:
        return None
    best: Path | None = None
    best_last = datetime.min
    best_pri = 999
    for path in existing:
        last = _d1_csv_last_bar(path) or datetime.min
        pri = _D1_FOLDER_PRIORITY.get(path.parent.name, 50)
        if last > best_last or (last == best_last and pri < best_pri):
            best, best_last, best_pri = path, last, pri
    return best


def resolve_ohlcv_csv(data_dir: Path, symbol: str, timeframe: str, market: str = "auto") -> Path | None:
    tf = timeframe.strip().lower()
    if tf == "1d":
        return resolve_d1_csv(data_dir, symbol, market=market)
    root = Path(data_dir)
    sym = str(symbol).upper()
    base = sym.replace("USDT", "")
    folders = ("1h", "h1", "60m") if tf == "1h" else ("15m", "m15")
    if market in {"auto", "futures", "domestic"}:
        for folder in folders:
            sub = root / folder
            if not sub.is_dir():
                continue
            for name in (f"{sym}.csv", f"{base}.csv"):
                path = sub / name
                if path.exists():
                    return path
    if market in {"auto", "crypto", "overseas"}:
        for folder in folders:
            sub = root / folder
            if not sub.is_dir():
                continue
            for name in (f"{sym}.csv", f"{base}USDT.csv", f"{base}-USDT.csv"):
                path = sub / name
                if path.exists():
                    return path
    if market in {"auto", "a_stock", "domestic"}:
        code = sym.zfill(6) if sym.isdigit() else sym
        for name in (f"{code}_60m_qfq.csv", f"{code}_1H_qfq.csv"):
            path = root / "a_stock" / name
            if path.exists():
                return path
    if market in {"auto", "us_stock"}:
        for name in (f"{sym}_1H.csv", f"{sym}_1h.csv"):
            path = root / "us_stock" / name
            if path.exists():
                return path
    return None


def resolve_d1_csv(data_dir: Path, symbol: str, market: str = "auto") -> Path | None:
    root = Path(data_dir)
    sym = str(symbol).upper()
    base = sym.replace("USDT", "")
    candidates: list[Path] = []

    if market in {"auto", "futures", "domestic"}:
        for folder in ("1d", "futures_1d"):
            candidates.append(root / folder / f"{sym}.csv")
            candidates.append(root / folder / f"{base}.csv")

    if market in {"auto", "a_stock"}:
        candidates.append(root / "a_stock" / f"{sym}_1D_qfq.csv")
        candidates.append(root / "a_stock" / f"{sym.zfill(6)}_1D_qfq.csv")

    if market in {"auto", "crypto", "overseas"}:
        for folder in ("overseas_1d", "1d", "crypto_okx"):
            candidates.extend(
                [
                    root / folder / f"{sym}.csv",
                    root / folder / f"{base}-USDT_1D_1825d.csv",
                    root / folder / f"{base}-USDT_1D_180d.csv",
                    root / folder / f"{base}USDT.csv",
                ]
            )

    return _pick_freshest_csv(candidates)


def parse_events_jsonl(path: Path, since_hours: float | None = None) -> list[dict[str, Any]]:
    file_path = Path(path)
    if not file_path.exists():
        return []

    cutoff: datetime | None = None
    if since_hours is not None and since_hours > 0:
        cutoff = datetime.now() - pd.Timedelta(hours=since_hours).to_pytimedelta()

    fills: list[dict[str, Any]] = []
    with file_path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(row, dict):
                continue
            if str(row.get("event_type", "")).lower() != "fill":
                continue
            if cutoff is not None:
                ttext = str(row.get("time", ""))
                try:
                    ts = datetime.strptime(ttext, "%Y-%m-%d %H:%M:%S")
                except ValueError:
                    ts = None
                if ts is not None and ts < cutoff:
                    continue
            fills.append(row)
    return fills
