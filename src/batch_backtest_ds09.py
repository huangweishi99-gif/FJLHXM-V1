from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from backtest_ds09 import DS09BacktestConfig, load_frame, load_m15_frame, run_ds09_backtest
from quant.futures_specs import get_futures_spec
from quant.metrics import max_drawdown


def symbol_from_m15(path: Path) -> str:
    stem = path.stem
    for token in ("_15m_latest", "_15M_LATEST", "_15m_", "_15M_"):
        if token in stem:
            return stem.split(token)[0]
    return stem.replace("_15m", "").replace("_15M", "")


def find_d1_file(d1_dir: Path, symbol: str) -> Path | None:
    exact = sorted(d1_dir.glob(f"{symbol}_日线*.csv"))
    if exact:
        return exact[0]
    aliases = {"液化气": "LPG", "铁矿": "铁矿石", "棕榈": "棕榈油"}
    alias = aliases.get(symbol)
    if alias:
        exact = sorted(d1_dir.glob(f"{alias}_日线*.csv"))
        if exact:
            return exact[0]
    fuzzy = sorted(d1_dir.glob(f"*{symbol}*日线*.csv"))
    return fuzzy[0] if fuzzy else None


def summarize(symbol: str, d1_path: Path, m15_path: Path, result: dict, initial_cash: float) -> dict:
    trades = result["trades"]
    bad_trades = result["bad_trades"]
    equity = result["equity"]
    debug = result["debug"].iloc[0].to_dict() if not result["debug"].empty else {}
    final_equity = float(equity["equity"].iloc[-1]) if not equity.empty else initial_cash
    trade_count = int(len(trades))
    wins = int((trades["net_pnl"] > 0).sum()) if not trades.empty else 0
    return {
        "symbol": symbol,
        "d1_csv": str(d1_path),
        "m15_csv": str(m15_path),
        "d1_rows": int(len(result["d1_df"])),
        "m15_rows": int(len(result["m5_df"])),
        "signals": int(len(result["signals"])),
        "trades": trade_count,
        "wins": wins,
        "win_rate": wins / trade_count if trade_count else 0.0,
        "bad_trades": int(len(bad_trades)),
        "trade_consistency_ok": bool(debug.get("trade_consistency_ok", False)),
        "end_forced_close_count": int(debug.get("end_forced_close_count", 0)),
        "net_pnl": float(trades["net_pnl"].sum()) if not trades.empty else 0.0,
        "final_equity": final_equity,
        "total_return": final_equity / initial_cash - 1.0,
        "max_drawdown": max_drawdown(equity["equity"]) if not equity.empty else 0.0,
    }


def save_result(out_dir: Path, result: dict) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    for name in ["signals", "trades", "bad_trades", "orders", "stop_history", "equity", "raw_nodes", "identity_nodes", "turns", "os_log", "debug"]:
        frame = result[name]
        if isinstance(frame, pd.DataFrame):
            frame.to_csv(out_dir / f"{name}.csv", index=False)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Batch run DS09 (D1 + M15) over matched futures CSV files.")
    parser.add_argument("--d1-dir", required=True)
    parser.add_argument("--m15-dir", required=True)
    parser.add_argument("--out-dir", default="results/ds09_real_m15_futures")
    parser.add_argument("--m15-pattern", default="*15m*.csv")
    parser.add_argument("--m5-dir", help="Deprecated alias for --m15-dir.")
    parser.add_argument("--m5-pattern", help="Deprecated alias for --m15-pattern.")
    parser.add_argument("--initial-cash", type=float, default=100_000.0)
    parser.add_argument("--lots", type=int, default=1)
    parser.add_argument("--commission-rate", type=float, default=0.0001)
    parser.add_argument("--slippage-ticks", type=float, default=1.0)
    parser.add_argument("--atr-window", type=int, default=14)
    parser.add_argument("--gap", type=int, default=3)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    m15_dir = Path(args.m15_dir or args.m5_dir or "")
    if not m15_dir.exists():
        raise SystemExit("DS09 batch requires --m15-dir with M15 CSV files.")
    m15_pattern = args.m15_pattern or args.m5_pattern or "*15m*.csv"

    d1_dir = Path(args.d1_dir)
    out_dir = Path(args.out_dir)
    files = sorted(path for path in m15_dir.glob(m15_pattern) if path.is_file())
    summaries: list[dict] = []
    errors: list[dict] = []

    for m15_path in files:
        symbol = symbol_from_m15(m15_path)
        d1_path = find_d1_file(d1_dir, symbol)
        if d1_path is None:
            errors.append({"symbol": symbol, "m15_csv": str(m15_path), "error": "D1 file not found"})
            print(f"{symbol}: ERROR D1 file not found")
            continue
        try:
            config = DS09BacktestConfig(
                initial_cash=args.initial_cash,
                lots=args.lots,
                commission_rate=args.commission_rate,
                slippage_ticks=args.slippage_ticks,
                atr_window=args.atr_window,
                gap=args.gap,
                futures_mode=True,
                spec=get_futures_spec(d1_path) or get_futures_spec(m15_path),
            )
            d1_df = load_frame(d1_path, config.atr_window)
            m15_df = load_m15_frame(m15_path, config.atr_window)
            result = run_ds09_backtest(d1_df, m15_df, config, symbol=symbol)
            save_result(out_dir / symbol, result)
            row = summarize(symbol, d1_path, m15_path, result, config.initial_cash)
            if config.spec:
                row["code"] = config.spec.code
                row["multiplier"] = config.spec.multiplier
                row["tick_size"] = config.spec.tick_size
                row["margin_rate"] = config.spec.margin_rate
            summaries.append(row)
            print(
                f"{symbol}: signals={row['signals']} trades={row['trades']} bad={row['bad_trades']} "
                f"consistent={row['trade_consistency_ok']} return={row['total_return'] * 100:.2f}% "
                f"mdd={row['max_drawdown'] * 100:.2f}%"
            )
        except Exception as exc:
            errors.append({"symbol": symbol, "d1_csv": str(d1_path), "m15_csv": str(m15_path), "error": repr(exc)})
            print(f"{symbol}: ERROR {exc}")

    out_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(summaries).sort_values(["bad_trades", "trade_consistency_ok", "total_return"], ascending=[True, False, False]).to_csv(
        out_dir / "summary.csv", index=False
    )
    pd.DataFrame(errors).to_csv(out_dir / "errors.csv", index=False)
    print("")
    print(f"M15 files:  {len(files)}")
    print(f"Succeeded:  {len(summaries)}")
    print(f"Failed:     {len(errors)}")
    print(f"Summary:    {out_dir / 'summary.csv'}")


if __name__ == "__main__":
    main()
