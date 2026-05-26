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
from backtest_ds07 import load_frame, read_csv_with_fallback
from quant.ds07 import add_atr, attach_os_detail, prepare_datetime_ohlcv
from quant.ds09 import (
    assign_cn_futures_session_date,
    audit_ds09_structure,
    build_prev_day_boundary_map,
    check_stop,
    entry_fill,
    make_ds09_signal,
    update_ds09_stop,
)
from quant.futures_specs import FuturesSpec, get_futures_spec
from quant.metrics import max_drawdown


@dataclass(frozen=True)
class DS09BacktestConfig:
    initial_cash: float = 100_000.0
    lots: int = 1
    commission_rate: float = 0.0001
    slippage_ticks: float = 1.0
    atr_window: int = 14
    gap: int = 3
    futures_mode: bool = True
    spec: FuturesSpec | None = None


def as_ds05_config(config: DS09BacktestConfig):
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


def load_m15_frame(path: str | Path, atr_window: int) -> pd.DataFrame:
    raw = None
    for encoding in ["gbk", "gb18030", "utf-8-sig", "utf-8"]:
        try:
            raw = pd.read_csv(path, encoding=encoding)
            break
        except UnicodeDecodeError:
            continue
    if raw is None:
        raw = read_csv_with_fallback(path)
    if len(raw.columns) >= 7:
        first = raw.iloc[:, 0].astype(str).str.strip()
        second = raw.iloc[:, 1].astype(str).str.extract(r"(\d+)", expand=False).fillna("").str.zfill(4)
        parsed = pd.to_datetime(first + " " + second.str.slice(0, 2) + ":" + second.str.slice(2, 4), errors="coerce", format="mixed")
        numeric_open = pd.to_numeric(raw.iloc[:, 2], errors="coerce")
        valid = parsed.notna() & numeric_open.notna()
        if valid.any():
            out = pd.DataFrame(
                {
                    "date": parsed,
                    "open": numeric_open,
                    "high": pd.to_numeric(raw.iloc[:, 3], errors="coerce"),
                    "low": pd.to_numeric(raw.iloc[:, 4], errors="coerce"),
                    "close": pd.to_numeric(raw.iloc[:, 5], errors="coerce"),
                    "volume": pd.to_numeric(raw.iloc[:, 6], errors="coerce").fillna(0),
                }
            )
            out = out[valid].dropna(subset=["date", "open", "high", "low", "close"]).sort_values("date").drop_duplicates("date").reset_index(drop=True)
            return add_atr(out, atr_window)
    return add_atr(prepare_datetime_ohlcv(raw), atr_window)


def build_os_detail_frame(df: pd.DataFrame, gap: int):
    _, engine = build_os_frame(df, gap)
    return attach_os_detail(df, engine), engine


def load_m5_frame(path: str | Path, atr_window: int) -> pd.DataFrame:
    return load_m15_frame(path, atr_window)


def run_ds09_backtest(d1_df: pd.DataFrame, m15_df: pd.DataFrame, config: DS09BacktestConfig, symbol: str = "") -> dict:
    m15_with_session = assign_cn_futures_session_date(m15_df, d1_df)
    m15_os, m15_engine = build_os_detail_frame(m15_with_session, config.gap)
    boundary_map = build_prev_day_boundary_map(d1_df)
    ds05_config = as_ds05_config(config)
    cash = config.initial_cash
    position: dict | None = None
    trade_no = 0
    trades: list[dict] = []
    orders: list[dict] = []
    equity: list[dict] = []
    stop_history: list[dict] = []
    signals: list[dict] = []
    day_states: dict[pd.Timestamp, dict | None] = {}
    consumed_days = 0
    end_forced_close_count = 0

    for i in range(len(m15_os)):
        row = m15_os.iloc[i]
        date = row["date"]
        session_date = pd.to_datetime(row["session_date"]).normalize()
        exited = False

        if session_date not in day_states:
            if session_date in boundary_map:
                day_states[session_date] = {
                    **boundary_map[session_date],
                    "lock_idx": None,
                    "consumed": False,
                    "attack_idx": None,
                    "attack_price": None,
                    "defense_idx": None,
                    "defense_price": None,
                }
            else:
                day_states[session_date] = None
        day_state = day_states[session_date]

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
                        "session_date": position["session_date"],
                        "mode": position["mode"],
                        "d1_boundary": position["d1_boundary"],
                        "prev_open": position["prev_open"],
                        "prev_close": position["prev_close"],
                        "lock_idx": position["lock_idx"],
                        "attack_idx": position["attack_idx"],
                        "attack_price": position["attack_price"],
                        "defense_idx": position["defense_idx"],
                        "defense_price": position["defense_price"],
                    }
                )
                orders.append({"idx": i, "date": date, "trade_no": position["trade_no"], "order_status": "exit", "price": exit_price, "stop": position["stop"]})
                position = None
                exited = True

        if position is not None:
            position = update_ds09_stop(position, row)
            stop_history.append({"idx": i, "date": date, "trade_no": position["trade_no"], "side": position["side"], "stop": position["stop"]})

        if position is None and not exited and day_state is not None and not day_state.get("consumed", False):
            if day_state.get("lock_idx") is None:
                mode = day_state["mode"]
                boundary = float(day_state["boundary"])
                if mode == "LONG" and float(row["high"]) > boundary:
                    day_state["lock_idx"] = i
                elif mode == "SHORT" and float(row["low"]) < boundary:
                    day_state["lock_idx"] = i
            else:
                signal = make_ds09_signal(row, day_state, symbol=symbol)
                if signal is not None:
                    signal_dict = signal.to_dict()
                    signals.append(signal_dict)
                    consumed_days += 1
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
                        position = update_ds09_stop(position, row)
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
                                "session_date": signal.session_date,
                                "lock_idx": signal.lock_idx,
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

    if position is not None and len(m15_os) > 0:
        last_idx = len(m15_os) - 1
        row = m15_os.iloc[last_idx]
        side = int(position["side"])
        exit_price = apply_slippage(float(row["close"]), side, "exit", ds05_config)
        gross = position_pnl(position, exit_price, ds05_config)
        exit_fee = trade_fee(exit_price, ds05_config)
        net = gross - float(position["entry_fee"]) - exit_fee
        cash += gross - exit_fee
        end_forced_close_count += 1
        trades.append(
            {
                "trade_no": position["trade_no"],
                "direction": "long" if side == 1 else "short",
                "entry_idx": position["entry_idx"],
                "exit_idx": last_idx,
                "entry_date": position["entry_date"],
                "exit_date": row["date"],
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
                "exit_reason": "end_forced_close",
                "key": position["key"],
                "session_date": position["session_date"],
                "mode": position["mode"],
                "d1_boundary": position["d1_boundary"],
                "prev_open": position["prev_open"],
                "prev_close": position["prev_close"],
                "lock_idx": position["lock_idx"],
                "attack_idx": position["attack_idx"],
                "attack_price": position["attack_price"],
                "defense_idx": position["defense_idx"],
                "defense_price": position["defense_price"],
            }
        )
        equity.append({"date": row["date"], "equity": cash, "cash": cash, "unrealized": 0.0})

    trades_df = pd.DataFrame(trades)
    equity_df = pd.DataFrame(equity)
    if not equity_df.empty:
        equity_df["peak"] = equity_df["equity"].cummax()
        equity_df["drawdown"] = equity_df["equity"] / equity_df["peak"] - 1.0
    signals_df = pd.DataFrame(signals)
    return {
        "d1_df": d1_df,
        "m15_df": m15_os,
        "m15_engine": m15_engine,
        "m5_df": m15_os,
        "m5_engine": m15_engine,
        "signals": signals_df,
        "trades": trades_df,
        "bad_trades": audit_ds09_structure(trades_df),
        "orders": pd.DataFrame(orders),
        "stop_history": pd.DataFrame(stop_history),
        "equity": equity_df,
        "raw_nodes": m15_engine.export_raw_nodes(),
        "identity_nodes": m15_engine.export_tagged_nodes(),
        "turns": m15_engine.export_turns(),
        "os_log": m15_engine.export_os_log(),
        "debug": pd.DataFrame(
            [
                {
                    "consumed_days": consumed_days,
                    "closed_trades": len(trades_df),
                    "end_forced_close_count": end_forced_close_count,
                    "trade_consistency_ok": len(trades_df) == consumed_days,
                }
            ]
        ),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run FengJi OS DS09 D1/M15 white-list sniper backtest.")
    parser.add_argument("--d1-csv", required=True)
    parser.add_argument("--m15-csv", required=False)
    parser.add_argument("--m5-csv", required=False, help="Deprecated alias for --m15-csv.")
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
    intraday_arg = args.m15_csv or args.m5_csv
    if not intraday_arg:
        raise ValueError("DS09 requires --m15-csv.")
    m15_path = Path(intraday_arg)
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
    result = run_ds09_backtest(d1_df, m15_df, config, symbol=args.symbol or m15_path.stem)
    trades = result["trades"]
    equity = result["equity"]
    bad_trades = result["bad_trades"]
    final_equity = float(equity["equity"].iloc[-1]) if not equity.empty else config.initial_cash
    total_return = final_equity / config.initial_cash - 1.0
    mdd = max_drawdown(equity["equity"]) if not equity.empty else 0.0
    debug = result["debug"].iloc[0].to_dict()

    print("FengJi OS DS09 Backtest")
    print(f"D1 rows:       {len(d1_df)}")
    print(f"M15 rows:      {len(m15_df)}")
    if config.spec:
        print(f"Spec:          {config.spec.name} {config.spec.code}, multiplier={config.spec.multiplier}, tick={config.spec.tick_size}, margin={config.spec.margin_rate * 100:.1f}%")
    print(f"Signals:       {len(result['signals'])}")
    print(f"Trades:        {len(trades)}")
    print(f"Bad trades:    {len(bad_trades)}")
    print(f"Consistency:   {debug['trade_consistency_ok']}")
    print(f"Final equity:  {final_equity:.2f}")
    print(f"Total return:  {total_return * 100:.2f}%")
    print(f"Max drawdown:  {mdd * 100:.2f}%")

    if args.out_dir:
        out_dir = Path(args.out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        for name in ["signals", "trades", "bad_trades", "orders", "stop_history", "equity", "raw_nodes", "identity_nodes", "turns", "os_log", "debug"]:
            frame = result[name]
            if isinstance(frame, pd.DataFrame):
                frame.to_csv(out_dir / f"{name}.csv", index=False)
        print(f"Saved DS09 result files to {out_dir}")


if __name__ == "__main__":
    main()
