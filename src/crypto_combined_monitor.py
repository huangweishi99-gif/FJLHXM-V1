from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from batch_unified_crypto_whitelist import fetch_okx_history, read_symbols
from unified_whitelist_engine import FENGJI_TOTAL_PATTERN_STRATEGIES, UnifiedConfig, run_unified_symbol


ALL_STRATEGIES = FENGJI_TOTAL_PATTERN_STRATEGIES


def safe_read(path: Path) -> pd.DataFrame:
    if not path.exists() or path.stat().st_size <= 5:
        return pd.DataFrame()
    try:
        return pd.read_csv(path)
    except pd.errors.EmptyDataError:
        return pd.DataFrame()


def latest_signals(symbol_dir: Path, lookback_hours: int, reference_time: pd.Timestamp) -> pd.DataFrame:
    accepted = safe_read(symbol_dir / "accepted_trades.csv")
    if accepted.empty or pd.isna(reference_time):
        return pd.DataFrame()
    accepted["entry_time"] = pd.to_datetime(accepted["entry_time"], errors="coerce")
    start = reference_time - pd.Timedelta(hours=lookback_hours)
    return accepted[accepted["entry_time"] >= start].copy()


def monitor_symbol(symbol: str, args: argparse.Namespace, run_root: Path) -> list[dict]:
    name = symbol.replace("-USDT", "")
    cache_root = Path(args.cache_dir)
    daily_csv = cache_root / f"{symbol}_1D_{args.days}d.csv"
    h1_csv = cache_root / f"{symbol}_1H_{args.days}d.csv"
    m15_csv = cache_root / f"{symbol}_15m_{args.days}d.csv"

    should_refresh = not args.use_cache
    fetch_okx_history(symbol, "1Dutc", args.days, daily_csv, args.atr_window, should_refresh)
    fetch_okx_history(symbol, "1H", args.days, h1_csv, args.atr_window, should_refresh)
    fetch_okx_history(symbol, "15m", args.days, m15_csv, args.atr_window, should_refresh)

    config = UnifiedConfig(
        initial_cash=args.initial_cash,
        lots=1,
        commission_rate=0.0,
        slippage_ticks=0.0,
        atr_window=args.atr_window,
        gap=args.gap,
        max_same_direction_entries=args.max_same_direction_entries,
        futures_mode=False,
        spec=None,
    )
    symbol_dir = run_root / symbol
    summary = run_unified_symbol(name, config, daily_csv, h1_csv, m15_csv, ALL_STRATEGIES, symbol_dir)

    h1_frame = pd.read_csv(h1_csv, usecols=["date"])
    reference_time = pd.to_datetime(h1_frame["date"], errors="coerce").max()
    signals = latest_signals(symbol_dir, args.lookback_hours, reference_time)
    checked_at = pd.Timestamp.now(tz="Asia/Shanghai").isoformat()

    base = {
        "checked_at": checked_at,
        "symbol": symbol,
        "auto_trade": "DISABLED",
        "strategies": ",".join(ALL_STRATEGIES),
        "lookback_hours": args.lookback_hours,
        "reference_time": "" if pd.isna(reference_time) else str(reference_time),
        "candidates": summary["candidates"],
        "accepted_total": summary["accepted"],
        "rejected_total": summary["rejected"],
        "bad_audits": summary["bad_audits"],
        "out_dir": str(symbol_dir),
    }
    if signals.empty:
        return [
            {
                **base,
                "decision": "NO_SIGNAL",
                "entry_time": "",
                "strategy_id": "",
                "direction": "",
                "entry_price": "",
                "initial_stop": "",
                "current_stop": "",
                "pattern": "",
            }
        ]

    rows: list[dict] = []
    for _, signal in signals.sort_values(["entry_time", "strategy_priority"]).iterrows():
        rows.append(
            {
                **base,
                "decision": "COMBINED_SIGNAL_OBSERVE_ONLY",
                "entry_time": signal.get("entry_time", ""),
                "strategy_id": signal.get("strategy_id", ""),
                "direction": signal.get("direction", ""),
                "entry_price": signal.get("entry_price", ""),
                "initial_stop": signal.get("initial_stop", ""),
                "current_stop": signal.get("current_stop", ""),
                "pattern": signal.get("pattern", ""),
            }
        )
    return rows


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="FengJi Total Pattern DS01-DS09 crypto monitor. Observation only; no live orders.")
    parser.add_argument("--symbols", required=True, help="Comma-separated symbols, DEFAULT, or a text file.")
    parser.add_argument("--out-dir", default="results/crypto_combined_monitor")
    parser.add_argument("--cache-dir", default="data/crypto_okx")
    parser.add_argument("--days", type=int, default=180)
    parser.add_argument("--lookback-hours", type=int, default=24)
    parser.add_argument("--initial-cash", type=float, default=1000.0)
    parser.add_argument("--atr-window", type=int, default=14)
    parser.add_argument("--gap", type=int, default=3)
    parser.add_argument("--max-same-direction-entries", type=int, default=3)
    parser.add_argument("--use-cache", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    symbols = read_symbols(args.symbols)
    run_root = Path(args.out_dir) / pd.Timestamp.now(tz="Asia/Shanghai").strftime("%Y%m%d_%H%M%S")
    run_root.mkdir(parents=True, exist_ok=True)

    rows: list[dict] = []
    for symbol in symbols:
        try:
            rows.extend(monitor_symbol(symbol, args, run_root))
        except Exception as exc:
            rows.append(
                {
                    "checked_at": pd.Timestamp.now(tz="Asia/Shanghai").isoformat(),
                    "symbol": symbol,
                    "decision": "ERROR",
                    "auto_trade": "DISABLED",
                    "strategies": ",".join(ALL_STRATEGIES),
                    "entry_time": "",
                    "strategy_id": "",
                    "direction": "",
                    "entry_price": "",
                    "initial_stop": "",
                    "current_stop": "",
                    "pattern": "",
                    "lookback_hours": args.lookback_hours,
                    "reference_time": "",
                    "candidates": 0,
                    "accepted_total": 0,
                    "rejected_total": 0,
                    "bad_audits": 0,
                    "out_dir": str(run_root / symbol),
                    "error": str(exc),
                }
            )

    monitor = pd.DataFrame(rows)
    monitor.to_csv(run_root / "combined_monitor_signals.csv", index=False, encoding="utf-8-sig")
    monitor.to_csv(Path(args.out_dir) / "latest_combined_monitor_signals.csv", index=False, encoding="utf-8-sig")
    print(monitor.to_string(index=False))
    print(f"Saved combined monitor signals to {run_root / 'combined_monitor_signals.csv'}")


if __name__ == "__main__":
    main()
