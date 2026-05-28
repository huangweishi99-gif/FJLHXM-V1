from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
import requests

from backtest_ds05 import DS05BacktestConfig, build_os_frame
from quant.data import add_atr
from quant.ds05 import audit_ds05_camp_direction, check_stop, make_ds05_signal, update_ds05_stop
from quant.metrics import max_drawdown


CRYPTO_LIST = {
    "BTC-USDT": "BTC",
    "ETH-USDT": "ETH",
    "SOL-USDT": "SOL",
    "BNB-USDT": "BNB",
    "XRP-USDT": "XRP",
    "ADA-USDT": "ADA",
    "DOGE-USDT": "DOGE",
    "AVAX-USDT": "AVAX",
    "LTC-USDT": "LTC",
    "LINK-USDT": "LINK",
}


@dataclass(frozen=True)
class CryptoBacktestConfig:
    initial_cash: float = 1_000.0
    margin_per_trade: float = 200.0
    leverage: float = 5.0
    fee_rate: float = 0.0005
    slippage_rate: float = 0.0003
    maintenance_margin_rate: float = 0.005
    atr_window: int = 14
    extreme_atr_tol: float = 0.80
    gap: int = 3
    years: int = 5


def fetch_crypto_okx(inst_id: str, years: int, atr_window: int) -> pd.DataFrame:
    url = "https://www.okx.com/api/v5/market/history-candles"
    start_date = pd.Timestamp.utcnow().tz_localize(None) - pd.DateOffset(years=years)
    rows: list[list[str]] = []
    cursor: str | None = None
    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0"})

    while True:
        params = {"instId": inst_id, "bar": "1Dutc", "limit": "100"}
        if cursor:
            params["after"] = cursor
        response = session.get(url, params=params, timeout=30)
        response.raise_for_status()
        payload = response.json()
        if payload.get("code") != "0":
            raise ValueError(f"OKX error for {inst_id}: {payload}")
        batch = payload.get("data", [])
        if not batch:
            break
        rows.extend(batch)
        oldest_ts = int(batch[-1][0])
        oldest_date = pd.to_datetime(oldest_ts, unit="ms")
        cursor = batch[-1][0]
        if oldest_date <= start_date or len(batch) < 100:
            break

    if not rows:
        raise ValueError(f"No data downloaded for {inst_id}")

    frame = pd.DataFrame(rows, columns=["ts", "open", "high", "low", "close", "volume", "vol_ccy", "vol_ccy_quote", "confirm"])
    frame["date"] = pd.to_datetime(pd.to_numeric(frame["ts"]), unit="ms")
    for col in ["open", "high", "low", "close", "volume"]:
        frame[col] = pd.to_numeric(frame[col], errors="coerce")
    frame = frame[frame["date"] >= start_date]
    frame = frame[["date", "open", "high", "low", "close", "volume"]].dropna().drop_duplicates("date").sort_values("date").reset_index(drop=True)
    return add_atr(frame, atr_window)


def apply_slippage(price: float, side: int, action: str, slip: float) -> float:
    if action == "entry":
        return price * (1.0 + slip) if side == 1 else price * (1.0 - slip)
    return price * (1.0 - slip) if side == 1 else price * (1.0 + slip)


def liquidation_price(position: dict, config: CryptoBacktestConfig) -> float:
    entry = float(position["entry_price"])
    if int(position["side"]) == 1:
        return entry * (1.0 - 1.0 / config.leverage + config.maintenance_margin_rate)
    return entry * (1.0 + 1.0 / config.leverage - config.maintenance_margin_rate)


def check_liquidation(row: pd.Series, position: dict, config: CryptoBacktestConfig) -> float | None:
    liq = liquidation_price(position, config)
    if int(position["side"]) == 1 and float(row["low"]) <= liq:
        return liq
    if int(position["side"]) == -1 and float(row["high"]) >= liq:
        return liq
    return None


def unrealized(position: dict | None, close: float) -> float:
    if position is None:
        return 0.0
    side = int(position["side"])
    qty = float(position["qty"])
    entry = float(position["entry_price"])
    if side == 1:
        return (close - entry) * qty
    return (entry - close) * qty


def run_crypto_backtest(df: pd.DataFrame, config: CryptoBacktestConfig) -> dict[str, pd.DataFrame]:
    os_config = DS05BacktestConfig(atr_window=config.atr_window, extreme_atr_tol=config.extreme_atr_tol, gap=config.gap)
    os_df, engine = build_os_frame(df, os_config.gap)
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
                entry_price = apply_slippage(signal.entry_price, side, "entry", config.slippage_rate)
                margin = config.margin_per_trade
                notional = margin * config.leverage
                qty = notional / entry_price
                fee = notional * config.fee_rate
                if cash >= margin + fee:
                    cash -= fee
                    trade_no += 1
                    position = {
                        "trade_no": trade_no,
                        "side": side,
                        "entry_idx": signal.activate_idx,
                        "entry_date": date,
                        "entry_price": entry_price,
                        "qty": qty,
                        "margin": margin,
                        "stop": signal.initial_stop,
                        "initial_stop": signal.initial_stop,
                        "entry_fee": fee,
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
                exit_price, exit_reason = check_stop(row, position)
                if exit_price is not None:
                    exit_price = apply_slippage(exit_price, side, "exit", config.slippage_rate)
                    gross = unrealized(position, exit_price)
                    exit_fee = abs(exit_price * float(position["qty"])) * config.fee_rate
                    net = gross - float(position["entry_fee"]) - exit_fee

            if exit_price is not None:
                cash += net
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
                        "qty": position["qty"],
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

        equity.append({"date": date, "equity": cash + unrealized(position, float(row["close"])), "cash": cash})

    trades_df = pd.DataFrame(trades)
    equity_df = pd.DataFrame(equity)
    if not equity_df.empty:
        equity_df["peak"] = equity_df["equity"].cummax()
        equity_df["drawdown"] = equity_df["equity"] / equity_df["peak"] - 1.0
    return {
        "df": os_df,
        "raw_nodes": engine.export_raw_nodes(),
        "identity_nodes": engine.export_tagged_nodes(),
        "turns": engine.export_turns(),
        "os_log": engine.export_os_log(),
        "trades": trades_df,
        "bad_trades": audit_ds05_camp_direction(trades_df),
        "equity": equity_df,
    }


def summarize(symbol: str, name: str, result: dict[str, pd.DataFrame], config: CryptoBacktestConfig) -> dict:
    trades = result["trades"]
    bad = result["bad_trades"]
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
        "bad_trades": int(len(bad)),
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
    parser = argparse.ArgumentParser(description="Batch run DS05 on hot crypto daily data.")
    parser.add_argument("--out-dir", default="results/ds05_crypto_hot")
    parser.add_argument("--years", type=int, default=5)
    parser.add_argument("--initial-cash", type=float, default=1_000.0)
    parser.add_argument("--margin-per-trade", type=float, default=200.0)
    parser.add_argument("--leverage", type=float, default=5.0)
    parser.add_argument("--fee-rate", type=float, default=0.0005)
    parser.add_argument("--slippage-rate", type=float, default=0.0003)
    parser.add_argument("--maintenance-margin-rate", type=float, default=0.005)
    parser.add_argument("--atr-window", type=int, default=14)
    parser.add_argument("--extreme-atr-tol", type=float, default=0.80)
    parser.add_argument("--gap", type=int, default=3)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = CryptoBacktestConfig(
        initial_cash=args.initial_cash,
        margin_per_trade=args.margin_per_trade,
        leverage=args.leverage,
        fee_rate=args.fee_rate,
        slippage_rate=args.slippage_rate,
        maintenance_margin_rate=args.maintenance_margin_rate,
        atr_window=args.atr_window,
        extreme_atr_tol=args.extreme_atr_tol,
        gap=args.gap,
        years=args.years,
    )
    out_dir = Path(args.out_dir)
    summaries = []
    errors = []
    for symbol, name in CRYPTO_LIST.items():
        try:
            df = fetch_crypto_okx(symbol, config.years, config.atr_window)
            result = run_crypto_backtest(df, config)
            save_frames(out_dir / name, result)
            row = summarize(symbol, name, result, config)
            summaries.append(row)
            print(
                f"{name}: trades={row['trades']} bad={row['bad_trades']} "
                f"liq={row['liquidations']} return={row['total_return'] * 100:.2f}% "
                f"mdd={row['max_drawdown'] * 100:.2f}%"
            )
        except Exception as exc:
            errors.append({"symbol": symbol, "name": name, "error": repr(exc)})
            print(f"{name}: ERROR {exc}")

    out_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(summaries).sort_values(["bad_trades", "total_return"], ascending=[True, False]).to_csv(out_dir / "summary.csv", index=False)
    pd.DataFrame(errors).to_csv(out_dir / "errors.csv", index=False)
    print("")
    print(f"Files processed: {len(CRYPTO_LIST)}")
    print(f"Succeeded:       {len(summaries)}")
    print(f"Failed:          {len(errors)}")
    print(f"Summary:         {out_dir / 'summary.csv'}")


if __name__ == "__main__":
    main()
