from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from backtest_ds05 import (
    apply_slippage,
    build_os_frame,
    contract_multiplier,
    required_margin,
    trade_fee,
)
from quant.data import load_ohlcv_for_engine
from quant.ds01 import ds01_left_filter_pass, entry_fill, exit_fill, make_ds01_pending
from quant.futures_specs import FuturesSpec, get_futures_spec
from quant.metrics import max_drawdown


@dataclass(frozen=True)
class DS01BacktestConfig:
    initial_cash: float = 100_000.0
    lots: int = 1
    max_entries: int = 3
    commission_rate: float = 0.0001
    slippage_ticks: float = 1.0
    left_lookback: int = 30
    atr_window: int = 14
    gap: int = 3
    stop_mode: str = "one_bar"
    futures_mode: bool = True
    spec: FuturesSpec | None = None


def as_ds05_config(config: DS01BacktestConfig):
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


def position_pnl(position: dict, exit_price: float, config: DS01BacktestConfig) -> float:
    side = int(position["side"])
    qty = int(position["total_lots"]) * contract_multiplier(as_ds05_config(config))
    entry = float(position["avg_entry_price"])
    if side == 1:
        return (exit_price - entry) * qty
    return (entry - exit_price) * qty


def add_leg(position: dict | None, leg: dict, stop_mode: str = "one_bar") -> dict:
    if position is None:
        return {
            "trade_no": leg["trade_no"],
            "side": leg["side"],
            "entry_idx": leg["entry_idx"],
            "entry_date": leg["entry_date"],
            "avg_entry_price": leg["entry_price"],
            "total_lots": leg["lots"],
            "entry_fee": leg["entry_fee"],
            "margin": leg["margin"],
            "entries": 1,
            "adds": 0,
            "legs": [leg],
            "stop": leg["stop"],
            "initial_stop": leg["stop"],
            "left_count": leg["left_count"],
            "camp_signal": leg["camp_signal"],
        }

    total_lots = int(position["total_lots"]) + int(leg["lots"])
    weighted = (
        float(position["avg_entry_price"]) * int(position["total_lots"])
        + float(leg["entry_price"]) * int(leg["lots"])
    ) / total_lots
    position["avg_entry_price"] = weighted
    position["total_lots"] = total_lots
    position["entry_fee"] = float(position["entry_fee"]) + float(leg["entry_fee"])
    position["margin"] = float(position["margin"]) + float(leg["margin"])
    position["entries"] = int(position["entries"]) + 1
    position["adds"] = int(position["adds"]) + 1
    position["legs"].append(leg)
    if stop_mode == "trigger":
        position["stop"] = leg["stop"]
    return position


def update_one_bar_stop(position: dict, row: pd.Series) -> dict:
    if int(position["side"]) == 1:
        position["stop"] = float(row["low"])
    else:
        position["stop"] = float(row["high"])
    return position


def audit_ds01_camp_direction(trades: pd.DataFrame) -> pd.DataFrame:
    if trades.empty:
        return trades.copy()
    bad_long = (trades["direction"] == "long") & (trades["camp_signal"] != 1)
    bad_short = (trades["direction"] == "short") & (trades["camp_signal"] != -1)
    return trades[bad_long | bad_short].copy()


def run_ds01_backtest(df: pd.DataFrame, config: DS01BacktestConfig) -> dict:
    os_df, engine = build_os_frame(df, config.gap)
    cash = config.initial_cash
    position: dict | None = None
    pending = None
    trade_no = 0
    trades: list[dict] = []
    orders: list[dict] = []
    equity: list[dict] = []
    ds05_config = as_ds05_config(config)

    for i in range(len(os_df)):
        row = os_df.iloc[i]
        date = row["date"]

        # 1. Pending order from yesterday triggers intraday today.
        if pending is not None and pending.trigger_idx == i:
            fill = entry_fill(row, pending.side, pending.trigger_price)
            if fill is not None:
                visible_idx = max(0, i - 1)
                hardened_visible = engine.hardened_by_bar[visible_idx] if engine.hardened_by_bar else []
                max_confirm_idx = max((node.confirm_idx for node in hardened_visible), default=-1)
                left_check_price = float(row["high"]) if pending.side == 1 else float(row["low"])
                left_ok, left_count = ds01_left_filter_pass(
                    hardened_visible,
                    i,
                    left_check_price,
                    pending.is_add,
                    config.left_lookback,
                )
                if left_ok and (position is None or int(position["side"]) == pending.side):
                    entry_price = apply_slippage(fill, pending.side, "entry", ds05_config)
                    entry_fee = trade_fee(entry_price, ds05_config)
                    margin = required_margin(entry_price, ds05_config)
                    if cash >= margin + entry_fee:
                        cash -= entry_fee
                        if position is None:
                            trade_no += 1
                        leg = {
                            "trade_no": trade_no,
                            "side": pending.side,
                            "entry_idx": i,
                            "entry_date": date,
                            "entry_price": entry_price,
                            "lots": config.lots,
                            "entry_fee": entry_fee,
                            "margin": margin,
                            "stop": pending.stop_price,
                            "signal_idx": pending.signal_idx,
                            "trigger_price": pending.trigger_price,
                            "left_count": left_count,
                            "left_check_price": left_check_price,
                            "visible_os_idx": visible_idx,
                            "max_hardened_confirm_idx_used": max_confirm_idx,
                            "future_violation": max_confirm_idx > i - 1,
                            "camp_signal": int(os_df.iloc[pending.signal_idx]["camp"]),
                            "is_add": pending.is_add,
                        }
                        position = add_leg(position, leg, config.stop_mode)
                        orders.append({**leg, "order_status": "filled"})
                    else:
                        orders.append({"idx": i, "date": date, "order_status": "cash_reject", "trigger_price": pending.trigger_price})
                else:
                    orders.append(
                        {
                            "idx": i,
                            "date": date,
                            "side": pending.side,
                            "order_status": "left_filter_reject",
                            "trigger_price": pending.trigger_price,
                            "left_check_price": left_check_price,
                            "left_count": left_count,
                            "visible_os_idx": visible_idx,
                            "max_hardened_confirm_idx_used": max_confirm_idx,
                            "future_violation": max_confirm_idx > i - 1,
                            "is_add": pending.is_add,
                        }
                    )
            pending = None

        # 2. Stop check after entry attempt. Same-bar entry then stop is allowed.
        if position is not None:
            stop_fill = exit_fill(row, int(position["side"]), float(position["stop"]))
            if stop_fill is not None and i >= int(position["entry_idx"]):
                exit_price = apply_slippage(stop_fill, int(position["side"]), "exit", ds05_config)
                gross = position_pnl(position, exit_price, config)
                exit_fee = trade_fee(exit_price, ds05_config) * int(position["total_lots"]) / config.lots
                net = gross - float(position["entry_fee"]) - exit_fee
                cash += gross - exit_fee
                trades.append(
                    {
                        "trade_no": position["trade_no"],
                        "direction": "long" if int(position["side"]) == 1 else "short",
                        "entry_idx": position["entry_idx"],
                        "exit_idx": i,
                        "entry_date": position["entry_date"],
                        "exit_date": date,
                        "avg_entry_price": position["avg_entry_price"],
                        "exit_price": exit_price,
                        "total_lots": position["total_lots"],
                        "entries": position["entries"],
                        "initial_stop": position["initial_stop"],
                        "final_stop": position["stop"],
                        "gross_pnl": gross,
                        "net_pnl": net,
                        "fee": float(position["entry_fee"]) + exit_fee,
                        "exit_reason": f"{config.stop_mode}_stop",
                        "left_count": position["left_count"],
                        "visible_os_idx": position["legs"][0]["visible_os_idx"],
                        "max_hardened_confirm_idx_used": max(
                            int(leg["max_hardened_confirm_idx_used"]) for leg in position["legs"]
                        ),
                        "future_violations": sum(int(bool(leg["future_violation"])) for leg in position["legs"]),
                        "camp_signal": position["camp_signal"],
                        "legs": list(position["legs"]),
                    }
                )
                position = None
            elif config.stop_mode == "one_bar":
                position = update_one_bar_stop(position, row)

        # 3. At close, create tomorrow setup from today's candle.
        if i + 1 < len(os_df):
            camp = int(row["camp"])
            pending = make_ds01_pending(os_df, i, camp, position, max_adds=config.max_entries - 1)

        unrealized = 0.0 if position is None else position_pnl(position, float(row["close"]), config)
        equity.append({"date": date, "equity": cash + unrealized, "cash": cash, "unrealized": unrealized})

    if position is not None:
        trades.append(
            {
                "trade_no": position["trade_no"],
                "direction": "long" if int(position["side"]) == 1 else "short",
                "entry_idx": position["entry_idx"],
                "exit_idx": pd.NA,
                "entry_date": position["entry_date"],
                "exit_date": pd.NaT,
                "avg_entry_price": position["avg_entry_price"],
                "exit_price": pd.NA,
                "total_lots": position["total_lots"],
                "entries": position["entries"],
                "initial_stop": position["initial_stop"],
                "final_stop": position["stop"],
                "gross_pnl": unrealized,
                "net_pnl": unrealized - float(position["entry_fee"]),
                "fee": float(position["entry_fee"]),
                "exit_reason": "open",
                "left_count": position["left_count"],
                "left_check_price": position["legs"][0].get("left_check_price"),
                "visible_os_idx": position["legs"][0]["visible_os_idx"],
                "max_hardened_confirm_idx_used": max(
                    int(leg["max_hardened_confirm_idx_used"]) for leg in position["legs"]
                ),
                "future_violations": sum(int(bool(leg["future_violation"])) for leg in position["legs"]),
                "camp_signal": position["camp_signal"],
                "legs": list(position["legs"]),
            }
        )

    trades_df = pd.DataFrame(trades)
    equity_df = pd.DataFrame(equity)
    if not equity_df.empty:
        equity_df["peak"] = equity_df["equity"].cummax()
        equity_df["drawdown"] = equity_df["equity"] / equity_df["peak"] - 1.0
    orders_df = pd.DataFrame(orders)

    return {
        "df": os_df,
        "engine": engine,
        "trades": trades_df,
        "orders": orders_df,
        "bad_trades": audit_ds01_camp_direction(trades_df),
        "equity": equity_df,
        "raw_nodes": engine.export_raw_nodes(),
        "identity_nodes": engine.export_tagged_nodes(),
        "turns": engine.export_turns(),
        "os_log": engine.export_os_log(),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run DS01 Cuogun futures backtest.")
    parser.add_argument("--csv", required=True)
    parser.add_argument("--initial-cash", type=float, default=100_000.0)
    parser.add_argument("--lots", type=int, default=1)
    parser.add_argument("--max-entries", type=int, default=3)
    parser.add_argument("--commission-rate", type=float, default=0.0001)
    parser.add_argument("--slippage-ticks", type=float, default=1.0)
    parser.add_argument("--left-lookback", type=int, default=30)
    parser.add_argument("--atr-window", type=int, default=14)
    parser.add_argument("--gap", type=int, default=3)
    parser.add_argument("--stop-mode", choices=["one_bar", "trigger"], default="one_bar")
    parser.add_argument("--out-dir", default="")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    csv_path = Path(args.csv)
    config = DS01BacktestConfig(
        initial_cash=args.initial_cash,
        lots=args.lots,
        max_entries=args.max_entries,
        commission_rate=args.commission_rate,
        slippage_ticks=args.slippage_ticks,
        left_lookback=args.left_lookback,
        atr_window=args.atr_window,
        gap=args.gap,
        stop_mode=args.stop_mode,
        futures_mode=True,
        spec=get_futures_spec(csv_path),
    )
    df = load_ohlcv_for_engine(csv_path, config.atr_window)
    result = run_ds01_backtest(df, config)
    trades = result["trades"]
    equity = result["equity"]
    bad = result["bad_trades"]
    final_equity = float(equity["equity"].iloc[-1]) if not equity.empty else config.initial_cash
    total_return = final_equity / config.initial_cash - 1.0
    mdd = max_drawdown(equity["equity"]) if not equity.empty else 0.0

    print("FengJi OS DS01 Backtest")
    print(f"Rows:          {len(df)}")
    if config.spec:
        print(f"Spec:          {config.spec.name} {config.spec.code}, multiplier={config.spec.multiplier}, tick={config.spec.tick_size}, margin={config.spec.margin_rate * 100:.1f}%")
    print(f"Trades:        {len(trades)}")
    print(f"Bad trades:    {len(bad)}")
    print(f"Final equity:  {final_equity:.2f}")
    print(f"Total return:  {total_return * 100:.2f}%")
    print(f"Max drawdown:  {mdd * 100:.2f}%")

    if args.out_dir:
        out_dir = Path(args.out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        for name, frame in result.items():
            if isinstance(frame, pd.DataFrame):
                frame.to_csv(out_dir / f"{name}.csv", index=False)
        print(f"Saved DS01 result files to {out_dir}")


if __name__ == "__main__":
    main()
