from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from batch_backtest_ds05_crypto import CRYPTO_LIST, fetch_crypto_okx
from backtest_ds01 import DS01BacktestConfig, audit_ds01_camp_direction
from backtest_ds05 import build_os_frame
from quant.ds01 import ds01_left_filter_pass, entry_fill, exit_fill, make_ds01_pending
from quant.metrics import max_drawdown


@dataclass(frozen=True)
class DS01CryptoConfig:
    initial_cash: float = 1_000.0
    margin_per_trade: float = 200.0
    leverage: float = 5.0
    fee_rate: float = 0.0005
    slippage_rate: float = 0.0003
    maintenance_margin_rate: float = 0.005
    max_entries: int = 3
    left_lookback: int = 30
    atr_window: int = 14
    gap: int = 3
    stop_mode: str = "one_bar"
    years: int = 5


def apply_slippage(price: float, side: int, action: str, slip: float) -> float:
    if action == "entry":
        return price * (1.0 + slip) if side == 1 else price * (1.0 - slip)
    return price * (1.0 - slip) if side == 1 else price * (1.0 + slip)


def liquidation_price(position: dict, config: DS01CryptoConfig) -> float:
    entry = float(position["avg_entry_price"])
    if int(position["side"]) == 1:
        return entry * (1.0 - 1.0 / config.leverage + config.maintenance_margin_rate)
    return entry * (1.0 + 1.0 / config.leverage - config.maintenance_margin_rate)


def check_liquidation(row: pd.Series, position: dict, config: DS01CryptoConfig) -> float | None:
    liq = liquidation_price(position, config)
    if int(position["side"]) == 1 and float(row["low"]) <= liq:
        return liq
    if int(position["side"]) == -1 and float(row["high"]) >= liq:
        return liq
    return None


def position_pnl(position: dict, exit_price: float) -> float:
    side = int(position["side"])
    qty = float(position["qty"])
    entry = float(position["avg_entry_price"])
    if side == 1:
        return (exit_price - entry) * qty
    return (entry - exit_price) * qty


def unrealized(position: dict | None, close: float) -> float:
    return 0.0 if position is None else position_pnl(position, close)


def add_leg(position: dict | None, leg: dict, stop_mode: str = "one_bar") -> dict:
    if position is None:
        return {
            "trade_no": leg["trade_no"],
            "side": leg["side"],
            "entry_idx": leg["entry_idx"],
            "entry_date": leg["entry_date"],
            "avg_entry_price": leg["entry_price"],
            "qty": leg["qty"],
            "margin": leg["margin"],
            "entry_fee": leg["entry_fee"],
            "entries": 1,
            "adds": 0,
            "legs": [leg],
            "stop": leg["stop"],
            "initial_stop": leg["stop"],
            "left_count": leg["left_count"],
            "camp_signal": leg["camp_signal"],
        }

    old_notional_qty = float(position["qty"])
    new_qty = old_notional_qty + float(leg["qty"])
    position["avg_entry_price"] = (
        float(position["avg_entry_price"]) * old_notional_qty + float(leg["entry_price"]) * float(leg["qty"])
    ) / new_qty
    position["qty"] = new_qty
    position["margin"] = float(position["margin"]) + float(leg["margin"])
    position["entry_fee"] = float(position["entry_fee"]) + float(leg["entry_fee"])
    position["entries"] = int(position["entries"]) + 1
    position["adds"] = int(position["adds"]) + 1
    position["legs"].append(leg)
    if stop_mode == "trigger":
        position["stop"] = leg["stop"]
    return position


def update_one_bar_stop(position: dict, row: pd.Series) -> dict:
    position["stop"] = float(row["low"]) if int(position["side"]) == 1 else float(row["high"])
    return position


def run_ds01_crypto_backtest(df: pd.DataFrame, config: DS01CryptoConfig) -> dict[str, pd.DataFrame]:
    os_df, engine = build_os_frame(df, config.gap)
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
                    entry_price = apply_slippage(fill, pending.side, "entry", config.slippage_rate)
                    margin = config.margin_per_trade
                    notional = margin * config.leverage
                    qty = notional / entry_price
                    fee = notional * config.fee_rate
                    if cash >= margin + fee:
                        cash -= fee
                        if position is None:
                            trade_no += 1
                        leg = {
                            "trade_no": trade_no,
                            "side": pending.side,
                            "entry_idx": i,
                            "entry_date": date,
                            "entry_price": entry_price,
                            "qty": qty,
                            "margin": margin,
                            "entry_fee": fee,
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
                        orders.append({"idx": i, "date": date, "order_status": "cash_reject"})
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

        if position is not None:
            liq = check_liquidation(row, position, config)
            exit_price = None
            exit_reason = None
            gross = 0.0
            exit_fee = 0.0
            net = 0.0
            if liq is not None:
                exit_price = liq
                exit_reason = "liquidation"
                gross = net = -float(position["margin"])
            else:
                stop_fill = exit_fill(row, int(position["side"]), float(position["stop"]))
                if stop_fill is not None and i >= int(position["entry_idx"]):
                    exit_price = apply_slippage(stop_fill, int(position["side"]), "exit", config.slippage_rate)
                    gross = position_pnl(position, exit_price)
                    exit_fee = abs(exit_price * float(position["qty"])) * config.fee_rate
                    net = gross - float(position["entry_fee"]) - exit_fee
                    exit_reason = f"{config.stop_mode}_stop"

            if exit_price is not None:
                cash += net
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
                        "qty": position["qty"],
                        "margin": position["margin"],
                        "entries": position["entries"],
                        "initial_stop": position["initial_stop"],
                        "final_stop": position["stop"],
                        "gross_pnl": gross,
                        "net_pnl": net,
                        "fee": float(position["entry_fee"]) + exit_fee,
                        "exit_reason": exit_reason,
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

        if i + 1 < len(os_df):
            pending = make_ds01_pending(
                os_df,
                i,
                int(row["camp"]),
                position,
                max_adds=config.max_entries - 1,
            )

        equity.append({"date": date, "equity": cash + unrealized(position, float(row["close"])), "cash": cash})

    if position is not None:
        mark = float(os_df.iloc[-1]["close"])
        open_unrealized = position_pnl(position, mark)
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
                "qty": position["qty"],
                "margin": position["margin"],
                "entries": position["entries"],
                "initial_stop": position["initial_stop"],
                "final_stop": position["stop"],
                "gross_pnl": open_unrealized,
                "net_pnl": open_unrealized - float(position["entry_fee"]),
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
    orders_df = pd.DataFrame(orders)
    equity_df = pd.DataFrame(equity)
    if not equity_df.empty:
        equity_df["peak"] = equity_df["equity"].cummax()
        equity_df["drawdown"] = equity_df["equity"] / equity_df["peak"] - 1.0
    return {
        "df": os_df,
        "trades": trades_df,
        "orders": orders_df,
        "bad_trades": audit_ds01_camp_direction(trades_df),
        "equity": equity_df,
        "raw_nodes": engine.export_raw_nodes(),
        "identity_nodes": engine.export_tagged_nodes(),
        "turns": engine.export_turns(),
        "os_log": engine.export_os_log(),
    }


def no_future_violations(trades: pd.DataFrame) -> int:
    if trades.empty:
        return 0
    if "future_violations" in trades:
        return int(trades["future_violations"].sum())
    return int((trades["max_hardened_confirm_idx_used"] > trades["entry_idx"] - 1).sum())


def summarize(symbol: str, name: str, result: dict[str, pd.DataFrame], config: DS01CryptoConfig) -> dict:
    trades = result["trades"]
    equity = result["equity"]
    final_equity = float(equity["equity"].iloc[-1]) if not equity.empty else config.initial_cash
    total_return = final_equity / config.initial_cash - 1.0
    wins = int((trades["net_pnl"] > 0).sum()) if not trades.empty else 0
    trade_count = int(len(trades))
    return {
        "symbol": symbol,
        "name": name,
        "rows": int(len(result["df"])),
        "trades": trade_count,
        "wins": wins,
        "win_rate": wins / trade_count if trade_count else 0.0,
        "bad_trades": int(len(result["bad_trades"])),
        "future_violations": no_future_violations(trades),
        "liquidations": int((trades["exit_reason"] == "liquidation").sum()) if not trades.empty else 0,
        "net_pnl": float(trades["net_pnl"].sum()) if not trades.empty else 0.0,
        "final_equity": final_equity,
        "total_return": total_return,
        "max_drawdown": max_drawdown(equity["equity"]) if not equity.empty else 0.0,
    }


def save_frames(out_dir: Path, result: dict[str, pd.DataFrame]) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    for name, frame in result.items():
        if isinstance(frame, pd.DataFrame):
            frame.to_csv(out_dir / f"{name}.csv", index=False)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Batch run DS01 on hot crypto daily data.")
    parser.add_argument("--out-dir", default="results/ds01_crypto_hot_okx")
    parser.add_argument("--years", type=int, default=5)
    parser.add_argument("--initial-cash", type=float, default=1_000.0)
    parser.add_argument("--margin-per-trade", type=float, default=200.0)
    parser.add_argument("--leverage", type=float, default=5.0)
    parser.add_argument("--fee-rate", type=float, default=0.0005)
    parser.add_argument("--slippage-rate", type=float, default=0.0003)
    parser.add_argument("--maintenance-margin-rate", type=float, default=0.005)
    parser.add_argument("--max-entries", type=int, default=3)
    parser.add_argument("--left-lookback", type=int, default=30)
    parser.add_argument("--atr-window", type=int, default=14)
    parser.add_argument("--gap", type=int, default=3)
    parser.add_argument("--stop-mode", choices=["one_bar", "trigger"], default="one_bar")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = DS01CryptoConfig(
        initial_cash=args.initial_cash,
        margin_per_trade=args.margin_per_trade,
        leverage=args.leverage,
        fee_rate=args.fee_rate,
        slippage_rate=args.slippage_rate,
        maintenance_margin_rate=args.maintenance_margin_rate,
        max_entries=args.max_entries,
        left_lookback=args.left_lookback,
        atr_window=args.atr_window,
        gap=args.gap,
        stop_mode=args.stop_mode,
        years=args.years,
    )
    out_dir = Path(args.out_dir)
    summaries = []
    errors = []
    for symbol, name in CRYPTO_LIST.items():
        try:
            df = fetch_crypto_okx(symbol, config.years, config.atr_window)
            result = run_ds01_crypto_backtest(df, config)
            save_frames(out_dir / name, result)
            row = summarize(symbol, name, result, config)
            summaries.append(row)
            print(
                f"{name}: trades={row['trades']} bad={row['bad_trades']} "
                f"future={row['future_violations']} liq={row['liquidations']} "
                f"return={row['total_return'] * 100:.2f}% mdd={row['max_drawdown'] * 100:.2f}%"
            )
        except Exception as exc:
            errors.append({"symbol": symbol, "name": name, "error": repr(exc)})
            print(f"{name}: ERROR {exc}")

    out_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(summaries).sort_values(["bad_trades", "future_violations", "total_return"], ascending=[True, True, False]).to_csv(out_dir / "summary.csv", index=False)
    pd.DataFrame(errors).to_csv(out_dir / "errors.csv", index=False)
    print("")
    print(f"Files processed: {len(CRYPTO_LIST)}")
    print(f"Succeeded:       {len(summaries)}")
    print(f"Failed:          {len(errors)}")
    print(f"Summary:         {out_dir / 'summary.csv'}")


if __name__ == "__main__":
    main()
