from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from backtest_ds05 import (
    apply_slippage,
    build_os_frame,
    contract_multiplier,
    position_pnl,
    required_margin,
    trade_fee,
)
from quant.data import load_ohlcv_for_engine
from quant.ds02 import audit_ds02_camp_direction, check_stop, make_ds02_signal, update_ds02_stop
from quant.futures_specs import FuturesSpec, get_futures_spec
from quant.metrics import max_drawdown


@dataclass(frozen=True)
class DS02BacktestConfig:
    initial_cash: float = 100_000.0
    lots: int = 1
    commission_rate: float = 0.0001
    slippage_ticks: float = 1.0
    atr_window: int = 14
    gap: int = 3
    futures_mode: bool = True
    spec: FuturesSpec | None = None


def as_ds05_config(config: DS02BacktestConfig):
    from backtest_ds05 import DS05BacktestConfig

    return DS05BacktestConfig(
        initial_cash=config.initial_cash,
        lots=config.lots,
        commission_rate=config.commission_rate,
        slippage_ticks=config.slippage_ticks,
        atr_window=config.atr_window,
        gap=config.gap,
        futures_mode=config.futures_mode,
        spec=config.spec,
    )


def run_ds02_backtest(df: pd.DataFrame, config: DS02BacktestConfig) -> dict:
    os_df, engine = build_os_frame(df, config.gap)
    ds05_config = as_ds05_config(config)
    cash = config.initial_cash
    position: dict | None = None
    pending = None
    trade_no = 0
    trades: list[dict] = []
    orders: list[dict] = []
    equity: list[dict] = []

    for i in range(len(os_df)):
        row = os_df.iloc[i]
        date = row["date"]

        if position is not None and i >= int(position["entry_idx"]):
            side = int(position["side"])
            exit_price, exit_reason = check_stop(row, position)
            if exit_price is not None:
                exit_price = apply_slippage(exit_price, side, "exit", ds05_config)
                gross = position_pnl(position, exit_price, ds05_config)
                exit_fee = trade_fee(exit_price, ds05_config)
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
                        "camp_k1": position["camp_k1"],
                        "camp_k2": position["camp_k2"],
                        "signal_camp": position["signal_camp"],
                    }
                )
                orders.append({"idx": i, "date": date, "trade_no": position["trade_no"], "order_status": "exit", "price": exit_price})
                position = None
                pending = None
            else:
                position = update_ds02_stop(position, row)

        if pending is not None and pending.activate_idx == i and position is None:
            side = pending.side
            fill = float(row["open"])
            entry_price = apply_slippage(fill, side, "entry", ds05_config)
            entry_fee = trade_fee(entry_price, ds05_config)
            margin = required_margin(entry_price, ds05_config)
            if cash >= margin + entry_fee:
                cash -= entry_fee
                trade_no += 1
                position = {
                    "trade_no": trade_no,
                    "side": side,
                    "entry_idx": i,
                    "entry_date": date,
                    "entry_price": entry_price,
                    "lots": config.lots,
                    "multiplier": contract_multiplier(ds05_config),
                    "margin": margin,
                    "stop": pending.initial_stop,
                    "initial_stop": pending.initial_stop,
                    "entry_fee": entry_fee,
                    "pattern": pending.pattern,
                    "k1": pending.k1,
                    "k2": pending.k2,
                    "camp_k1": pending.camp_k1,
                    "camp_k2": pending.camp_k2,
                    "signal_camp": pending.signal_camp,
                }
                orders.append(
                    {
                        "idx": i,
                        "date": date,
                        "trade_no": trade_no,
                        "order_status": "entry",
                        "side": side,
                        "price": entry_price,
                        "initial_stop": pending.initial_stop,
                        "k1": pending.k1,
                        "k2": pending.k2,
                        "camp_k1": pending.camp_k1,
                        "camp_k2": pending.camp_k2,
                    }
                )
            else:
                orders.append({"idx": i, "date": date, "order_status": "cash_reject", "side": side})
            pending = None

        if pending is None and position is None:
            pending = make_ds02_signal(os_df, i)

        unrealized = 0.0 if position is None else position_pnl(position, float(row["close"]), ds05_config)
        equity.append({"date": date, "equity": cash + unrealized, "cash": cash, "unrealized": unrealized})

    trades_df = pd.DataFrame(trades)
    equity_df = pd.DataFrame(equity)
    if not equity_df.empty:
        equity_df["peak"] = equity_df["equity"].cummax()
        equity_df["drawdown"] = equity_df["equity"] / equity_df["peak"] - 1.0
    orders_df = pd.DataFrame(orders)
    return {
        "df": os_df,
        "engine": engine,
        "raw_nodes": engine.export_raw_nodes(),
        "identity_nodes": engine.export_tagged_nodes(),
        "turns": engine.export_turns(),
        "os_log": engine.export_os_log(),
        "trades": trades_df,
        "bad_trades": audit_ds02_camp_direction(trades_df),
        "orders": orders_df,
        "equity": equity_df,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run FengJi OS DS02 Yin-Yang Eats backtest.")
    parser.add_argument("--csv", required=True)
    parser.add_argument("--initial-cash", type=float, default=100_000.0)
    parser.add_argument("--lots", type=int, default=1)
    parser.add_argument("--commission-rate", type=float, default=0.0001)
    parser.add_argument("--slippage-ticks", type=float, default=1.0)
    parser.add_argument("--atr-window", type=int, default=14)
    parser.add_argument("--gap", type=int, default=3)
    parser.add_argument("--out-dir", default="")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    csv_path = Path(args.csv)
    config = DS02BacktestConfig(
        initial_cash=args.initial_cash,
        lots=args.lots,
        commission_rate=args.commission_rate,
        slippage_ticks=args.slippage_ticks,
        atr_window=args.atr_window,
        gap=args.gap,
        futures_mode=True,
        spec=get_futures_spec(csv_path),
    )
    df = load_ohlcv_for_engine(csv_path, config.atr_window)
    result = run_ds02_backtest(df, config)
    trades = result["trades"]
    equity = result["equity"]
    bad_trades = result["bad_trades"]
    final_equity = float(equity["equity"].iloc[-1]) if not equity.empty else config.initial_cash
    total_return = final_equity / config.initial_cash - 1.0
    mdd = max_drawdown(equity["equity"]) if not equity.empty else 0.0

    print("FengJi OS DS02 Backtest")
    print(f"Rows:          {len(df)}")
    if config.spec:
        print(f"Spec:          {config.spec.name} {config.spec.code}, multiplier={config.spec.multiplier}, tick={config.spec.tick_size}, margin={config.spec.margin_rate * 100:.1f}%")
    print(f"Trades:        {len(trades)}")
    print(f"Bad trades:    {len(bad_trades)}")
    print(f"Final equity:  {final_equity:.2f}")
    print(f"Total return:  {total_return * 100:.2f}%")
    print(f"Max drawdown:  {mdd * 100:.2f}%")

    if args.out_dir:
        out_dir = Path(args.out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        for name in ["trades", "bad_trades", "orders", "equity", "raw_nodes", "identity_nodes", "turns", "os_log"]:
            frame = result[name]
            if isinstance(frame, pd.DataFrame):
                frame.to_csv(out_dir / f"{name}.csv", index=False)
        print(f"Saved DS02 result files to {out_dir}")


if __name__ == "__main__":
    main()
