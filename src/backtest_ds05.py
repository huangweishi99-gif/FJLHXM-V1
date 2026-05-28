from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from quant.data import load_ohlcv_for_engine
from quant.ds05 import audit_ds05_camp_direction, check_stop, make_ds05_signal, update_ds05_stop
from quant.futures_specs import FuturesSpec, get_futures_spec
from quant.metrics import max_drawdown
from quant.os_engine import FengJiOSIdentityEngine


@dataclass(frozen=True)
class DS05BacktestConfig:
    initial_cash: float = 100_000.0
    lots: int = 1
    commission_rate: float = 0.0001
    slippage_ticks: float = 1.0
    atr_window: int = 14
    extreme_atr_tol: float = 0.80
    gap: int = 3
    futures_mode: bool = False
    spec: FuturesSpec | None = None


def contract_multiplier(config: DS05BacktestConfig) -> float:
    return config.spec.multiplier if config.futures_mode and config.spec else 1.0


def tick_size(config: DS05BacktestConfig) -> float:
    return config.spec.tick_size if config.futures_mode and config.spec else 0.0


def margin_rate(config: DS05BacktestConfig) -> float:
    return config.spec.margin_rate if config.futures_mode and config.spec else 0.0


def apply_slippage(price: float, side: int, action: str, config: DS05BacktestConfig) -> float:
    slip = tick_size(config) * config.slippage_ticks
    if slip <= 0:
        return price
    if action == "entry":
        return price + slip if side == 1 else price - slip
    return price - slip if side == 1 else price + slip


def notional(price: float, config: DS05BacktestConfig) -> float:
    return abs(price * config.lots * contract_multiplier(config))


def required_margin(price: float, config: DS05BacktestConfig) -> float:
    return notional(price, config) * margin_rate(config)


def trade_fee(price: float, config: DS05BacktestConfig) -> float:
    return notional(price, config) * config.commission_rate


def position_pnl(position: dict, exit_price: float, config: DS05BacktestConfig) -> float:
    side = int(position["side"])
    entry = float(position["entry_price"])
    qty = int(position["lots"]) * contract_multiplier(config)
    if side == 1:
        return (exit_price - entry) * qty
    return (entry - exit_price) * qty


def build_os_frame(df: pd.DataFrame, gap: int) -> tuple[pd.DataFrame, FengJiOSIdentityEngine]:
    engine = FengJiOSIdentityEngine(gap=gap).run(df)
    return engine.to_frame(df), engine


def run_ds05_backtest(df: pd.DataFrame, config: DS05BacktestConfig) -> dict[str, pd.DataFrame | FengJiOSIdentityEngine]:
    os_df, engine = build_os_frame(df, config.gap)
    cash = config.initial_cash
    position: dict | None = None
    trade_no = 0
    trades: list[dict] = []
    equity: list[dict] = []

    for i in range(len(os_df)):
        row = os_df.iloc[i]
        date = row["date"]

        if position is None:
            signal = make_ds05_signal(os_df, i, config.extreme_atr_tol)
            if signal is not None:
                side = signal.side
                entry_price = apply_slippage(signal.entry_price, side, "entry", config)
                entry_fee = trade_fee(entry_price, config)
                margin = required_margin(entry_price, config)
                if cash >= margin + entry_fee:
                    cash -= entry_fee
                    trade_no += 1
                    position = {
                        "trade_no": trade_no,
                        "side": side,
                        "entry_idx": signal.activate_idx,
                        "entry_date": date,
                        "entry_price": entry_price,
                        "lots": config.lots,
                        "multiplier": contract_multiplier(config),
                        "margin": margin,
                        "stop": signal.initial_stop,
                        "initial_stop": signal.initial_stop,
                        "entry_fee": entry_fee,
                        "pattern": signal.pattern,
                        "k1": signal.k1,
                        "k2": signal.k2,
                        "k3": signal.k3,
                        "k2_possible_extreme": signal.k2_possible_extreme,
                        "camp_k1": signal.camp_k1,
                        "camp_k2": signal.camp_k2,
                        "camp_k3": signal.camp_k3,
                        "signal_camp": signal.signal_camp,
                    }

        if position is not None and i >= int(position["entry_idx"]):
            side = int(position["side"])
            exit_price, exit_reason = check_stop(row, position)
            if exit_price is not None:
                exit_price = apply_slippage(exit_price, side, "exit", config)
                gross = position_pnl(position, exit_price, config)
                exit_fee = trade_fee(exit_price, config)
                net = gross - float(position["entry_fee"]) - exit_fee
                cash += gross - exit_fee
                trades.append(
                    {
                        "trade_no": position["trade_no"],
                        "direction": "long" if side == 1 else "short",
                        "entry_idx": position["entry_idx"],
                        "exit_idx": i,
                        "entry_date": position["entry_date"],
                        "exit_date": date,
                        "entry_price": position["entry_price"],
                        "exit_price": exit_price,
                        "lots": position["lots"],
                        "multiplier": position["multiplier"],
                        "margin": position["margin"],
                        "initial_stop": position["initial_stop"],
                        "final_stop": position["stop"],
                        "gross_pnl": gross,
                        "net_pnl": net,
                        "fee": float(position["entry_fee"]) + exit_fee,
                        "pattern": position["pattern"],
                        "exit_reason": exit_reason,
                        "k1": position["k1"],
                        "k2": position["k2"],
                        "k3": position["k3"],
                        "k2_possible_extreme": position["k2_possible_extreme"],
                        "camp_k1": position["camp_k1"],
                        "camp_k2": position["camp_k2"],
                        "camp_k3": position["camp_k3"],
                        "signal_camp": position["signal_camp"],
                    }
                )
                position = None
            else:
                position = update_ds05_stop(position, row)

        unrealized = 0.0
        if position is not None:
            unrealized = position_pnl(position, float(row["close"]), config)
        equity.append({"date": date, "equity": cash + unrealized, "cash": cash, "unrealized": unrealized})

    trades_df = pd.DataFrame(trades)
    equity_df = pd.DataFrame(equity)
    if not equity_df.empty:
        equity_df["peak"] = equity_df["equity"].cummax()
        equity_df["drawdown"] = equity_df["equity"] / equity_df["peak"] - 1.0

    return {
        "df": os_df,
        "engine": engine,
        "raw_nodes": engine.export_raw_nodes(),
        "identity_nodes": engine.export_tagged_nodes(),
        "turns": engine.export_turns(),
        "os_log": engine.export_os_log(),
        "trades": trades_df,
        "bad_trades": audit_ds05_camp_direction(trades_df),
        "equity": equity_df,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run FengJi OS DS05 finger-pattern backtest.")
    parser.add_argument("--csv", required=True, help="Path to OHLCV CSV.")
    parser.add_argument("--initial-cash", type=float, default=100_000.0)
    parser.add_argument("--lots", type=int, default=1, help="Lots per trade.")
    parser.add_argument("--commission-rate", type=float, default=0.0001)
    parser.add_argument("--slippage-ticks", type=float, default=1.0)
    parser.add_argument("--atr-window", type=int, default=14)
    parser.add_argument("--extreme-atr-tol", type=float, default=0.80)
    parser.add_argument("--gap", type=int, default=3)
    parser.add_argument("--futures-mode", action="store_true", help="Use futures multiplier, margin, and tick slippage.")
    parser.add_argument("--out-dir", default="", help="Optional directory for trades/equity/os logs.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = DS05BacktestConfig(
        initial_cash=args.initial_cash,
        lots=args.lots,
        commission_rate=args.commission_rate,
        slippage_ticks=args.slippage_ticks,
        atr_window=args.atr_window,
        extreme_atr_tol=args.extreme_atr_tol,
        gap=args.gap,
        futures_mode=args.futures_mode,
        spec=get_futures_spec(args.csv) if args.futures_mode else None,
    )
    df = load_ohlcv_for_engine(args.csv, config.atr_window)
    result = run_ds05_backtest(df, config)
    trades = result["trades"]
    equity = result["equity"]
    bad_trades = result["bad_trades"]

    final_equity = float(equity["equity"].iloc[-1]) if not equity.empty else config.initial_cash
    total_return = final_equity / config.initial_cash - 1.0
    mdd = max_drawdown(equity["equity"]) if not equity.empty else 0.0

    print("FengJi OS DS05 Backtest")
    print(f"Rows:          {len(df)}")
    if config.futures_mode and config.spec:
        print(f"Spec:          {config.spec.name} {config.spec.code}, multiplier={config.spec.multiplier}, tick={config.spec.tick_size}, margin={config.spec.margin_rate * 100:.1f}%")
    print(f"Lots:          {config.lots}")
    print(f"Fee rate:      {config.commission_rate * 10000:.2f}/10000")
    print(f"Slippage:      {config.slippage_ticks:.2f} tick(s)")
    print(f"Trades:        {len(trades)}")
    print(f"Bad trades:    {len(bad_trades)}")
    print(f"Final equity:  {final_equity:.2f}")
    print(f"Total return:  {total_return * 100:.2f}%")
    print(f"Max drawdown:  {mdd * 100:.2f}%")

    if args.out_dir:
        out_dir = Path(args.out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        for name in ["trades", "bad_trades", "equity", "raw_nodes", "identity_nodes", "turns", "os_log"]:
            frame = result[name]
            if isinstance(frame, pd.DataFrame):
                frame.to_csv(out_dir / f"{name}.csv", index=False)
        print(f"Saved DS05 result files to {out_dir}")


if __name__ == "__main__":
    main()
