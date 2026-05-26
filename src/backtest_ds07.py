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
from quant.ds07 import (
    add_atr,
    attach_os_detail,
    audit_ds07_structure,
    check_stop,
    entry_fill,
    make_ds07_signal,
    map_d1_to_h1_future,
    prepare_datetime_ohlcv,
    update_ds07_stop,
)
from quant.futures_specs import FuturesSpec, get_futures_spec
from quant.metrics import max_drawdown


@dataclass(frozen=True)
class DS07BacktestConfig:
    initial_cash: float = 100_000.0
    lots: int = 1
    commission_rate: float = 0.0001
    slippage_ticks: float = 1.0
    atr_window: int = 14
    gap: int = 3
    futures_mode: bool = True
    spec: FuturesSpec | None = None


def as_ds05_config(config: DS07BacktestConfig):
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


def read_csv_with_fallback(path: str | Path) -> pd.DataFrame:
    last_error: Exception | None = None
    for encoding in ["utf-8-sig", "utf-8", "gbk", "gb18030"]:
        try:
            return pd.read_csv(path, encoding=encoding)
        except UnicodeDecodeError as exc:
            last_error = exc
    if last_error is not None:
        raise last_error
    return pd.read_csv(path)


def load_frame(path: str | Path, atr_window: int) -> pd.DataFrame:
    return add_atr(prepare_datetime_ohlcv(read_csv_with_fallback(path)), atr_window)


def build_os_detail_frame(df: pd.DataFrame, gap: int):
    _, engine = build_os_frame(df, gap)
    return attach_os_detail(df, engine), engine


def run_ds07_backtest(d1_df: pd.DataFrame, h1_df: pd.DataFrame, config: DS07BacktestConfig, symbol: str = "") -> dict:
    d1_os, d1_engine = build_os_detail_frame(d1_df, config.gap)
    h1_os, h1_engine = build_os_detail_frame(h1_df, config.gap)
    h1 = map_d1_to_h1_future(d1_os, h1_os)
    ds05_config = as_ds05_config(config)
    cash = config.initial_cash
    position: dict | None = None
    trade_no = 0
    trades: list[dict] = []
    orders: list[dict] = []
    equity: list[dict] = []
    stop_history: list[dict] = []
    signal_rows: list[dict] = []
    used_attack_keys: set[str] = set()

    for i in range(len(h1)):
        row = h1.iloc[i]
        date = row["date"]
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
                        "trigger_type": position["trigger_type"],
                        "exit_reason": exit_reason,
                        "d1_camp": position["d1_camp"],
                        "prev_h1_camp": position["prev_h1_camp"],
                        "h1_camp": position["h1_camp"],
                        "attack_idx": position["attack_idx"],
                        "attack_price": position["attack_price"],
                        "defense_idx": position["defense_idx"],
                        "defense_price": position["defense_price"],
                        "attack_key": position["attack_key"],
                        "session_date": position["session_date"],
                    }
                )
                orders.append({"idx": i, "date": date, "trade_no": position["trade_no"], "order_status": "exit", "price": exit_price, "stop": position["stop"]})
                position = None
                exited = True

        if position is not None:
            position = update_ds07_stop(position, row)
            stop_history.append({"idx": i, "date": date, "trade_no": position["trade_no"], "side": position["side"], "stop": position["stop"]})

        if position is None and not exited:
            prev_row = h1.iloc[i - 1] if i > 0 else None
            signal = make_ds07_signal(row, i, used_attack_keys, symbol=symbol, prev_row=prev_row)
            if signal is not None:
                used_attack_keys.add(signal.attack_key)
                signal_rows.append(signal.to_dict())
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
                        "pattern": signal.pattern,
                        "trigger_type": signal.trigger_type,
                        "d1_camp": signal.d1_camp,
                        "prev_h1_camp": signal.prev_h1_camp,
                        "h1_camp": signal.h1_camp,
                        "attack_idx": signal.attack_idx,
                        "attack_price": signal.attack_price,
                        "defense_idx": signal.defense_idx,
                        "defense_price": signal.defense_price,
                        "attack_key": signal.attack_key,
                        "session_date": signal.session_date,
                    }
                    position = update_ds07_stop(position, row)
                    stop_history.append({"idx": i, "date": date, "trade_no": trade_no, "side": side, "stop": position["stop"]})
                    orders.append(
                        {
                            "idx": i,
                            "date": date,
                            "trade_no": trade_no,
                            "order_status": "entry",
                            "side": side,
                            "price": entry_price,
                            "attack_idx": signal.attack_idx,
                            "attack_price": signal.attack_price,
                            "defense_idx": signal.defense_idx,
                            "defense_price": signal.defense_price,
                            "d1_camp": signal.d1_camp,
                            "prev_h1_camp": signal.prev_h1_camp,
                            "h1_camp": signal.h1_camp,
                            "trigger_type": signal.trigger_type,
                            "attack_key": signal.attack_key,
                            "session_date": signal.session_date,
                        }
                    )
                else:
                    orders.append({"idx": i, "date": date, "order_status": "cash_reject", "side": side, "attack_key": signal.attack_key})

        unrealized = 0.0 if position is None else position_pnl(position, float(row["close"]), ds05_config)
        equity.append({"date": date, "equity": cash + unrealized, "cash": cash, "unrealized": unrealized})

    trades_df = pd.DataFrame(trades)
    equity_df = pd.DataFrame(equity)
    if not equity_df.empty:
        equity_df["peak"] = equity_df["equity"].cummax()
        equity_df["drawdown"] = equity_df["equity"] / equity_df["peak"] - 1.0

    return {
        "d1_df": d1_os,
        "h1_df": h1,
        "d1_engine": d1_engine,
        "h1_engine": h1_engine,
        "signals": pd.DataFrame(signal_rows),
        "trades": trades_df,
        "bad_trades": audit_ds07_structure(trades_df),
        "orders": pd.DataFrame(orders),
        "stop_history": pd.DataFrame(stop_history),
        "equity": equity_df,
        "d1_raw_nodes": d1_engine.export_raw_nodes(),
        "h1_raw_nodes": h1_engine.export_raw_nodes(),
        "d1_identity_nodes": d1_engine.export_tagged_nodes(),
        "h1_identity_nodes": h1_engine.export_tagged_nodes(),
        "d1_turns": d1_engine.export_turns(),
        "h1_turns": h1_engine.export_turns(),
        "d1_os_log": d1_engine.export_os_log(),
        "h1_os_log": h1_engine.export_os_log(),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run FengJi OS DS07 D1/H1 resonance backtest.")
    parser.add_argument("--d1-csv", required=True)
    parser.add_argument("--h1-csv", required=True)
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
    d1_path = Path(args.d1_csv)
    h1_path = Path(args.h1_csv)
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
    result = run_ds07_backtest(d1_df, h1_df, config, symbol=args.symbol or d1_path.stem)
    trades = result["trades"]
    equity = result["equity"]
    bad_trades = result["bad_trades"]
    final_equity = float(equity["equity"].iloc[-1]) if not equity.empty else config.initial_cash
    total_return = final_equity / config.initial_cash - 1.0
    mdd = max_drawdown(equity["equity"]) if not equity.empty else 0.0

    print("FengJi OS DS07 Backtest")
    print(f"D1 rows:       {len(d1_df)}")
    print(f"H1 rows:       {len(h1_df)}")
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
        print(f"Saved DS07 result files to {out_dir}")


if __name__ == "__main__":
    main()
