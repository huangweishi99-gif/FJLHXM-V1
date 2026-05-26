from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from backtest_ds07 import DS07BacktestConfig, load_frame, run_ds07_backtest
from quant.futures_specs import get_futures_spec
from quant.metrics import max_drawdown


def symbol_from_h1(path: Path) -> str:
    return path.stem.replace("_60m", "").replace("_60M", "")


def find_d1_file(d1_dir: Path, symbol: str) -> Path | None:
    exact = sorted(d1_dir.glob(f"{symbol}_日线*.csv"))
    if exact:
        return exact[0]
    fuzzy = sorted(d1_dir.glob(f"*{symbol}*日线*.csv"))
    if fuzzy:
        return fuzzy[0]
    aliases = {"液化气": "LPG", "铁矿": "铁矿石"}
    alias = aliases.get(symbol)
    if alias:
        return find_d1_file(d1_dir, alias)
    return None


def summarize(symbol: str, d1_path: Path, h1_path: Path, result: dict, initial_cash: float) -> dict:
    trades = result["trades"]
    bad_trades = result["bad_trades"]
    equity = result["equity"]
    final_equity = float(equity["equity"].iloc[-1]) if not equity.empty else initial_cash
    trade_count = int(len(trades))
    wins = int((trades["net_pnl"] > 0).sum()) if not trades.empty else 0
    return {
        "symbol": symbol,
        "d1_csv": str(d1_path),
        "h1_csv": str(h1_path),
        "d1_rows": int(len(result["d1_df"])),
        "h1_rows": int(len(result["h1_df"])),
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
    for name in [
        "signals",
        "trades",
        "bad_trades",
        "orders",
        "stop_history",
        "equity",
        "d1_raw_nodes",
        "h1_raw_nodes",
        "d1_identity_nodes",
        "h1_identity_nodes",
        "d1_turns",
        "h1_turns",
        "d1_os_log",
        "h1_os_log",
    ]:
        frame = result[name]
        if isinstance(frame, pd.DataFrame):
            frame.to_csv(out_dir / f"{name}.csv", index=False)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Batch run DS07 over matched D1 and 60m futures CSV files.")
    parser.add_argument("--d1-dir", required=True)
    parser.add_argument("--h1-dir", required=True)
    parser.add_argument("--out-dir", default="results/ds07_real_60m_futures")
    parser.add_argument("--h1-pattern", default="*_60m.csv")
    parser.add_argument("--initial-cash", type=float, default=100_000.0)
    parser.add_argument("--lots", type=int, default=1)
    parser.add_argument("--commission-rate", type=float, default=0.0001)
    parser.add_argument("--slippage-ticks", type=float, default=1.0)
    parser.add_argument("--atr-window", type=int, default=14)
    parser.add_argument("--gap", type=int, default=3)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    d1_dir = Path(args.d1_dir)
    h1_dir = Path(args.h1_dir)
    out_dir = Path(args.out_dir)
    summaries: list[dict] = []
    errors: list[dict] = []

    h1_files = sorted(path for path in h1_dir.glob(args.h1_pattern) if path.is_file())
    for h1_path in h1_files:
        symbol = symbol_from_h1(h1_path)
        d1_path = find_d1_file(d1_dir, symbol)
        if d1_path is None:
            errors.append({"symbol": symbol, "h1_csv": str(h1_path), "error": "D1 file not found"})
            print(f"{symbol}: ERROR D1 file not found")
            continue
        try:
            config = DS07BacktestConfig(
                initial_cash=args.initial_cash,
                lots=args.lots,
                commission_rate=args.commission_rate,
                slippage_ticks=args.slippage_ticks,
                atr_window=args.atr_window,
                gap=args.gap,
                futures_mode=True,
                spec=get_futures_spec(d1_path),
            )
            d1_df = load_frame(d1_path, config.atr_window)
            h1_df = load_frame(h1_path, config.atr_window)
            result = run_ds07_backtest(d1_df, h1_df, config, symbol=symbol)
            save_result(out_dir / symbol, result)
            row = summarize(symbol, d1_path, h1_path, result, config.initial_cash)
            if config.spec:
                row["code"] = config.spec.code
                row["multiplier"] = config.spec.multiplier
                row["tick_size"] = config.spec.tick_size
                row["margin_rate"] = config.spec.margin_rate
            summaries.append(row)
            print(f"{symbol}: signals={row['signals']} trades={row['trades']} bad={row['bad_trades']} return={row['total_return'] * 100:.2f}% mdd={row['max_drawdown'] * 100:.2f}%")
        except Exception as exc:
            errors.append({"symbol": symbol, "d1_csv": str(d1_path), "h1_csv": str(h1_path), "error": repr(exc)})
            print(f"{symbol}: ERROR {exc}")

    out_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(summaries).sort_values(["bad_trades", "total_return"], ascending=[True, False]).to_csv(out_dir / "summary.csv", index=False)
    pd.DataFrame(errors).to_csv(out_dir / "errors.csv", index=False)
    print("")
    print(f"H1 files:   {len(h1_files)}")
    print(f"Succeeded:  {len(summaries)}")
    print(f"Failed:     {len(errors)}")
    print(f"Summary:    {out_dir / 'summary.csv'}")


if __name__ == "__main__":
    main()
