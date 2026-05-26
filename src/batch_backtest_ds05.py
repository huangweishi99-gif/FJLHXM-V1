from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from backtest_ds05 import DS05BacktestConfig, run_ds05_backtest
from quant.data import load_ohlcv_for_engine
from quant.futures_specs import get_futures_spec
from quant.metrics import max_drawdown


def safe_name(path: Path) -> str:
    return path.stem.replace(" ", "_")


def iter_csv_files(data_dir: Path, pattern: str) -> list[Path]:
    files = sorted(data_dir.glob(pattern))
    return [path for path in files if path.is_file()]


def summarize_result(symbol: str, csv_path: Path, result: dict, initial_cash: float) -> dict:
    trades = result["trades"]
    bad_trades = result["bad_trades"]
    equity = result["equity"]
    final_equity = float(equity["equity"].iloc[-1]) if not equity.empty else initial_cash
    total_return = final_equity / initial_cash - 1.0
    wins = int((trades["net_pnl"] > 0).sum()) if not trades.empty else 0
    trade_count = int(len(trades))
    win_rate = wins / trade_count if trade_count else 0.0
    net_pnl = float(trades["net_pnl"].sum()) if not trades.empty else 0.0
    mdd = max_drawdown(equity["equity"]) if not equity.empty else 0.0

    return {
        "symbol": symbol,
        "csv": str(csv_path),
        "rows": int(len(result["df"])),
        "trades": trade_count,
        "wins": wins,
        "win_rate": win_rate,
        "bad_trades": int(len(bad_trades)),
        "net_pnl": net_pnl,
        "final_equity": final_equity,
        "total_return": total_return,
        "max_drawdown": mdd,
    }


def save_result_frames(out_dir: Path, result: dict) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    for name in ["trades", "bad_trades", "equity", "raw_nodes", "identity_nodes", "turns", "os_log"]:
        frame = result[name]
        if isinstance(frame, pd.DataFrame):
            frame.to_csv(out_dir / f"{name}.csv", index=False)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Batch run FengJi OS DS05 over a CSV directory.")
    parser.add_argument("--data-dir", required=True, help="Directory containing OHLCV CSV files.")
    parser.add_argument("--pattern", default="*日线*.csv", help="Glob pattern, default keeps daily files only.")
    parser.add_argument("--out-dir", default="results/ds05_batch")
    parser.add_argument("--initial-cash", type=float, default=100_000.0)
    parser.add_argument("--lots", type=int, default=1)
    parser.add_argument("--commission-rate", type=float, default=0.0001)
    parser.add_argument("--slippage-ticks", type=float, default=1.0)
    parser.add_argument("--no-futures-mode", action="store_true", help="Disable futures multiplier/margin/tick model.")
    parser.add_argument("--atr-window", type=int, default=14)
    parser.add_argument("--extreme-atr-tol", type=float, default=0.80)
    parser.add_argument("--gap", type=int, default=3)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    data_dir = Path(args.data_dir)
    out_dir = Path(args.out_dir)
    if not data_dir.exists():
        raise FileNotFoundError(f"Data directory not found: {data_dir}")

    config = DS05BacktestConfig(
        initial_cash=args.initial_cash,
        lots=args.lots,
        commission_rate=args.commission_rate,
        slippage_ticks=args.slippage_ticks,
        atr_window=args.atr_window,
        extreme_atr_tol=args.extreme_atr_tol,
        gap=args.gap,
        futures_mode=not args.no_futures_mode,
    )

    files = iter_csv_files(data_dir, args.pattern)
    if not files:
        raise FileNotFoundError(f"No CSV files matched {args.pattern} in {data_dir}")

    summaries: list[dict] = []
    errors: list[dict] = []
    for csv_path in files:
        symbol = safe_name(csv_path)
        try:
            df = load_ohlcv_for_engine(csv_path, config.atr_window)
            run_config = DS05BacktestConfig(
                initial_cash=config.initial_cash,
                lots=config.lots,
                commission_rate=config.commission_rate,
                slippage_ticks=config.slippage_ticks,
                atr_window=config.atr_window,
                extreme_atr_tol=config.extreme_atr_tol,
                gap=config.gap,
                futures_mode=config.futures_mode,
                spec=get_futures_spec(csv_path) if config.futures_mode else None,
            )
            result = run_ds05_backtest(df, run_config)
            save_result_frames(out_dir / symbol, result)
            row = summarize_result(symbol, csv_path, result, run_config.initial_cash)
            if run_config.spec:
                row["code"] = run_config.spec.code
                row["multiplier"] = run_config.spec.multiplier
                row["tick_size"] = run_config.spec.tick_size
                row["margin_rate"] = run_config.spec.margin_rate
            summaries.append(row)
            print(
                f"{symbol}: trades={row['trades']} bad={row['bad_trades']} "
                f"return={row['total_return'] * 100:.2f}% mdd={row['max_drawdown'] * 100:.2f}%"
            )
        except Exception as exc:  # Keep batch runs moving and write failures.
            errors.append({"symbol": symbol, "csv": str(csv_path), "error": repr(exc)})
            print(f"{symbol}: ERROR {exc}")

    out_dir.mkdir(parents=True, exist_ok=True)
    summary_df = pd.DataFrame(summaries).sort_values(["bad_trades", "total_return"], ascending=[True, False])
    summary_df.to_csv(out_dir / "summary.csv", index=False)
    pd.DataFrame(errors).to_csv(out_dir / "errors.csv", index=False)

    print("")
    print(f"Files processed: {len(files)}")
    print(f"Succeeded:       {len(summaries)}")
    print(f"Failed:          {len(errors)}")
    print(f"Summary:         {out_dir / 'summary.csv'}")


if __name__ == "__main__":
    main()
