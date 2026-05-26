from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from batch_unified_crypto_whitelist import fetch_okx_history
from unified_whitelist_engine import UnifiedConfig, run_unified_symbol


def read_observation_rules(path: str | Path) -> list[dict]:
    rules = pd.read_csv(path)
    required = {"symbol", "allowed_strategies"}
    missing = required.difference(rules.columns)
    if missing:
        raise ValueError(f"Observation rules missing columns: {sorted(missing)}")
    out: list[dict] = []
    for _, row in rules.iterrows():
        strategies = [item.strip().upper() for item in str(row["allowed_strategies"]).split(",") if item.strip()]
        if not strategies:
            continue
        out.append(
            {
                "symbol": str(row["symbol"]).strip().upper(),
                "strategies": strategies,
                "reason": str(row.get("reason", "")),
            }
        )
    return out


def safe_read(path: Path) -> pd.DataFrame:
    if not path.exists() or path.stat().st_size <= 5:
        return pd.DataFrame()
    try:
        return pd.read_csv(path)
    except pd.errors.EmptyDataError:
        return pd.DataFrame()


def latest_signals(symbol_dir: Path, lookback_hours: int, reference_time: pd.Timestamp) -> pd.DataFrame:
    accepted = safe_read(symbol_dir / "accepted_trades.csv")
    if accepted.empty:
        return pd.DataFrame()
    accepted["entry_time"] = pd.to_datetime(accepted["entry_time"], errors="coerce")
    if pd.isna(reference_time):
        return pd.DataFrame()
    start = reference_time - pd.Timedelta(hours=lookback_hours)
    return accepted[accepted["entry_time"] >= start].copy()


def monitor_symbol(
    symbol: str,
    strategies: list[str],
    reason: str,
    args: argparse.Namespace,
    run_root: Path,
) -> list[dict]:
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
    summary = run_unified_symbol(name, config, daily_csv, h1_csv, m15_csv, strategies, symbol_dir)
    m15_frame = pd.read_csv(m15_csv, usecols=["date"])
    reference_time = pd.to_datetime(m15_frame["date"], errors="coerce").max()
    signals = latest_signals(symbol_dir, args.lookback_hours, reference_time)

    rows: list[dict] = []
    checked_at = pd.Timestamp.now(tz="Asia/Shanghai").isoformat()
    if signals.empty:
        rows.append(
            {
                "checked_at": checked_at,
                "symbol": symbol,
                "decision": "NO_SIGNAL",
                "auto_trade": "DISABLED",
                "allowed_strategies": ",".join(strategies),
                "reason": reason,
                "entry_time": "",
                "strategy_id": "",
                "direction": "",
                "entry_price": "",
                "initial_stop": "",
                "current_stop": "",
                "pattern": "",
                "lookback_hours": args.lookback_hours,
                "reference_time": "" if pd.isna(reference_time) else str(reference_time),
                "candidates": summary["candidates"],
                "accepted_total": summary["accepted"],
                "rejected_total": summary["rejected"],
                "bad_audits": summary["bad_audits"],
                "out_dir": str(symbol_dir),
            }
        )
        return rows

    for _, signal in signals.sort_values(["entry_time", "strategy_priority"]).iterrows():
        rows.append(
            {
                "checked_at": checked_at,
                "symbol": symbol,
                "decision": "OBSERVE_SIGNAL_ONLY",
                "auto_trade": "DISABLED",
                "allowed_strategies": ",".join(strategies),
                "reason": reason,
                "entry_time": signal.get("entry_time", ""),
                "strategy_id": signal.get("strategy_id", ""),
                "direction": signal.get("direction", ""),
                "entry_price": signal.get("entry_price", ""),
                "initial_stop": signal.get("initial_stop", ""),
                "current_stop": signal.get("current_stop", ""),
                "pattern": signal.get("pattern", ""),
                "lookback_hours": args.lookback_hours,
                "reference_time": "" if pd.isna(reference_time) else str(reference_time),
                "candidates": summary["candidates"],
                "accepted_total": summary["accepted"],
                "rejected_total": summary["rejected"],
                "bad_audits": summary["bad_audits"],
                "out_dir": str(symbol_dir),
            }
        )
    return rows


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Observation-only crypto realtime monitor for DS01-DS09 M15 rules.")
    parser.add_argument("--rules", default="data/crypto_m15_forward_observation_rules.csv")
    parser.add_argument("--out-dir", default="results/crypto_realtime_monitor")
    parser.add_argument("--cache-dir", default="data/crypto_okx")
    parser.add_argument("--days", type=int, default=180)
    parser.add_argument("--lookback-hours", type=int, default=24)
    parser.add_argument("--initial-cash", type=float, default=1000.0)
    parser.add_argument("--atr-window", type=int, default=14)
    parser.add_argument("--gap", type=int, default=3)
    parser.add_argument("--max-same-direction-entries", type=int, default=3)
    parser.add_argument("--use-cache", action="store_true", help="Use cached OKX bars instead of refreshing latest data.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    rules = read_observation_rules(args.rules)
    run_root = Path(args.out_dir) / pd.Timestamp.now(tz="Asia/Shanghai").strftime("%Y%m%d_%H%M%S")
    run_root.mkdir(parents=True, exist_ok=True)

    rows: list[dict] = []
    for rule in rules:
        try:
            rows.extend(monitor_symbol(rule["symbol"], rule["strategies"], rule["reason"], args, run_root))
        except Exception as exc:
            rows.append(
                {
                    "checked_at": pd.Timestamp.now(tz="Asia/Shanghai").isoformat(),
                    "symbol": rule["symbol"],
                    "decision": "ERROR",
                    "auto_trade": "DISABLED",
                    "allowed_strategies": ",".join(rule["strategies"]),
                    "reason": str(exc),
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
                    "out_dir": str(run_root / rule["symbol"]),
                }
            )

    monitor = pd.DataFrame(rows)
    monitor.to_csv(run_root / "monitor_signals.csv", index=False, encoding="utf-8-sig")
    monitor.to_csv(Path(args.out_dir) / "latest_monitor_signals.csv", index=False, encoding="utf-8-sig")
    print(monitor.to_string(index=False))
    print(f"Saved monitor signals to {run_root / 'monitor_signals.csv'}")


if __name__ == "__main__":
    main()
