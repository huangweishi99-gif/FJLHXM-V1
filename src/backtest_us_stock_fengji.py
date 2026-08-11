from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from unified_whitelist_engine import DEFAULT_STRATEGIES_CSV, UnifiedConfig, merge_candidates, run_unified_symbol
from us_stock_data import fetch_us_kline, normalize_ticker


def make_config(args: argparse.Namespace) -> UnifiedConfig:
    return UnifiedConfig(
        atr_window=args.atr_window,
        gap=args.gap,
        max_same_direction_entries=3,
        spec=None,
    )


def safe_read_csv(path: Path) -> pd.DataFrame:
    if not path.exists() or path.stat().st_size <= 5:
        return pd.DataFrame()
    return pd.read_csv(path)


def score_us_trades(accepted: pd.DataFrame, args: argparse.Namespace, out_dir: Path) -> dict:
    if accepted.empty:
        return {
            "trades": 0,
            "wins": 0,
            "win_rate": 0.0,
            "net_pnl": 0.0,
            "final_equity": float(args.initial_cash),
            "total_return": 0.0,
            "max_drawdown": 0.0,
        }
    cash = float(args.initial_cash)
    peak = cash
    max_dd = 0.0
    rows = []
    for _, item in accepted.sort_values(["entry_time", "portfolio_trade_no"]).iterrows():
        entry = float(item["entry_price"])
        exit_price = float(item["exit_price"])
        side = int(item.get("side", 1))
        shares = max(int(cash // max(entry, 0.01)), 0)
        if shares <= 0:
            continue
        entry_eff = entry * (1 + args.slippage_rate) if side > 0 else entry * (1 - args.slippage_rate)
        exit_eff = exit_price * (1 - args.slippage_rate) if side > 0 else exit_price * (1 + args.slippage_rate)
        buy_value = shares * entry_eff
        sell_value = shares * exit_eff
        fee = (buy_value + sell_value) * args.commission_rate
        if side > 0:
            net = sell_value - buy_value - fee
        else:
            net = buy_value - sell_value - fee
        cash += net
        peak = max(peak, cash)
        max_dd = min(max_dd, cash / peak - 1.0)
        rows.append({**item.to_dict(), "shares": shares, "net_pnl": net, "cash_after": cash})
    scored = pd.DataFrame(rows)
    scored.to_csv(out_dir / "us_scored_trades.csv", index=False, encoding="utf-8-sig")
    if scored.empty:
        return {
            "trades": 0,
            "wins": 0,
            "win_rate": 0.0,
            "net_pnl": 0.0,
            "final_equity": float(args.initial_cash),
            "total_return": 0.0,
            "max_drawdown": 0.0,
        }
    return {
        "trades": int(len(scored)),
        "wins": int((scored["net_pnl"] > 0).sum()),
        "win_rate": float((scored["net_pnl"] > 0).mean()),
        "net_pnl": float(scored["net_pnl"].sum()),
        "final_equity": float(scored["cash_after"].iloc[-1]),
        "total_return": float(scored["cash_after"].iloc[-1] / args.initial_cash - 1.0),
        "max_drawdown": float(max_dd),
    }


def run_us_stock_backtest(args: argparse.Namespace) -> dict:
    ticker = normalize_ticker(args.symbol)
    cache_root = Path(args.cache_dir)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    source = getattr(args, "data_source", "auto")
    pause = float(getattr(args, "download_pause_seconds", 0.8))

    daily_csv = cache_root / f"{ticker}_1D.csv"
    h1_csv = cache_root / f"{ticker}_1H.csv"
    daily = fetch_us_kline(
        ticker, "1d", args.start, args.end, daily_csv,
        source=source, refresh=args.refresh, pause_seconds=pause,
    )
    try:
        h1 = fetch_us_kline(
            ticker, "1h", args.start, args.end, h1_csv,
            source=source, refresh=args.refresh, pause_seconds=pause,
        )
    except Exception as exc:
        h1 = pd.DataFrame()
        print(f"{ticker}: H1 unavailable ({exc}), skip DS07/DS08")

    strategies_requested = [s.strip().upper() for s in args.strategies.split(",") if s.strip()]
    strategies_to_run = strategies_requested
    if h1.empty:
        strategies_to_run = [s for s in strategies_requested if s not in {"DS07", "DS08"}]
    strategies_to_run = [s for s in strategies_to_run if s != "DS09"]

    ledger = run_unified_symbol(
        symbol=ticker,
        config=make_config(args),
        daily_csv=daily_csv,
        h1_csv=h1_csv if not h1.empty else None,
        m15_csv=None,
        strategies=strategies_to_run,
        out_dir=out_dir / "raw_fengji",
    )
    candidates = safe_read_csv(out_dir / "raw_fengji" / "candidate_trades.csv")
    long_candidates = candidates[candidates["side"].astype(int) == 1].copy() if not candidates.empty else pd.DataFrame()
    merged = merge_candidates(long_candidates, max_same_direction_entries=1)
    merged["accepted_trades"].to_csv(out_dir / "us_long_accepted_trades.csv", index=False, encoding="utf-8-sig")
    score = score_us_trades(merged["accepted_trades"], args, out_dir)
    summary = {
        "symbol": ticker,
        "name": args.name or ticker,
        "market": "US_STOCK",
        "data_source": source,
        "start": args.start,
        "end": args.end,
        "d1_rows": len(daily),
        "h1_rows": len(h1),
        "candidates_all": int(len(candidates)),
        "candidates_long": int(len(long_candidates)),
        "ledger_candidates": ledger["candidates"],
        "bad_audits": ledger["bad_audits"],
        "strategies_run": ",".join(strategies_to_run),
        **score,
        "daily_csv": str(daily_csv),
        "h1_csv": "" if h1.empty else str(h1_csv),
        "out_dir": str(out_dir),
    }
    pd.DataFrame([summary]).to_csv(out_dir / "us_summary.csv", index=False, encoding="utf-8-sig")
    print(
        f"{ticker}: trades={summary['trades']} return={summary['total_return']:.2%} "
        f"dd={summary['max_drawdown']:.2%} bad={summary['bad_audits']} out={out_dir}"
    )
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Backtest FengJi Total Pattern on US stocks.")
    parser.add_argument("--symbol", required=True, help="US ticker, e.g. AAPL")
    parser.add_argument("--name", default="")
    parser.add_argument("--start", default="2020-01-01")
    parser.add_argument("--end", default="2050-01-01")
    parser.add_argument("--cache-dir", default="data/us_stock")
    parser.add_argument("--out-dir", default="results/fengji_total_us_stock_AAPL")
    parser.add_argument("--data-source", default="auto", choices=["auto", "yahoo_chart", "yfinance"])
    parser.add_argument("--download-pause-seconds", type=float, default=0.8)
    parser.add_argument("--strategies", default=DEFAULT_STRATEGIES_CSV.replace(",DS09", ""))
    parser.add_argument("--initial-cash", type=float, default=100000.0)
    parser.add_argument("--commission-rate", type=float, default=0.0005)
    parser.add_argument("--slippage-rate", type=float, default=0.0002)
    parser.add_argument("--atr-window", type=int, default=14)
    parser.add_argument("--gap", type=int, default=3)
    parser.add_argument("--refresh", action="store_true")
    return parser.parse_args()


def main() -> None:
    run_us_stock_backtest(parse_args())


if __name__ == "__main__":
    main()
