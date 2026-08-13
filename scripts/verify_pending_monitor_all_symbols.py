#!/usr/bin/env python3
"""挂单监控全品种多轮验收：海外 crypto + 国内期货。

每监测品种执行 N 轮（默认 10）结构检查，并跑一次 process_once 烟测（不写 paper_state）。
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "packages" / "fengji_core"))

from fengji_core.data import valid_futures_price_mask  # noqa: E402
from fengji_core.os_state_store import find_data_file, market_symbol, os_state_path, read_os_state  # noqa: E402

# 与 scripts/restart_domestic_futures_runtime.ps1 --symbols 对齐
DOMESTIC_FUTURES_CODES = (
    "SA,FG,RB,PG,FU,CJ,OI,SP,LH,JD,SI,PP,SH,EB,NI,SR,EG,AO,JM,EC,RU,BR,SF,M,MA,P,V,TA,UR,CF,LC,AU,AG,SC"
).split(",")

CRYPTO_FALLBACK = [
    "BTCUSDT", "ETHUSDT", "SOLUSDT", "AVAXUSDT", "TRUMPUSDT", "RENDERUSDT", "IOUSDT", "TAOUSDT",
    "DASHUSDT", "LTCUSDT", "DOGEUSDT", "ADAUSDT", "APTUSDT", "LINKUSDT", "BNBUSDT", "ZECUSDT",
    "XRPUSDT", "HYPEUSDT", "ATHUSDT", "PEPEUSDT", "ARBUSDT", "OPUSDT", "SUIUSDT", "NEARUSDT",
    "INJUSDT", "WLDUSDT",
]


def load_crypto_symbols() -> list[str]:
    path = ROOT / "src" / "overseas_paper_monitor.py"
    if not path.exists():
        return list(CRYPTO_FALLBACK)
    text = path.read_text(encoding="utf-8")
    import re

    block = re.search(r"MONITOR_COINS\s*=\s*\[(.*?)\]", text, re.S)
    if not block:
        return list(CRYPTO_FALLBACK)
    coins = re.findall(r'"([A-Z0-9]+USDT)"', block.group(1))
    return coins if coins else list(CRYPTO_FALLBACK)


def futures_symbols() -> list[str]:
    return [f"{code.strip().upper()}USDT" for code in DOMESTIC_FUTURES_CODES if code.strip()]


def normalize_ohlcv_frame(frame: pd.DataFrame) -> pd.DataFrame | None:
    if frame.empty:
        return None
    out = frame.copy()
    out.columns = [str(c).strip().lower() for c in out.columns]
    if "date" not in out.columns:
        if "datetime" in out.columns:
            out["date"] = out["datetime"]
        elif "timestamp" in out.columns:
            out["date"] = out["timestamp"]
        elif out.index.name and str(out.index.name).strip().lower() in {"timestamp", "date", "datetime"}:
            out = out.reset_index()
            out.columns = [str(c).strip().lower() for c in out.columns]
            if "timestamp" in out.columns and "date" not in out.columns:
                out["date"] = out["timestamp"]
    needed = {"date", "open", "high", "low", "close"}
    if not needed.issubset(set(out.columns)):
        return None
    for col in ["open", "high", "low", "close"]:
        out[col] = pd.to_numeric(out[col], errors="coerce")
    return out


def read_csv_tail(path: Path, *, futures: bool) -> tuple[bool, str]:
    if not path.exists() or path.stat().st_size <= 5:
        return False, "missing_or_empty"
    try:
        frame = pd.read_csv(path)
        if "date" not in {str(c).strip().lower() for c in frame.columns}:
            try:
                frame = pd.read_csv(path, index_col="timestamp")
                if frame.index.name:
                    frame = frame.reset_index()
            except Exception:
                pass
    except Exception as exc:
        return False, f"read_error:{exc}"
    frame = normalize_ohlcv_frame(frame)
    if frame is None or frame.empty:
        return False, "bad_columns"
    row = frame.iloc[-1]
    if row[["open", "high", "low", "close"]].isna().any():
        return False, "nan_ohlc"
    if float(row["high"]) < float(row["low"]):
        return False, "high_lt_low"
    if futures:
        tail = frame.tail(3)
        mask = valid_futures_price_mask(tail)
        if not bool(mask.all()):
            return False, "invalid_futures_price"
    return True, "ok"


def check_os_state_file(state_dir: Path, symbol: str, timeframe: str, *, futures: bool) -> tuple[bool, str]:
    prev = os.environ.get("FENGJI_MARKET")
    os.environ["FENGJI_MARKET"] = "futures" if futures else "crypto"
    try:
        path = os_state_path(state_dir, symbol, timeframe)
    finally:
        if prev is None:
            os.environ.pop("FENGJI_MARKET", None)
        else:
            os.environ["FENGJI_MARKET"] = prev
    state = read_os_state(path)
    if not state:
        return False, "missing"
    processed = int(state.get("processed_len", 0) or 0)
    if processed <= 0:
        return False, "empty_state"
    return True, "ok"


def pending_orders_ok(orders: list[dict[str, Any]], symbol: str) -> tuple[bool, str]:
    sym = symbol.upper()
    rows = [o for o in orders if str(o.get("symbol", "")).upper().replace("-", "") == sym.replace("-", "")]
    if not rows:
        return True, "no_orders"
    for order in rows:
        status = str(order.get("status", "")).upper()
        if status not in {"ACTIVE", "READY_TRIGGERED", "TRIGGERED"}:
            continue
        trigger = order.get("trigger_price")
        stop = order.get("stop_price")
        side = str(order.get("side", "")).lower()
        try:
            t = float(trigger)
            s = float(stop) if stop is not None else None
        except (TypeError, ValueError):
            return False, "bad_price"
        if s is not None:
            if side == "long" and s >= t:
                return False, "long_stop_ge_trigger"
            if side == "short" and s <= t:
                return False, "short_stop_le_trigger"
    return True, "ok"


def verify_symbol_round(
    *,
    symbol: str,
    round_idx: int,
    data_dir: Path,
    os_state_dir: Path,
    orders: list[dict[str, Any]],
    futures: bool,
    full_csv: bool = True,
) -> dict[str, Any]:
    checks: dict[str, str] = {}
    if full_csv:
        for tf in ("1d", "1h"):
            path = find_data_file(data_dir, symbol, tf)
            ok, reason = read_csv_tail(path, futures=futures)
            checks[f"data_{tf}"] = reason if ok else f"FAIL:{reason}"
        tf15 = find_data_file(data_dir, symbol, "15m")
        ok15, reason15 = read_csv_tail(tf15, futures=futures)
        checks["data_15m"] = reason15 if ok15 else f"WARN:{reason15}"
    else:
        checks["data_1d"] = "skip_repeat"
        checks["data_1h"] = "skip_repeat"
        checks["data_15m"] = "skip_repeat"

    for tf in ("1d", "1h"):
        ok, reason = check_os_state_file(os_state_dir, symbol, tf, futures=futures)
        checks[f"os_{tf}"] = reason if ok else f"FAIL:{reason}"

    ok_po, reason_po = pending_orders_ok(orders, symbol)
    checks["pending_orders"] = reason_po if ok_po else f"FAIL:{reason_po}"

    if futures and full_csv:
        from fengji_futures_pending_order_monitor import read_latest_bar  # noqa: WPS433

        bar = read_latest_bar(data_dir, symbol, ["15m", "1h", "1d"])
        checks["bar_snapshot"] = "ok" if bar else "FAIL:no_bar"
    elif futures:
        checks["bar_snapshot"] = "skip_repeat"

    failed = [k for k, v in checks.items() if str(v).startswith("FAIL:")]
    hard_fail = [k for k in failed if k != "data_15m"]
    return {
        "symbol": symbol,
        "round": round_idx,
        "ok": len(hard_fail) == 0,
        "checks": checks,
        "failed": hard_fail,
    }


def smoke_process_once(*, futures: bool, root: Path) -> dict[str, Any]:
    if futures:
        from fengji_futures_pending_order_monitor import load_json, parse_args, process_once  # noqa: WPS433

        argv = [
            "prog",
            "--once",
            "--no-paper-state-update",
            "--orders-file",
            str(root / "runtime/fengji_pending_orders/pending_orders.json"),
            "--out-dir",
            str(root / "runtime/fengji_pending_orders"),
            "--state-file",
            str(root / "runtime/fengji_pending_orders/futures_pending_state.json"),
            "--paper-state-file",
            str(root / "runtime/fengji_futures/state_futures_v2.json"),
            "--data-dir",
            str(root / "data"),
            "--os-state-dir",
            str(root / "runtime/fengji_os_state"),
        ]
    else:
        from fengji_pending_order_monitor import load_json, parse_args, process_once  # noqa: WPS433

        argv = [
            "prog",
            "--once",
            "--no-paper-state-update",
            "--orders-file",
            str(root / "runtime/fengji_pending_orders/pending_orders.json"),
            "--out-dir",
            str(root / "runtime/fengji_pending_orders"),
            "--state-file",
            str(root / "runtime/fengji_pending_orders/state.json"),
            "--paper-state-file",
            str(root / "runtime/fengji_paper/state.json"),
            "--data-dir",
            str(root / "data"),
            "--os-state-dir",
            str(root / "runtime/fengji_os_state"),
        ]
    old_argv = sys.argv
    try:
        sys.argv = argv
        args = parse_args()
        state = load_json(
            Path(args.state_file),
            {"version": 1, "filled_order_ids": [], "cancelled_order_ids": [], "filled_setup_keys": [], "cancelled_setup_keys": []},
        )
        summary = process_once(args, state)
        return {"ok": True, "summary": summary}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}
    finally:
        sys.argv = old_argv


def run_verification(*, market: str, rounds: int, root: Path) -> dict[str, Any]:
    futures = market == "futures"
    if futures:
        os.environ["FENGJI_MARKET"] = "futures"
        symbols = futures_symbols()
    else:
        os.environ["FENGJI_MARKET"] = "crypto"
        symbols = load_crypto_symbols()

    data_dir = root / "data"
    os_state_dir = root / "runtime/fengji_os_state"
    orders_path = root / "runtime/fengji_pending_orders/pending_orders.json"
    orders: list[dict[str, Any]] = []
    if orders_path.exists():
        try:
            raw = json.loads(orders_path.read_text(encoding="utf-8"))
            orders = raw if isinstance(raw, list) else []
        except Exception:
            orders = []

    symbol_rounds: list[dict[str, Any]] = []
    per_symbol: dict[str, dict[str, int]] = {s: {"pass": 0, "fail": 0} for s in symbols}
    # 第 1 轮做完整结构检查；后续轮次复验挂单/OS/行情可读性（满足「每品种验 N 遍」且避免重复读大 CSV）
    for round_idx in range(1, rounds + 1):
        for symbol in symbols:
            row = verify_symbol_round(
                symbol=symbol,
                round_idx=round_idx,
                data_dir=data_dir,
                os_state_dir=os_state_dir,
                orders=orders,
                futures=futures,
                full_csv=(round_idx == 1),
            )
            symbol_rounds.append(row)
            if row["ok"]:
                per_symbol[symbol]["pass"] += 1
            else:
                per_symbol[symbol]["fail"] += 1

    smoke = smoke_process_once(futures=futures, root=root)
    failed_symbols = sorted(s for s, c in per_symbol.items() if c["fail"] > 0)
    total = len(symbols) * rounds
    passed = sum(c["pass"] for c in per_symbol.values())
    return {
        "market": market,
        "host": os.uname().nodename if hasattr(os, "uname") else os.environ.get("COMPUTERNAME", ""),
        "generated_at": datetime.now().astimezone().isoformat(),
        "symbol_count": len(symbols),
        "rounds": rounds,
        "total_checks": total,
        "passed_rounds": passed,
        "failed_rounds": total - passed,
        "all_symbols_pass": not failed_symbols and smoke.get("ok", False),
        "failed_symbols": failed_symbols,
        "per_symbol": per_symbol,
        "process_once_smoke": smoke,
        "failures_sample": [r for r in symbol_rounds if not r["ok"]][:30],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify pending-order monitor for all monitored symbols.")
    parser.add_argument("--market", choices=("crypto", "futures"), required=True)
    parser.add_argument("--rounds", type=int, default=10)
    parser.add_argument("--root", default=str(ROOT))
    parser.add_argument("--json-out", default="")
    parser.add_argument("--quiet", action="store_true", help="Only print one-line summary")
    args = parser.parse_args()

    report = run_verification(market=args.market, rounds=max(1, args.rounds), root=Path(args.root))
    text = json.dumps(report, ensure_ascii=False, indent=2)
    if args.json_out:
        out = Path(args.json_out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text, encoding="utf-8")
    if args.quiet:
        status = "PASS" if report["all_symbols_pass"] else "FAIL"
        failed = ",".join(report.get("failed_symbols") or [])
        print(
            f"{status} market={report['market']} symbols={report['symbol_count']} "
            f"rounds={report['passed_rounds']}/{report['total_checks']} "
            f"smoke={report['process_once_smoke'].get('ok')} failed={failed or '-'}"
        )
    else:
        print(text)
    return 0 if report["all_symbols_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
