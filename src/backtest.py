from __future__ import annotations

import argparse
from dataclasses import dataclass

import pandas as pd

from quant.data import load_ohlcv_csv
from quant.metrics import summarize
from quant.strategies import moving_average_cross_signal


@dataclass(frozen=True)
class BacktestConfig:
    initial_cash: float = 100_000.0
    commission_rate: float = 0.0003
    slippage_rate: float = 0.0002


def run_backtest(
    ohlcv: pd.DataFrame,
    short_window: int,
    long_window: int,
    config: BacktestConfig,
) -> pd.DataFrame:
    signal = moving_average_cross_signal(
        ohlcv["close"],
        short_window=short_window,
        long_window=long_window,
    )

    result = signal.copy()
    result["market_return"] = result["close"].pct_change().fillna(0.0)

    # Use yesterday's signal to avoid look-ahead bias.
    result["position_lag"] = result["position"].shift(1).fillna(0.0)
    result["trade"] = result["position"].diff().abs().fillna(result["position"])
    trading_cost = result["trade"] * (config.commission_rate + config.slippage_rate)
    result["strategy_return"] = result["position_lag"] * result["market_return"] - trading_cost
    result["equity"] = config.initial_cash * (1.0 + result["strategy_return"]).cumprod()
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a moving-average quant backtest.")
    parser.add_argument("--csv", required=True, help="Path to OHLCV CSV.")
    parser.add_argument("--short-window", type=int, default=20)
    parser.add_argument("--long-window", type=int, default=60)
    parser.add_argument("--initial-cash", type=float, default=100_000.0)
    parser.add_argument("--commission-rate", type=float, default=0.0003)
    parser.add_argument("--slippage-rate", type=float, default=0.0002)
    parser.add_argument("--output", default="", help="Optional path to save daily equity CSV.")
    return parser.parse_args()


def format_percent(value: float) -> str:
    return f"{value * 100:.2f}%"


def main() -> None:
    args = parse_args()
    data = load_ohlcv_csv(args.csv)
    config = BacktestConfig(
        initial_cash=args.initial_cash,
        commission_rate=args.commission_rate,
        slippage_rate=args.slippage_rate,
    )
    result = run_backtest(data, args.short_window, args.long_window, config)
    stats = summarize(result["equity"], result["strategy_return"])

    print("Backtest result")
    print(f"Rows:          {len(result)}")
    print(f"Final equity:  {stats['final_equity']:.2f}")
    print(f"Total return:  {format_percent(stats['total_return'])}")
    print(f"Annual return: {format_percent(stats['annual_return'])}")
    print(f"Max drawdown:  {format_percent(stats['max_drawdown'])}")
    print(f"Sharpe ratio:  {stats['sharpe']:.2f}")

    if args.output:
        result.to_csv(args.output, index_label="date")
        print(f"Saved daily result to {args.output}")


if __name__ == "__main__":
    main()

