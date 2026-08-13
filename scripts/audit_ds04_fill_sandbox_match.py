#!/usr/bin/env python3
"""Audit DS04 fill rows that cannot be matched back to sandbox trade_no.

This is a read-only diagnostics script. It does not alter DS04 rules; it
compares runtime fill metadata with the existing DS04 backtest/plotter surface.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
for search_path in (ROOT / "src", ROOT / "packages" / "fengji_core"):
    if str(search_path) not in sys.path:
        sys.path.insert(0, str(search_path))

import pandas as pd

from backtest_ds04 import DS04BacktestConfig, run_ds04_backtest
from fengji_core.ds04 import k2_is_weakest, make_ds04_signal, no_price_gap
from quant.data import load_ohlcv_for_engine
from quant.futures_specs import get_futures_spec


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8-sig"))


def parse_setup_dates(setup_key: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for key, raw in re.findall(r"(k[1-4])=(\d{14})", setup_key, flags=re.IGNORECASE):
        values[key.lower()] = f"{raw[:4]}-{raw[4:6]}-{raw[6:8]} {raw[8:10]}:{raw[10:12]}:{raw[12:14]}"
    return values


def resolve_csv(data_dir: Path, symbol: str) -> Path:
    candidates = [
        data_dir / "1d" / f"{symbol}.csv",
        data_dir / "1d" / f"{symbol.replace('USDT', '')}.csv",
        data_dir / "d1" / f"{symbol}.csv",
    ]
    for path in candidates:
        if path.exists():
            return path
    return candidates[0]


def find_idx_by_date(df: pd.DataFrame, when: str) -> int | None:
    if not when:
        return None
    target = pd.to_datetime(when)
    dates = pd.to_datetime(df["date"])
    hits = df.index[dates == target].tolist()
    if not hits:
        hits = df.index[dates.dt.normalize() == target.normalize()].tolist()
    return int(hits[-1]) if hits else None


def describe_k_window(os_df: pd.DataFrame, dates: dict[str, str]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for label in ("k1", "k2", "k3", "k4"):
        idx = find_idx_by_date(os_df, dates.get(label, ""))
        if idx is None:
            rows.append({"label": label.upper(), "idx": None, "date": dates.get(label, ""), "missing": True})
            continue
        row = os_df.iloc[idx]
        rows.append(
            {
                "label": label.upper(),
                "idx": idx,
                "date": str(row["date"]),
                "open": float(row["open"]),
                "high": float(row["high"]),
                "low": float(row["low"]),
                "close": float(row["close"]),
                "camp": int(row.get("camp", 0) or 0),
                "body": abs(float(row["close"]) - float(row["open"])),
                "range": float(row["high"]) - float(row["low"]),
            }
        )
    return rows


def evaluate_setup(os_df: pd.DataFrame, dates: dict[str, str]) -> dict[str, Any]:
    k3_idx = find_idx_by_date(os_df, dates.get("k3", ""))
    if k3_idx is None:
        return {"status": "missing_k3"}
    result: dict[str, Any] = {"k3_idx": k3_idx}
    if k3_idx < 3 or k3_idx + 1 >= len(os_df):
        result["status"] = "out_of_range"
        return result
    k1_idx = k3_idx - 2
    k2_idx = k3_idx - 1
    result.update({"derived_k1_idx": k1_idx, "derived_k2_idx": k2_idx})
    result["gap_prev_k1_ok"] = no_price_gap(os_df, k1_idx - 1, k1_idx)
    result["gap_k1_k2_ok"] = no_price_gap(os_df, k1_idx, k2_idx)
    result["gap_k2_k3_ok"] = no_price_gap(os_df, k2_idx, k3_idx)
    result["k2_weakest"] = k2_is_weakest(os_df, k1_idx, k2_idx, k3_idx)
    signal = make_ds04_signal(os_df, k3_idx)
    result["signal"] = signal.to_dict() if signal is not None else None
    result["status"] = "signal" if signal is not None else "no_signal"
    return result


def nearest_trades(trades: pd.DataFrame, *, side: str, fill_price: float, when: str) -> list[dict[str, Any]]:
    if trades.empty:
        return []
    candidates = trades.copy()
    if "direction" in candidates.columns:
        candidates = candidates[candidates["direction"].astype(str).str.lower() == side]
    if candidates.empty:
        return []
    target = pd.to_datetime(when) if when else None
    out: list[tuple[float, dict[str, Any]]] = []
    for _, trade in candidates.iterrows():
        price_score = abs(float(trade.get("entry_price", 0.0) or 0.0) - fill_price) / max(abs(fill_price), 1.0)
        date_score = 0.0
        if target is not None:
            entry = pd.to_datetime(trade.get("entry_date"))
            date_score = min(abs((entry.normalize() - target.normalize()).days), 30) * 0.01
        row = {
            "trade_no": int(trade["trade_no"]),
            "direction": str(trade["direction"]),
            "entry_date": str(trade["entry_date"]),
            "entry_price": float(trade["entry_price"]),
            "initial_stop": float(trade["initial_stop"]),
            "k1": int(trade["k1"]),
            "k2": int(trade["k2"]),
            "k3": int(trade["k3"]),
            "reclaim_price": float(trade["reclaim_price"]),
            "score": round(price_score + date_score, 8),
        }
        out.append((price_score + date_score, row))
    out.sort(key=lambda item: item[0])
    return [row for _, row in out[:5]]


def audit_task(task: dict[str, Any], *, data_dir: Path) -> dict[str, Any]:
    symbol = str(task.get("symbol") or "").upper()
    csv_path = resolve_csv(data_dir, symbol)
    report: dict[str, Any] = {
        "symbol": symbol,
        "order_id": task.get("order_id"),
        "setup_key": task.get("setup_key"),
        "fill_price": task.get("fill_price"),
        "trigger_price": task.get("trigger_price"),
        "stop_price": task.get("stop_price"),
        "event_time": task.get("event_time"),
        "csv": str(csv_path),
        "csv_exists": csv_path.exists(),
    }
    if not csv_path.exists():
        report["verdict"] = "missing_csv"
        return report
    config = DS04BacktestConfig(futures_mode=True, spec=get_futures_spec(csv_path))
    raw_df = load_ohlcv_for_engine(csv_path, config.atr_window)
    result = run_ds04_backtest(raw_df, config)
    os_df = result["df"]
    trades = result["trades"]
    dates = parse_setup_dates(str(task.get("setup_key") or ""))
    report["setup_dates"] = dates
    report["k_window"] = describe_k_window(os_df, dates)
    report["setup_eval"] = evaluate_setup(os_df, dates)
    report["trade_count"] = int(len(trades))
    try:
        fill = float(task.get("fill_price") or task.get("trigger_price"))
    except (TypeError, ValueError):
        fill = 0.0
    report["nearest_trades"] = nearest_trades(trades, side=str(task.get("side") or "").lower(), fill_price=fill, when=str(task.get("event_time") or ""))
    if report["setup_eval"].get("signal") is None:
        report["verdict"] = "runtime_setup_not_replayable_as_ds04_signal"
    elif not report["nearest_trades"]:
        report["verdict"] = "signal_exists_but_no_closed_trade"
    else:
        report["verdict"] = "nearest_trade_outside_match_tolerance"
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit DS04 fill sandbox no_backtest_trade rows.")
    parser.add_argument("--review-json", default="runtime/fill_sandbox_review/fill_sandbox_review.json")
    parser.add_argument("--data-dir", default="data")
    parser.add_argument("--out", default="")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    review = load_json(Path(args.review_json), {"tasks": []})
    tasks = [
        task
        for task in review.get("tasks", [])
        if str(task.get("strategy_id", "")).upper() == "DS04" and task.get("status") in {"no_backtest_trade", "ready", "generated", "failed"}
    ]
    reports = [audit_task(task, data_dir=Path(args.data_dir)) for task in tasks]
    payload = {"count": len(reports), "reports": reports}
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text, encoding="utf-8")
        print(f"saved={out} count={len(reports)}")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
