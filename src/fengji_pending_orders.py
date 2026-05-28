from __future__ import annotations

import argparse
import hashlib
import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import pandas as pd


ACTIONABLE_STATUSES = {"PENDING"}
DEFAULT_INCLUDE_STRATEGIES = {"DS01", "DS03", "DS04", "DS05", "DS07", "DS08", "DS09"}
DEFAULT_STRATEGY_PRIORITY = {
    "DS01": 10,
    "DS02": 20,
    "DS03": 30,
    "DS04": 40,
    "DS05": 50,
    "DS06": 60,
    "DS07": 70,
    "DS08": 80,
    "DS09": 90,
}


@dataclass
class PendingOrder:
    order_id: str
    symbol: str
    strategy_id: str
    timeframe: str
    side: str
    trigger_price: float
    stop_price: float | None
    current_price: float
    distance_pct: float
    status: str
    radar_status: str
    setup: str
    os_camp: str
    latest_time: str
    created_at: str
    valid_until: str
    priority: float
    reason: str
    setup_key: str


def now_text() -> str:
    return pd.Timestamp.now(tz="Asia/Shanghai").strftime("%Y-%m-%d %H:%M:%S")


def safe_float(value: Any) -> float | None:
    try:
        out = float(value)
    except Exception:
        return None
    if math.isnan(out):
        return None
    return out


def normalize_symbol(symbol: str) -> str:
    text = str(symbol).strip().upper().replace("-", "").replace("_", "")
    return text if text.endswith("USDT") else f"{text}USDT"


def parse_set(value: str) -> set[str]:
    return {item.strip().upper() for item in value.split(",") if item.strip()}


def read_radar(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(f"radar file not found: {path}")
    if path.suffix.lower() == ".json":
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, list):
            raise ValueError(f"radar json must be a list: {path}")
        return [item for item in payload if isinstance(item, dict)]
    frame = pd.read_csv(path)
    return frame.to_dict("records")


def order_id_for(row: dict[str, Any]) -> str:
    setup_identity = str(row.get("setup_key", "") or row.get("latest_time", ""))
    parts = [
        normalize_symbol(str(row.get("symbol", ""))),
        str(row.get("strategy_id", "")).upper(),
        str(row.get("timeframe", "")).upper(),
        str(row.get("side", "")).lower(),
        f"{safe_float(row.get('trigger_price')) or 0.0:.12g}",
        f"{safe_float(row.get('stop_price')) or 0.0:.12g}",
        setup_identity,
    ]
    digest = hashlib.sha1("|".join(parts).encode("utf-8")).hexdigest()[:16]
    return "-".join(parts[:4] + [digest]).replace(" ", "")


def default_valid_until(latest_time: Any, timeframe: str, *, anchor_time: str | None = None) -> str:
    """挂单有效期以雷达刷新时刻为锚，避免 K 线停更导致 valid_until 立刻过期。"""
    ts = pd.to_datetime(anchor_time or latest_time, errors="coerce")
    if pd.isna(ts):
        ts = pd.Timestamp.now(tz="Asia/Shanghai").tz_localize(None)
    tf = str(timeframe).upper()
    if tf in {"D1", "1D", "DAY", "DAILY"}:
        return str((ts + pd.Timedelta(days=2)).strftime("%Y-%m-%d %H:%M:%S"))
    if tf in {"H1", "1H", "60M", "60MIN"}:
        return str((ts + pd.Timedelta(hours=6)).strftime("%Y-%m-%d %H:%M:%S"))
    return str((ts + pd.Timedelta(hours=12)).strftime("%Y-%m-%d %H:%M:%S"))


def distance_for(side: str, current: float, trigger: float) -> float:
    if current <= 0:
        return math.nan
    if side == "long":
        return (trigger - current) / current
    return (current - trigger) / current


def convert_radar_rows(
    radar_rows: list[dict[str, Any]],
    *,
    include_strategies: set[str],
    include_triggered: bool,
    max_distance_pct: float,
    created_at: str | None = None,
    consumed_ds03_setup_keys: set[str] | None = None,
) -> list[PendingOrder]:
    created = created_at or now_text()
    statuses = set(ACTIONABLE_STATUSES)
    if include_triggered:
        statuses.add("TRIGGERED")

    orders: list[PendingOrder] = []
    for row in radar_rows:
        strategy_id = str(row.get("strategy_id", "")).upper()
        radar_status = str(row.get("status", "")).upper()
        side = str(row.get("side", "")).lower()
        setup_key = str(row.get("setup_key", "") or "")
        if (
            strategy_id == "DS03"
            and setup_key
            and consumed_ds03_setup_keys
            and setup_key in consumed_ds03_setup_keys
        ):
            continue
        trigger = safe_float(row.get("trigger_price"))
        current = safe_float(row.get("current_price"))
        stop = safe_float(row.get("stop_price"))
        if strategy_id not in include_strategies:
            continue
        if radar_status not in statuses:
            continue
        if side not in {"long", "short"} or trigger is None or current is None or trigger <= 0:
            continue
        dist = safe_float(row.get("distance_pct"))
        if dist is None or math.isnan(dist):
            dist = distance_for(side, current, trigger)
        if radar_status == "PENDING" and max_distance_pct >= 0 and dist > max_distance_pct:
            continue
        status = "ACTIVE" if radar_status == "PENDING" else "READY_TRIGGERED"
        base_priority = DEFAULT_STRATEGY_PRIORITY.get(strategy_id, 999)
        distance_priority = 0.0 if radar_status == "TRIGGERED" else max(dist, 0.0) * 100
        priority = base_priority + distance_priority
        orders.append(
            PendingOrder(
                order_id=order_id_for(row),
                symbol=normalize_symbol(str(row.get("symbol", ""))),
                strategy_id=strategy_id,
                timeframe=str(row.get("timeframe", "")).upper(),
                side=side,
                trigger_price=float(trigger),
                stop_price=None if stop is None else float(stop),
                current_price=float(current),
                distance_pct=float(dist),
                status=status,
                radar_status=radar_status,
                setup=str(row.get("setup", "")),
                os_camp=str(row.get("os_camp", "")),
                latest_time=str(row.get("latest_time", "")),
                created_at=created,
                valid_until=default_valid_until(
                    row.get("latest_time", ""),
                    str(row.get("timeframe", "")),
                    anchor_time=created,
                ),
                priority=float(priority),
                reason=str(row.get("reason", "")),
                setup_key=setup_key,
            )
        )
    return sorted(orders, key=lambda item: (item.priority, item.symbol, item.strategy_id, item.side))


def write_orders(orders: list[PendingOrder], out_dir: Path) -> tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    payload = [asdict(order) for order in orders]
    json_path = out_dir / "pending_orders.json"
    csv_path = out_dir / "pending_orders.csv"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    pd.DataFrame(payload).to_csv(csv_path, index=False, encoding="utf-8-sig")
    return json_path, csv_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build actionable FengJi pending trigger orders from radar output.")
    parser.add_argument("--radar", default="runtime/fengji_radar/radar.json")
    parser.add_argument("--out-dir", default="runtime/fengji_pending_orders")
    parser.add_argument("--strategies", default=",".join(sorted(DEFAULT_INCLUDE_STRATEGIES)))
    parser.add_argument("--include-triggered", action="store_true", help="Also export current-bar triggered radar rows.")
    parser.add_argument("--max-distance-pct", type=float, default=0.08, help="Ignore pending rows farther than this ratio; use -1 to disable.")
    parser.add_argument(
        "--monitor-state",
        default="",
        help="Optional pending monitor state JSON; DS03 rows with filled/consumed setup_key are skipped.",
    )
    return parser.parse_args()


def load_consumed_ds03_setup_keys(state_path: Path) -> set[str]:
    if not state_path.exists():
        return set()
    payload = json.loads(state_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        return set()
    keys: set[str] = set()
    for key in payload.get("filled_setup_keys", []) or []:
        text = str(key).strip()
        if text:
            keys.add(text)
    for key in payload.get("consumed_ds03_setup_keys", []) or []:
        text = str(key).strip()
        if text:
            keys.add(text)
    return keys


def main() -> None:
    args = parse_args()
    radar_rows = read_radar(Path(args.radar))
    consumed: set[str] = set()
    if args.monitor_state:
        consumed = load_consumed_ds03_setup_keys(Path(args.monitor_state))
    orders = convert_radar_rows(
        radar_rows,
        include_strategies=parse_set(args.strategies),
        include_triggered=bool(args.include_triggered),
        max_distance_pct=float(args.max_distance_pct),
        consumed_ds03_setup_keys=consumed,
    )
    json_path, csv_path = write_orders(orders, Path(args.out_dir))
    if orders:
        frame = pd.DataFrame([asdict(order) for order in orders])
        print(frame[["symbol", "strategy_id", "timeframe", "side", "status", "trigger_price", "current_price", "distance_pct", "stop_price", "priority"]].to_string(index=False))
    else:
        print("No actionable pending orders.")
    print(f"Saved: {json_path}")
    print(f"Saved: {csv_path}")


if __name__ == "__main__":
    main()
