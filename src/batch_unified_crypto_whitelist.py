from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import pandas as pd

try:
    import requests
except ModuleNotFoundError:
    requests = None

from unified_whitelist_engine import DEFAULT_STRATEGIES_CSV, UnifiedConfig, run_unified_symbol


DEFAULT_CRYPTO_WHITELIST = [
    "BTC-USDT",
    "ETH-USDT",
    "SOL-USDT",
    "BNB-USDT",
    "XRP-USDT",
    "ADA-USDT",
    "DOGE-USDT",
    "AVAX-USDT",
    "LTC-USDT",
    "LINK-USDT",
]


def read_symbols(value: str) -> list[str]:
    path = Path(value)
    if path.exists():
        text = path.read_text(encoding="utf-8-sig")
        return [normalize_symbol(line.strip()) for line in text.splitlines() if line.strip() and not line.strip().startswith("#")]
    if value.upper() == "DEFAULT":
        return DEFAULT_CRYPTO_WHITELIST
    return [normalize_symbol(item.strip()) for item in value.split(",") if item.strip()]


def normalize_symbol(value: str) -> str:
    text = value.strip().upper().replace("_", "-").replace("/", "-")
    if not text:
        return text
    if "-" in text:
        return text
    if text.endswith("USDT") and len(text) > 4:
        return f"{text[:-4]}-USDT"
    return f"{text}-USDT"


def fetch_okx_history(inst_id: str, bar: str, days: int, cache_path: Path, atr_window: int, refresh: bool = False) -> pd.DataFrame:
    if cache_path.exists() and not refresh:
        frame = pd.read_csv(cache_path)
        frame["date"] = pd.to_datetime(frame["date"], errors="raise")
        if len(frame.columns) > 6:
            frame = frame[["date", "open", "high", "low", "close", "volume"]].copy()
            frame.to_csv(cache_path, index=False, encoding="utf-8")
        return frame

    url = "https://www.okx.com/api/v5/market/history-candles"
    start_date = pd.Timestamp.now("UTC").tz_localize(None) - pd.Timedelta(days=days)
    rows: list[list[str]] = []
    cursor: str | None = None
    session = requests.Session() if requests is not None else None
    if session is not None:
        session.headers.update({"User-Agent": "Mozilla/5.0"})

    while True:
        params = {"instId": inst_id, "bar": bar, "limit": "300"}
        if cursor:
            params["after"] = cursor
        last_exc: Exception | None = None
        for attempt in range(4):
            try:
                if session is not None:
                    response = session.get(url, params=params, timeout=30)
                    response.raise_for_status()
                    payload = response.json()
                else:
                    request = Request(f"{url}?{urlencode(params)}", headers={"User-Agent": "Mozilla/5.0"})
                    with urlopen(request, timeout=30) as response:
                        payload = json.loads(response.read().decode("utf-8"))
                last_exc = None
                break
            except Exception as exc:
                last_exc = exc
                time.sleep(0.8 * (attempt + 1))
        if last_exc is not None:
            raise last_exc
        if payload.get("code") != "0":
            raise ValueError(f"OKX error for {inst_id} {bar}: {payload}")
        batch = payload.get("data", [])
        if not batch:
            break
        rows.extend(batch)
        oldest_ts = int(batch[-1][0])
        oldest_date = pd.to_datetime(oldest_ts, unit="ms")
        cursor = batch[-1][0]
        if oldest_date <= start_date or len(batch) < 300:
            break
        time.sleep(0.08)

    if not rows:
        raise ValueError(f"No OKX data downloaded for {inst_id} {bar}")

    frame = pd.DataFrame(rows, columns=["ts", "open", "high", "low", "close", "volume", "vol_ccy", "vol_ccy_quote", "confirm"])
    frame["date"] = pd.to_datetime(pd.to_numeric(frame["ts"]), unit="ms")
    for col in ["open", "high", "low", "close", "volume"]:
        frame[col] = pd.to_numeric(frame[col], errors="coerce")
    frame = frame[frame["date"] >= start_date]
    frame = frame[["date", "open", "high", "low", "close", "volume"]].dropna().drop_duplicates("date").sort_values("date").reset_index(drop=True)

    prev_close = frame["close"].shift(1)
    ranges = pd.concat(
        [
            frame["high"] - frame["low"],
            (frame["high"] - prev_close).abs(),
            (frame["low"] - prev_close).abs(),
        ],
        axis=1,
    )
    frame["tr"] = ranges.max(axis=1)
    frame["atr"] = frame["tr"].rolling(atr_window).mean()
    saved = frame[["date", "open", "high", "low", "close", "volume"]].copy()
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    saved.to_csv(cache_path, index=False, encoding="utf-8")
    return frame


def pct_return_trade(row: pd.Series, margin: float, leverage: float, fee_rate: float, slippage_rate: float, maintenance_margin_rate: float) -> dict:
    side = int(row["side"])
    entry = float(row["entry_price"])
    exit_price = float(row["exit_price"])
    if side == 1:
        entry_eff = entry * (1.0 + slippage_rate)
        exit_eff = exit_price * (1.0 - slippage_rate)
        liq = entry_eff * (1.0 - 1.0 / leverage + maintenance_margin_rate)
        liquidated = exit_price <= liq
        gross = -margin if liquidated else margin * leverage * ((exit_eff / entry_eff) - 1.0)
    else:
        entry_eff = entry * (1.0 - slippage_rate)
        exit_eff = exit_price * (1.0 + slippage_rate)
        liq = entry_eff * (1.0 + 1.0 / leverage - maintenance_margin_rate)
        liquidated = exit_price >= liq
        gross = -margin if liquidated else margin * leverage * ((entry_eff / exit_eff) - 1.0)
    fee = 0.0 if liquidated else margin * leverage * fee_rate * 2.0
    net = gross - fee
    return {"crypto_entry_price": entry_eff, "crypto_exit_price": exit_eff, "liquidation_price": liq, "liquidated": liquidated, "crypto_net_pnl": net}


def score_crypto_results(
    symbol_dir: Path,
    initial_cash: float,
    margin: float,
    leverage: float,
    fee_rate: float,
    slippage_rate: float,
    maintenance_margin_rate: float,
    score_days: int | None = None,
) -> dict[str, Any]:
    accepted_path = symbol_dir / "accepted_trades.csv"
    rejected_path = symbol_dir / "rejected_orders.csv"
    bad_path = symbol_dir / "strategy_bad_trades.csv"
    if not accepted_path.exists():
        raise FileNotFoundError(accepted_path)
    accepted = pd.read_csv(accepted_path)
    rejected = safe_read_csv(rejected_path)
    bad = safe_read_csv(bad_path)
    if accepted.empty:
        return {
            "trades": 0,
            "wins": 0,
            "win_rate": 0.0,
            "liquidations": 0,
            "net_pnl": 0.0,
            "final_equity": initial_cash,
            "total_return": 0.0,
            "max_drawdown": 0.0,
            "accepted": 0,
            "rejected": len(rejected),
            "bad_audits": len(bad),
        }

    accepted["entry_time"] = pd.to_datetime(accepted["entry_time"], errors="coerce")
    accepted["exit_time"] = pd.to_datetime(accepted["exit_time"], errors="coerce")
    score_start = pd.NaT
    if score_days is not None and score_days > 0:
        latest_time = accepted[["entry_time", "exit_time"]].max(axis=1).max()
        if not pd.isna(latest_time):
            score_start = latest_time - pd.Timedelta(days=score_days)
            accepted = accepted[accepted["entry_time"] >= score_start].copy()

    if accepted.empty:
        return {
            "trades": 0,
            "wins": 0,
            "win_rate": 0.0,
            "liquidations": 0,
            "net_pnl": 0.0,
            "final_equity": initial_cash,
            "total_return": 0.0,
            "max_drawdown": 0.0,
            "accepted": 0,
            "rejected": len(rejected),
            "bad_audits": len(bad),
            "score_days": score_days or 0,
            "score_start": "" if pd.isna(score_start) else str(score_start),
        }

    pnl_rows = [
        pct_return_trade(row, margin, leverage, fee_rate, slippage_rate, maintenance_margin_rate)
        for _, row in accepted.iterrows()
    ]
    pnl = pd.DataFrame(pnl_rows)
    scored = pd.concat([accepted.reset_index(drop=True), pnl], axis=1)
    scored = scored.sort_values(["exit_time", "portfolio_trade_no"]).reset_index(drop=True)
    scored["equity"] = initial_cash + scored["crypto_net_pnl"].cumsum()
    scored["peak"] = scored["equity"].cummax()
    scored["drawdown"] = scored["equity"] / scored["peak"] - 1.0
    scored.to_csv(symbol_dir / "crypto_scored_accepted_trades.csv", index=False, encoding="utf-8-sig")
    by_strategy = (
        scored.groupby("strategy_id", dropna=False)
        .agg(
            trades=("strategy_id", "size"),
            wins=("crypto_net_pnl", lambda x: int((x > 0).sum())),
            net_pnl=("crypto_net_pnl", "sum"),
            liquidations=("liquidated", "sum"),
        )
        .reset_index()
    )
    by_strategy["win_rate"] = by_strategy["wins"] / by_strategy["trades"]
    by_strategy.to_csv(symbol_dir / "crypto_by_strategy.csv", index=False, encoding="utf-8-sig")
    return {
        "trades": int(len(scored)),
        "wins": int((scored["crypto_net_pnl"] > 0).sum()),
        "win_rate": float((scored["crypto_net_pnl"] > 0).mean()),
        "liquidations": int(scored["liquidated"].sum()),
        "net_pnl": float(scored["crypto_net_pnl"].sum()),
        "final_equity": float(scored["equity"].iloc[-1]),
        "total_return": float(scored["equity"].iloc[-1] / initial_cash - 1.0),
        "max_drawdown": float(scored["drawdown"].min()),
        "accepted": int(len(scored)),
        "rejected": int(len(rejected)),
        "bad_audits": int(len(bad)),
        "score_days": score_days or 0,
        "score_start": "" if pd.isna(score_start) else str(score_start),
    }


def safe_read_csv(path: Path) -> pd.DataFrame:
    if not path.exists() or path.stat().st_size <= 5:
        return pd.DataFrame()
    try:
        return pd.read_csv(path)
    except pd.errors.EmptyDataError:
        return pd.DataFrame()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Backtest FengJi Total Pattern DS01-DS09 on OKX crypto whitelist.")
    parser.add_argument("--symbols", default="DEFAULT")
    parser.add_argument("--days", type=int, default=180)
    parser.add_argument("--out-dir", default="results/unified_crypto_whitelist")
    parser.add_argument("--cache-dir", default="data/crypto_okx")
    parser.add_argument("--strategies", default=DEFAULT_STRATEGIES_CSV)
    parser.add_argument("--initial-cash", type=float, default=1000.0)
    parser.add_argument("--margin-per-trade", type=float, default=200.0)
    parser.add_argument("--leverage", type=float, default=2.0)
    parser.add_argument("--fee-rate", type=float, default=0.0005)
    parser.add_argument("--slippage-rate", type=float, default=0.0003)
    parser.add_argument("--maintenance-margin-rate", type=float, default=0.005)
    parser.add_argument("--atr-window", type=int, default=14)
    parser.add_argument("--gap", type=int, default=3)
    parser.add_argument("--max-same-direction-entries", type=int, default=3)
    parser.add_argument("--score-days", type=int, default=0, help="Only score trades whose entry_time is within the latest N days; 0 scores the full window.")
    parser.add_argument("--refresh", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    symbols = read_symbols(args.symbols)
    strategies = [item.strip().upper() for item in args.strategies.split(",") if item.strip()]
    needs_daily = any(item in strategies for item in ["DS01", "DS02", "DS03", "DS04", "DS05", "DS06", "DS07", "DS09"])
    needs_h1 = any(item in strategies for item in ["DS07", "DS08"])
    needs_m15 = "DS09" in strategies
    out_root = Path(args.out_dir)
    cache_root = Path(args.cache_dir)
    out_root.mkdir(parents=True, exist_ok=True)
    summaries: list[dict] = []

    for inst_id in symbols:
        name = inst_id.replace("-USDT", "")
        symbol_dir = out_root / inst_id
        try:
            daily_csv = cache_root / f"{inst_id}_1D_{args.days}d.csv"
            h1_csv = cache_root / f"{inst_id}_1H_{args.days}d.csv"
            m15_csv = cache_root / f"{inst_id}_15m_{args.days}d.csv"
            if needs_daily:
                fetch_okx_history(inst_id, "1Dutc", args.days, daily_csv, args.atr_window, args.refresh)
            if needs_h1:
                fetch_okx_history(inst_id, "1H", args.days, h1_csv, args.atr_window, args.refresh)
            if needs_m15:
                fetch_okx_history(inst_id, "15m", args.days, m15_csv, args.atr_window, args.refresh)

            config = UnifiedConfig(
                initial_cash=args.initial_cash,
                lots=1,
                commission_rate=0.0,
                slippage_ticks=0.0,
                atr_window=args.atr_window,
                gap=args.gap,
                max_same_direction_entries=args.max_same_direction_entries,
                futures_mode=False,
                spec=None,
            )
            ledger = run_unified_symbol(
                name,
                config,
                daily_csv if needs_daily else None,
                h1_csv if needs_h1 else None,
                m15_csv if needs_m15 else None,
                strategies,
                symbol_dir,
            )
            score = score_crypto_results(
                symbol_dir,
                args.initial_cash,
                args.margin_per_trade,
                args.leverage,
                args.fee_rate,
                args.slippage_rate,
                args.maintenance_margin_rate,
                args.score_days if args.score_days > 0 else None,
            )
            summary = {
                "symbol": inst_id,
                "name": name,
                "days": args.days,
                "d1_rows": len(pd.read_csv(daily_csv)) if needs_daily and daily_csv.exists() else 0,
                "h1_rows": len(pd.read_csv(h1_csv)) if needs_h1 and h1_csv.exists() else 0,
                "m15_rows": len(pd.read_csv(m15_csv)) if needs_m15 and m15_csv.exists() else 0,
                "candidates": ledger["candidates"],
                **score,
                "status": "ok",
                "error": "",
                "out_dir": str(symbol_dir),
            }
        except Exception as exc:
            summary = {
                "symbol": inst_id,
                "name": name,
                "days": args.days,
                "d1_rows": 0,
                "h1_rows": 0,
                "m15_rows": 0,
                "candidates": 0,
                "trades": 0,
                "wins": 0,
                "win_rate": 0.0,
                "liquidations": 0,
                "net_pnl": 0.0,
                "final_equity": args.initial_cash,
                "total_return": 0.0,
                "max_drawdown": 0.0,
                "accepted": 0,
                "rejected": 0,
                "bad_audits": 0,
                "status": "error",
                "error": str(exc),
                "out_dir": str(symbol_dir),
            }
        summaries.append(summary)
        print(
            f"{inst_id}: {summary['status']} candidates={summary['candidates']} "
            f"accepted={summary['accepted']} rejected={summary['rejected']} "
            f"return={summary['total_return']:.2%} dd={summary['max_drawdown']:.2%} bad={summary['bad_audits']}"
        )

    summary_df = pd.DataFrame(summaries).sort_values(["status", "total_return"], ascending=[True, False])
    summary_df.to_csv(out_root / "crypto_whitelist_summary.csv", index=False, encoding="utf-8-sig")
    print(f"Saved crypto whitelist summary to {out_root / 'crypto_whitelist_summary.csv'}")


if __name__ == "__main__":
    main()
