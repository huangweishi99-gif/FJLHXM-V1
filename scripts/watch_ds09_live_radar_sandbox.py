"""Watch crypto radar for new DS09 rows and emit session sandbox charts (read-only)."""
from __future__ import annotations

import argparse
import json
import sys
from argparse import Namespace
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "packages" / "fengji_core"))
sys.path.insert(0, str(ROOT / "scripts"))

from fengji_total_radar import RadarRow, analyze_symbol, discover_futures_symbols, normalize_symbol  # noqa: E402
from run_crypto_ds09_sandbox_review import analyze_symbol as sandbox_analyze_symbol  # noqa: E402


DEFAULT_STATE = ROOT / "runtime" / "ds09_live_watch_state.json"
DEFAULT_OUT = ROOT / "results" / "ds09_live_watch"


def row_fingerprint(row: RadarRow) -> str:
    key = (row.setup_key or "").strip()
    if key:
        return f"{row.symbol}|DS09|{key}"
    return f"{row.symbol}|DS09|{row.side}|{row.status}|{row.trigger_price:.10g}"


def load_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"seen": [], "events": []}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"seen": [], "events": []}
    data.setdefault("seen", [])
    data.setdefault("events", [])
    return data


def save_state(path: Path, state: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def discover_crypto_symbols(data_dir: Path) -> list[str]:
    symbols: set[str] = set()
    for sub in ("overseas_1d", "1d"):
        d = data_dir / sub
        if not d.is_dir():
            continue
        for path in d.glob("*.csv"):
            stem = path.stem.strip().upper()
            if stem.endswith("USDT"):
                symbols.add(stem)
    return sorted(symbols)


def resolve_symbols(args: argparse.Namespace, data_dir: Path) -> list[str]:
    explicit = [normalize_symbol(s) for s in str(args.symbols or "").split(",") if s.strip()]
    if explicit:
        return explicit
    if args.market == "futures":
        return [normalize_symbol(s) for s in discover_futures_symbols(data_dir)]
    return discover_crypto_symbols(data_dir)


def scan_ds09_rows(data_dir: Path, symbol: str, radar_args: Namespace) -> list[RadarRow]:
    rows = analyze_symbol(data_dir, symbol, radar_args)
    return [r for r in rows if r.strategy_id == "DS09"]


def pick_new_rows(ds09_rows: list[RadarRow], seen: set[str]) -> list[tuple[str, RadarRow]]:
    out: list[tuple[str, RadarRow]] = []
    for row in ds09_rows:
        fp = row_fingerprint(row)
        if fp in seen:
            continue
        out.append((fp, row))
    return out


def radar_row_summary(row: RadarRow) -> dict[str, Any]:
    return {
        "symbol": row.symbol,
        "side": row.side,
        "status": row.status,
        "trigger_price": row.trigger_price,
        "stop_price": row.stop_price,
        "setup": row.setup,
        "setup_key": row.setup_key,
        "latest_time": str(row.latest_time),
        "reason": row.reason,
    }


def emit_sandbox(symbol: str, args: argparse.Namespace, out_dir: Path) -> dict[str, Any]:
    review_args = Namespace(
        data_dir=args.data_dir,
        os_state_dir=args.os_state_dir,
        daily_tail=args.daily_tail,
        m15_tail=args.m15_tail,
        out_dir=str(out_dir),
    )
    return sandbox_analyze_symbol(symbol, review_args)


def main() -> int:
    parser = argparse.ArgumentParser(description="Watch radar for new DS09 rows and plot sandbox charts.")
    parser.add_argument("--data-dir", default="data")
    parser.add_argument("--os-state-dir", default="runtime/fengji_os_state")
    parser.add_argument("--symbols", default="", help="Comma-separated symbols; empty = auto discover")
    parser.add_argument("--market", choices=("crypto", "futures"), default="crypto")
    parser.add_argument("--daily-tail", type=int, default=400)
    parser.add_argument("--h1-tail", type=int, default=2400)
    parser.add_argument("--m15-tail", type=int, default=960)
    parser.add_argument("--state-file", default=str(DEFAULT_STATE))
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT))
    parser.add_argument("--once", action="store_true", help="Single scan then exit (for scheduled tasks)")
    parser.add_argument("--dry-run", action="store_true", help="Detect only; do not plot or persist state")
    parser.add_argument("--reset-state", action="store_true", help="Clear seen fingerprints before scan")
    args = parser.parse_args()

    data_dir = Path(args.data_dir)
    out_dir = Path(args.out_dir)
    state_path = Path(args.state_file)
    out_dir.mkdir(parents=True, exist_ok=True)

    state = {"seen": [], "events": []} if args.reset_state else load_state(state_path)
    seen = set(str(x) for x in state.get("seen", []))

    radar_args = Namespace(
        atr_window=14,
        gap=3,
        daily_tail=args.daily_tail,
        h1_tail=args.h1_tail,
        m15_tail=args.m15_tail,
        os_state_dir=args.os_state_dir,
        extreme_atr_tol=0.80,
    )

    symbols = resolve_symbols(args, data_dir)
    if not symbols:
        print("WATCH_DS09_NO_SYMBOLS")
        return 1

    run_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    new_events: list[dict[str, Any]] = []
    total_new = 0

    for symbol in symbols:
        try:
            ds09_rows = scan_ds09_rows(data_dir, symbol, radar_args)
        except Exception as exc:
            print(f"SCAN_FAIL {symbol}: {exc}")
            continue

        for fp, row in pick_new_rows(ds09_rows, seen):
            total_new += 1
            event: dict[str, Any] = {
                "at": run_at,
                "fingerprint": fp,
                "radar": radar_row_summary(row),
                "sandbox": None,
                "png": None,
            }
            print(f"NEW_DS09 {symbol} {row.side} {row.status} fp={fp}")

            if not args.dry_run:
                try:
                    sandbox = emit_sandbox(symbol, args, out_dir)
                    event["sandbox"] = {k: sandbox.get(k) for k in (
                        "symbol", "latest_session", "latest_stage", "latest_pierce",
                        "session_png", "lock_session_png", "backtest_trades", "error",
                    )}
                    event["png"] = sandbox.get("session_png") or sandbox.get("lock_session_png")
                    if event["png"]:
                        print(f"  PNG {event['png']}")
                except Exception as exc:
                    event["sandbox"] = {"error": str(exc)}
                    print(f"  SANDBOX_FAIL {exc}")

                seen.add(fp)
                state.setdefault("events", []).append(event)
                new_events.append(event)

    if not args.dry_run:
        state["seen"] = sorted(seen)
        state["last_run"] = run_at
        state["last_new_count"] = total_new
        save_state(state_path, state)
        log_path = out_dir / f"watch_run_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        log_path.write_text(
            json.dumps({"run_at": run_at, "symbols": symbols, "new_count": total_new, "events": new_events}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    print(f"WATCH_DS09_DONE symbols={len(symbols)} new={total_new} dry_run={args.dry_run}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
