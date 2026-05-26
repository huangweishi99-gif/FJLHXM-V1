from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from backtest_ds08 import DS08BacktestConfig, load_frame, run_ds08_backtest
from quant.futures_specs import get_futures_spec
from quant.metrics import max_drawdown


def symbol_from_path(path: Path) -> str:
    return path.stem.replace("_60m", "").replace("_60M", "")


def summarize(symbol: str, csv_path: Path, result: dict, initial_cash: float) -> dict:
    trades = result["trades"]
    bad_trades = result["bad_trades"]
    equity = result["equity"]
    final_equity = float(equity["equity"].iloc[-1]) if not equity.empty else initial_cash
    trade_count = int(len(trades))
    wins = int((trades["net_pnl"] > 0).sum()) if not trades.empty else 0
    return {
        "symbol": symbol,
        "csv": str(csv_path),
        "rows": int(len(result["df"])),
        "signals": int(len(result["signals"])),
        "trades": trade_count,
        "wins": wins,
        "win_rate": wins / trade_count if trade_count else 0.0,
        "bad_trades": int(len(bad_trades)),
        "net_pnl": float(trades["net_pnl"].sum()) if not trades.empty else 0.0,
        "final_equity": final_equity,
        "total_return": final_equity / initial_cash - 1.0,
        "max_drawdown": max_drawdown(equity["equity"]) if not equity.empty else 0.0,
    }


def save_result(out_dir: Path, result: dict) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    for name in ["signals", "trades", "bad_trades", "orders", "stop_history", "equity", "raw_nodes", "identity_nodes", "turns", "os_log"]:
        frame = result[name]
        if isinstance(frame, pd.DataFrame):
            frame.to_csv(out_dir / f"{name}.csv", index=False)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Batch run DS08 over 60m/H1 futures CSV files.")
    parser.add_argument("--data-dir", required=True)
    parser.add_argument("--pattern", default="*_60m.csv")
    parser.add_argument("--out-dir", default="results/ds08_real_60m_futures")
    parser.add_argument("--initial-cash", type=float, default=100_000.0)
    parser.add_argument("--lots", type=int, default=1)
    parser.add_argument("--commission-rate", type=float, default=0.0001)
    parser.add_argument("--slippage-ticks", type=float, default=1.0)
    parser.add_argument("--atr-window", type=int, default=14)
    parser.add_argument("--gap", type=int, default=3)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    data_dir = Path(args.data_dir)
    out_dir = Path(args.out_dir)
    files = sorted(path for path in data_dir.glob(args.pattern) if path.is_file())
    summaries: list[dict] = []
    errors: list[dict] = []

    for csv_path in files:
        symbol = symbol_from_path(csv_path)
        try:
            config = DS08BacktestConfig(
                initial_cash=args.initial_cash,
                lots=args.lots,
                commission_rate=args.commission_rate,
                slippage_ticks=args.slippage_ticks,
                atr_window=args.atr_window,
                gap=args.gap,
                futures_mode=True,
                spec=get_futures_spec(csv_path),
            )
            df = load_frame(csv_path, config.atr_window)
            result = run_ds08_backtest(df, config, symbol=symbol)
            save_result(out_dir / symbol, result)
            row = summarize(symbol, csv_path, result, config.initial_cash)
            if config.spec:
                row["code"] = config.spec.code
                row["multiplier"] = config.spec.multiplier
                row["tick_size"] = config.spec.tick_size
                row["margin_rate"] = config.spec.margin_rate
            summaries.append(row)
            print(f"{symbol}: signals={row['signals']} trades={row['trades']} bad={row['bad_trades']} return={row['total_return'] * 100:.2f}% mdd={row['max_drawdown'] * 100:.2f}%")
        except Exception as exc:
            errors.append({"symbol": symbol, "csv": str(csv_path), "error": repr(exc)})
            print(f"{symbol}: ERROR {exc}")

    out_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(summaries).sort_values(["bad_trades", "total_return"], ascending=[True, False]).to_csv(out_dir / "summary.csv", index=False)
    pd.DataFrame(errors).to_csv(out_dir / "errors.csv", index=False)
    print("")
    print(f"Files:      {len(files)}")
    print(f"Succeeded:  {len(summaries)}")
    print(f"Failed:     {len(errors)}")
    print(f"Summary:    {out_dir / 'summary.csv'}")


if __name__ == "__main__":
    main()
