from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from quant.futures_specs import get_futures_spec
from unified_whitelist_engine import DEFAULT_STRATEGIES_CSV, UnifiedConfig, run_unified_symbol


def read_whitelist(value: str) -> list[str]:
    path = Path(value)
    if path.exists():
        raw = path.read_text(encoding="utf-8-sig")
        return [line.strip() for line in raw.splitlines() if line.strip() and not line.strip().startswith("#")]
    return [item.strip() for item in value.split(",") if item.strip()]


def first_match(directory: str | Path, patterns: list[str]) -> Path | None:
    root = Path(directory)
    if not root.exists():
        return None
    for pattern in patterns:
        matches = sorted(root.glob(pattern))
        if matches:
            return matches[0]
    return None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Batch unified FengJi Total Pattern DS01-DS09 whitelist ledger engine.")
    parser.add_argument("--whitelist", required=True, help="Comma-separated symbols or a text file with one symbol per line.")
    parser.add_argument("--daily-dir", required=True)
    parser.add_argument("--minute-dir", required=True)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--strategies", default=DEFAULT_STRATEGIES_CSV)
    parser.add_argument("--initial-cash", type=float, default=100_000.0)
    parser.add_argument("--lots", type=int, default=1)
    parser.add_argument("--commission-rate", type=float, default=0.0001)
    parser.add_argument("--slippage-ticks", type=float, default=1.0)
    parser.add_argument("--atr-window", type=int, default=14)
    parser.add_argument("--gap", type=int, default=3)
    parser.add_argument("--max-same-direction-entries", type=int, default=3)
    return parser.parse_args()


def safe_read_csv(path: Path) -> pd.DataFrame:
    if not path.exists() or path.stat().st_size <= 5:
        return pd.DataFrame()
    try:
        return pd.read_csv(path)
    except pd.errors.EmptyDataError:
        return pd.DataFrame()


def score_futures_results(symbol_dir: Path, initial_cash: float) -> dict:
    accepted = safe_read_csv(symbol_dir / "accepted_trades.csv")
    rejected = safe_read_csv(symbol_dir / "rejected_orders.csv")
    bad = safe_read_csv(symbol_dir / "strategy_bad_trades.csv")
    if accepted.empty:
        return {
            "trades": 0,
            "wins": 0,
            "win_rate": 0.0,
            "net_pnl": 0.0,
            "final_equity": initial_cash,
            "total_return": 0.0,
            "max_drawdown": 0.0,
            "accepted": 0,
            "rejected": len(rejected),
            "bad_audits": len(bad),
        }

    accepted = accepted.copy()
    accepted["exit_time"] = pd.to_datetime(accepted["exit_time"], errors="coerce")
    accepted["entry_time"] = pd.to_datetime(accepted["entry_time"], errors="coerce")
    accepted["net"] = pd.to_numeric(accepted.get("net", 0.0), errors="coerce").fillna(0.0)
    accepted = accepted.sort_values(["exit_time", "portfolio_trade_no"]).reset_index(drop=True)
    accepted["equity"] = initial_cash + accepted["net"].cumsum()
    accepted["peak"] = accepted["equity"].cummax()
    accepted["drawdown"] = accepted["equity"] / accepted["peak"] - 1.0
    accepted.to_csv(symbol_dir / "futures_scored_accepted_trades.csv", index=False, encoding="utf-8-sig")

    by_strategy = (
        accepted.groupby("strategy_id", dropna=False)
        .agg(
            trades=("strategy_id", "size"),
            wins=("net", lambda x: int((x > 0).sum())),
            net_pnl=("net", "sum"),
        )
        .reset_index()
    )
    by_strategy["win_rate"] = by_strategy["wins"] / by_strategy["trades"]
    by_strategy.to_csv(symbol_dir / "futures_by_strategy.csv", index=False, encoding="utf-8-sig")

    return {
        "trades": int(len(accepted)),
        "wins": int((accepted["net"] > 0).sum()),
        "win_rate": float((accepted["net"] > 0).mean()),
        "net_pnl": float(accepted["net"].sum()),
        "final_equity": float(accepted["equity"].iloc[-1]),
        "total_return": float(accepted["equity"].iloc[-1] / initial_cash - 1.0),
        "max_drawdown": float(accepted["drawdown"].min()),
        "accepted": int(len(accepted)),
        "rejected": len(rejected),
        "bad_audits": len(bad),
    }


def main() -> None:
    args = parse_args()
    symbols = read_whitelist(args.whitelist)
    strategies = [item.strip().upper() for item in args.strategies.split(",") if item.strip()]
    root_out = Path(args.out_dir)
    root_out.mkdir(parents=True, exist_ok=True)
    summaries: list[dict] = []

    for symbol in symbols:
        daily_csv = first_match(args.daily_dir, [f"{symbol}_日线_*.csv", f"*{symbol}*日线*.csv", f"{symbol}*.csv"])
        h1_csv = first_match(args.minute_dir, [f"{symbol}_60m.csv", f"*{symbol}*60m*.csv", f"*{symbol}*60*.csv"])
        m15_csv = first_match(args.minute_dir, [f"{symbol}_15m.csv", f"{symbol}_15m_latest.csv", f"*{symbol}*15m*.csv", f"*{symbol}*15*.csv"])
        spec = get_futures_spec(daily_csv or h1_csv or m15_csv or symbol)
        config = UnifiedConfig(
            initial_cash=args.initial_cash,
            lots=args.lots,
            commission_rate=args.commission_rate,
            slippage_ticks=args.slippage_ticks,
            atr_window=args.atr_window,
            gap=args.gap,
            max_same_direction_entries=args.max_same_direction_entries,
            futures_mode=True,
            spec=spec,
        )
        try:
            summary = run_unified_symbol(
                symbol=symbol,
                config=config,
                daily_csv=daily_csv,
                h1_csv=h1_csv,
                m15_csv=m15_csv,
                strategies=strategies,
                out_dir=root_out / symbol,
            )
            score = score_futures_results(root_out / symbol, args.initial_cash)
            summary.update(
                {
                    "daily_csv": str(daily_csv or ""),
                    "h1_csv": str(h1_csv or ""),
                    "m15_csv": str(m15_csv or ""),
                    **score,
                    "status": "ok",
                    "error": "",
                }
            )
        except Exception as exc:
            summary = {
                "symbol": symbol,
                "spec": spec.code if spec else "",
                "candidates": 0,
                "trades": 0,
                "wins": 0,
                "win_rate": 0.0,
                "net_pnl": 0.0,
                "final_equity": args.initial_cash,
                "total_return": 0.0,
                "max_drawdown": 0.0,
                "accepted": 0,
                "rejected": 0,
                "bad_audits": 0,
                "out_dir": str(root_out / symbol),
                "daily_csv": str(daily_csv or ""),
                "h1_csv": str(h1_csv or ""),
                "m15_csv": str(m15_csv or ""),
                "status": "error",
                "error": str(exc),
            }
        summaries.append(summary)
        print(
            f"{symbol}: {summary['status']} candidates={summary['candidates']} "
            f"accepted={summary['accepted']} rejected={summary['rejected']} "
            f"return={summary.get('total_return', 0.0):.2%} dd={summary.get('max_drawdown', 0.0):.2%} "
            f"bad={summary['bad_audits']}"
        )

    pd.DataFrame(summaries).to_csv(root_out / "whitelist_summary.csv", index=False, encoding="utf-8-sig")
    print(f"Saved whitelist summary to {root_out / 'whitelist_summary.csv'}")


if __name__ == "__main__":
    main()
