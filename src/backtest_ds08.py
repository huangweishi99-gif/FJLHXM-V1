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
from backtest_ds07 import load_frame
from quant.ds08 import (
    audit_ds08_structure,
    check_stop,
    entry_fill,
    make_ds08_signal,
    update_ds08_stop,
)
from quant.futures_specs import FuturesSpec, get_futures_spec
from quant.metrics import max_drawdown


@dataclass(frozen=True)
class DS08BacktestConfig:
    initial_cash: float = 100_000.0
    lots: int = 1
    commission_rate: float = 0.0001
    slippage_ticks: float = 1.0
    atr_window: int = 14
    gap: int = 3
    futures_mode: bool = True
    spec: FuturesSpec | None = None


def as_ds05_config(config: DS08BacktestConfig):
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


def run_ds08_backtest(df: pd.DataFrame, config: DS08BacktestConfig, symbol: str = "") -> dict:
    os_df, engine = build_os_frame(df, config.gap)
    ds05_config = as_ds05_config(config)
    cash = config.initial_cash
    position: dict | None = None
    trade_no = 0
    trades: list[dict] = []
    orders: list[dict] = []
    equity: list[dict] = []
    stop_history: list[dict] = []
    signals: list[dict] = []
    used_keys: set[str] = set()

    for i in range(len(os_df)):
        row = os_df.iloc[i]
        date = row["date"]
        skeleton = engine.hardened_by_bar[i] if i < len(engine.hardened_by_bar) else []
        exited = False

        if position is not None and i > int(position["entry_idx"]):
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
                        "key": position["key"],
                        "attack_idx": position["attack_idx"],
                        "attack_price": position["attack_price"],
                        "defense_idx": position["defense_idx"],
                        "defense_price": position["defense_price"],
                        "n1_idx": position["n1_idx"],
                        "n1_price": position["n1_price"],
                        "n1_type": position["n1_type"],
                        "n2_idx": position["n2_idx"],
                        "n2_price": position["n2_price"],
                        "n2_type": position["n2_type"],
                        "n3_idx": position["n3_idx"],
                        "n3_price": position["n3_price"],
                        "n3_type": position["n3_type"],
                        "n4_idx": position["n4_idx"],
                        "n4_price": position["n4_price"],
                        "n4_type": position["n4_type"],
                        "n5_idx": position["n5_idx"],
                        "n5_confirm_idx": position["n5_confirm_idx"],
                        "n5_price": position["n5_price"],
                        "n5_type": position["n5_type"],
                    }
                )
                orders.append({"idx": i, "date": date, "trade_no": position["trade_no"], "order_status": "exit", "price": exit_price, "stop": position["stop"]})
                position = None
                exited = True

        if position is not None:
            position = update_ds08_stop(position, skeleton)
            stop_history.append({"idx": i, "date": date, "trade_no": position["trade_no"], "side": position["side"], "stop": position["stop"]})

        if position is None and not exited:
            signal = make_ds08_signal(os_df, i, skeleton, used_keys, symbol=symbol)
            if signal is not None:
                signal_dict = signal.to_dict()
                signals.append(signal_dict)
                side = signal.side
                fill = entry_fill(row, signal)
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
                        "stop": signal.initial_stop,
                        "initial_stop": signal.initial_stop,
                        "entry_fee": entry_fee,
                        **signal_dict,
                    }
                    position = update_ds08_stop(position, skeleton)
                    stop_history.append({"idx": i, "date": date, "trade_no": trade_no, "side": side, "stop": position["stop"]})
                    orders.append(
                        {
                            "idx": i,
                            "date": date,
                            "trade_no": trade_no,
                            "order_status": "entry",
                            "side": side,
                            "price": entry_price,
                            "key": signal.key,
                            "attack_idx": signal.attack_idx,
                            "attack_price": signal.attack_price,
                            "defense_idx": signal.defense_idx,
                            "defense_price": signal.defense_price,
                        }
                    )
                else:
                    orders.append({"idx": i, "date": date, "order_status": "cash_reject", "side": side, "key": signal.key})

        unrealized = 0.0 if position is None else position_pnl(position, float(row["close"]), ds05_config)
        equity.append({"date": date, "equity": cash + unrealized, "cash": cash, "unrealized": unrealized})

    trades_df = pd.DataFrame(trades)
    equity_df = pd.DataFrame(equity)
    if not equity_df.empty:
        equity_df["peak"] = equity_df["equity"].cummax()
        equity_df["drawdown"] = equity_df["equity"] / equity_df["peak"] - 1.0
    return {
        "df": os_df,
        "engine": engine,
        "signals": pd.DataFrame(signals),
        "trades": trades_df,
        "bad_trades": audit_ds08_structure(trades_df),
        "orders": pd.DataFrame(orders),
        "stop_history": pd.DataFrame(stop_history),
        "equity": equity_df,
        "raw_nodes": engine.export_raw_nodes(),
        "identity_nodes": engine.export_tagged_nodes(),
        "turns": engine.export_turns(),
        "os_log": engine.export_os_log(),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run FengJi OS DS08 power-seizure backtest.")
    parser.add_argument("--csv", required=True)
    parser.add_argument("--symbol", default="")
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
    result = run_ds08_backtest(df, config, symbol=args.symbol or csv_path.stem)
    trades = result["trades"]
    equity = result["equity"]
    bad_trades = result["bad_trades"]
    final_equity = float(equity["equity"].iloc[-1]) if not equity.empty else config.initial_cash
    total_return = final_equity / config.initial_cash - 1.0
    mdd = max_drawdown(equity["equity"]) if not equity.empty else 0.0

    print("FengJi OS DS08 Backtest")
    print(f"Rows:          {len(df)}")
    if config.spec:
        print(f"Spec:          {config.spec.name} {config.spec.code}, multiplier={config.spec.multiplier}, tick={config.spec.tick_size}, margin={config.spec.margin_rate * 100:.1f}%")
    print(f"Signals:       {len(result['signals'])}")
    print(f"Trades:        {len(trades)}")
    print(f"Bad trades:    {len(bad_trades)}")
    print(f"Final equity:  {final_equity:.2f}")
    print(f"Total return:  {total_return * 100:.2f}%")
    print(f"Max drawdown:  {mdd * 100:.2f}%")

    if args.out_dir:
        out_dir = Path(args.out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        for name in ["signals", "trades", "bad_trades", "orders", "stop_history", "equity", "raw_nodes", "identity_nodes", "turns", "os_log"]:
            frame = result[name]
            if isinstance(frame, pd.DataFrame):
                frame.to_csv(out_dir / f"{name}.csv", index=False)
        print(f"Saved DS08 result files to {out_dir}")


if __name__ == "__main__":
    main()
