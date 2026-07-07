from __future__ import annotations

import argparse
import json
import math
import time
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import pandas as pd

from fengji_core.market_coverage import filter_strategies_for_a_stock_data
from market_data_store import connect as connect_market_db
from market_data_store import export_csv, import_frame, init_db
from unified_whitelist_engine import DEFAULT_STRATEGIES_CSV, UnifiedConfig, merge_candidates, run_unified_symbol


DEFAULT_STOCKS = {
    "高德红外": "002414",
}


def normalize_code(value: str) -> str:
    text = value.strip().upper()
    if text in DEFAULT_STOCKS:
        return DEFAULT_STOCKS[text]
    for suffix in [".SZ", ".SH", ".BJ"]:
        text = text.replace(suffix, "")
    return text.zfill(6)


def eastmoney_secid(code: str) -> str:
    code = normalize_code(code)
    if code.startswith("6"):
        return f"1.{code}"
    return f"0.{code}"


def sina_symbol(code: str) -> str:
    code = normalize_code(code)
    if code.startswith("6"):
        return f"sh{code}"
    return f"sz{code}"


def clean_ohlcv_rows(rows: list[dict], source: str, code: str, timeframe: str, start: str = "", end: str = "") -> pd.DataFrame:
    frame = pd.DataFrame(rows)
    if frame.empty:
        raise ValueError(f"{source} kline data is empty for {code} {timeframe}")
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
    for column in ["open", "high", "low", "close", "volume"]:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    frame = frame[["date", "open", "high", "low", "close", "volume"]].dropna().drop_duplicates("date").sort_values("date").reset_index(drop=True)
    if start:
        start_dt = pd.to_datetime(start, errors="coerce")
        if not pd.isna(start_dt):
            frame = frame[frame["date"] >= start_dt]
    if end:
        end_dt = pd.to_datetime(end, errors="coerce")
        if not pd.isna(end_dt):
            if end_dt.hour == 0 and end_dt.minute == 0 and end_dt.second == 0:
                end_dt = end_dt.replace(hour=23, minute=59, second=59)
            frame = frame[frame["date"] <= end_dt]
    frame = frame.reset_index(drop=True)
    if frame.empty:
        raise ValueError(f"{source} kline data is empty after cleaning for {code} {timeframe}")
    return frame


def fetch_eastmoney_kline(code: str, klt: int, start: str, end: str, fqt: int, cache_path: Path, refresh: bool = False) -> pd.DataFrame:
    if cache_path.exists() and not refresh:
        frame = pd.read_csv(cache_path)
        if not frame.empty:
            frame["date"] = pd.to_datetime(frame["date"], errors="raise")
            return frame

    url = "https://push2his.eastmoney.com/api/qt/stock/kline/get"
    params = {
        "secid": eastmoney_secid(code),
        "fields1": "f1,f2,f3,f4,f5,f6",
        "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61",
        "klt": str(klt),
        "fqt": str(fqt),
        "beg": start,
        "end": end,
        "lmt": "1000000",
    }
    last_exc: Exception | None = None
    payload: dict | None = None
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/json,text/plain,*/*",
        "Referer": "https://quote.eastmoney.com/",
        "Connection": "close",
    }
    for attempt in range(3):
        try:
            request = Request(f"{url}?{urlencode(params)}", headers=headers)
            with urlopen(request, timeout=15) as response:
                payload = json.loads(response.read().decode("utf-8"))
            last_exc = None
            break
        except Exception as exc:
            last_exc = exc
            time.sleep(min(1.5 * (attempt + 1), 5.0))
    if last_exc is not None:
        raise last_exc
    if not payload or not payload.get("data") or not payload["data"].get("klines"):
        raise ValueError(f"Eastmoney returned no kline data for {code} klt={klt}: {payload}")

    rows: list[dict] = []
    for item in payload["data"]["klines"]:
        parts = item.split(",")
        if len(parts) < 6:
            continue
        rows.append(
            {
                "date": parts[0],
                "open": parts[1],
                "close": parts[2],
                "high": parts[3],
                "low": parts[4],
                "volume": parts[5],
            }
        )
    frame = clean_ohlcv_rows(rows, "Eastmoney", code, f"klt={klt}", start, end)
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(cache_path, index=False, encoding="utf-8")
    return frame


def fetch_sina_kline(code: str, scale: int, start: str, end: str, cache_path: Path, refresh: bool = False) -> pd.DataFrame:
    if cache_path.exists() and not refresh:
        frame = pd.read_csv(cache_path)
        if not frame.empty:
            frame["date"] = pd.to_datetime(frame["date"], errors="raise")
            return frame

    url = "https://quotes.sina.cn/cn/api/json_v2.php/CN_MarketData.getKLineData"
    params = {
        "symbol": sina_symbol(code),
        "scale": str(scale),
        "ma": "no",
        "datalen": "1023",
    }
    last_exc: Exception | None = None
    payload: list[dict] | None = None
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/json,text/plain,*/*",
        "Referer": "https://finance.sina.com.cn/",
        "Connection": "close",
    }
    for attempt in range(6):
        try:
            request = Request(f"{url}?{urlencode(params)}", headers=headers)
            with urlopen(request, timeout=20) as response:
                payload = json.loads(response.read().decode("utf-8"))
            last_exc = None
            break
        except Exception as exc:
            last_exc = exc
            time.sleep(min(2.0 * (attempt + 1), 12.0))
    if last_exc is not None:
        raise last_exc
    if not payload:
        raise ValueError(f"Sina returned no kline data for {code} scale={scale}: {payload}")

    rows = [
        {
            "date": item.get("day"),
            "open": item.get("open"),
            "high": item.get("high"),
            "low": item.get("low"),
            "close": item.get("close"),
            "volume": item.get("volume", 0),
        }
        for item in payload
    ]
    frame = clean_ohlcv_rows(rows, "Sina", code, f"scale={scale}", start, end)
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(cache_path, index=False, encoding="utf-8")
    return frame


def fetch_kline_with_fallback(
    code: str,
    eastmoney_klt: int,
    sina_scale: int,
    start: str,
    end: str,
    fqt: int,
    cache_path: Path,
    refresh: bool = False,
) -> tuple[pd.DataFrame, str]:
    try:
        return fetch_eastmoney_kline(code, eastmoney_klt, start, end, fqt, cache_path, refresh), "eastmoney"
    except Exception as eastmoney_exc:
        print(f"东方财富下载失败，改用新浪备用源: {eastmoney_exc}")
        try:
            return fetch_sina_kline(code, sina_scale, start, end, cache_path, refresh), "sina"
        except Exception as sina_exc:
            raise RuntimeError(f"东方财富和新浪都下载失败: Eastmoney={eastmoney_exc}; Sina={sina_exc}") from sina_exc


def db_bound(value: str, end_of_day: bool = False) -> str:
    if not value:
        return ""
    text = str(value).strip()
    if not text:
        return ""
    stamp = pd.to_datetime(text, errors="coerce")
    if pd.isna(stamp):
        return ""
    if end_of_day:
        stamp = stamp.replace(hour=23, minute=59, second=59)
    return stamp.strftime("%Y-%m-%d %H:%M:%S")


def load_or_fetch_stock_data(args: argparse.Namespace, code: str, cache_root: Path) -> tuple[pd.DataFrame, pd.DataFrame, Path, Path | None, str, str]:
    daily_csv = cache_root / f"{code}_1D_qfq.csv"
    h1_csv = cache_root / f"{code}_60m_qfq.csv"
    data_source = args.data_source
    data_warning = ""
    if args.refresh and data_source == "auto":
        data_source = "download"

    if data_source in {"auto", "db"}:
        db_path = Path(args.db)
        try:
            if not db_path.exists():
                raise FileNotFoundError(db_path)
            conn = connect_market_db(db_path)
            init_db(conn)
            start = db_bound(args.start)
            end = db_bound(args.end, end_of_day=True)
            d1_rows = export_csv(conn, "A_STOCK", code, "1D", daily_csv, start=start, end=end)
            h1_rows = export_csv(conn, "A_STOCK", code, "1H", h1_csv, start=start, end=end)
            if d1_rows > 0:
                daily = pd.read_csv(daily_csv)
                daily["date"] = pd.to_datetime(daily["date"], errors="raise")
                if h1_rows > 0:
                    h1 = pd.read_csv(h1_csv)
                    h1["date"] = pd.to_datetime(h1["date"], errors="raise")
                    print(f"数据源: 本地数据库 {db_path}，导出 D1={d1_rows} H1={h1_rows}")
                    return daily, h1, daily_csv, h1_csv, "db", data_warning
                data_warning = "H1缺失，仅运行日线定式DS01-DS06"
                print(f"数据源: 本地数据库 {db_path}，导出 D1={d1_rows} H1=0；{data_warning}")
                return daily, pd.DataFrame(), daily_csv, None, "db_partial", data_warning
            for path in [daily_csv, h1_csv]:
                if path.exists() and path.stat().st_size <= 50:
                    path.unlink()
            raise ValueError(f"数据库数据不完整: D1={d1_rows}, H1={h1_rows}")
        except Exception as exc:
            if data_source == "db":
                raise
            print(f"数据库取数失败，改用东方财富下载/缓存: {exc}")

    daily, daily_download_source = fetch_kline_with_fallback(code, 101, 240, args.start, args.end, 1, daily_csv, args.refresh)
    try:
        time.sleep(float(getattr(args, "download_pause_seconds", 1.0)))
        h1, h1_download_source = fetch_kline_with_fallback(code, 60, 60, args.start, args.end, 1, h1_csv, args.refresh)
        h1_path: Path | None = h1_csv
    except Exception as exc:
        h1 = pd.DataFrame()
        h1_path = None
        h1_download_source = "none"
        data_warning = f"H1下载失败，仅运行日线定式DS01-DS06: {exc}"
        print(data_warning)
    if not args.no_update_db:
        try:
            conn = connect_market_db(args.db)
            init_db(conn)
            import_frame(conn, daily, "A_STOCK", code, "1D", str(daily_csv), name=args.name or code)
            if not h1.empty and h1_path is not None:
                import_frame(conn, h1, "A_STOCK", code, "1H", str(h1_path), name=args.name or code)
            print(f"已回写数据库: {args.db}")
        except Exception as exc:
            print(f"回写数据库失败，不影响本次回测: {exc}")
    print(f"数据源: 下载/本地CSV缓存 D1={len(daily)}({daily_download_source}) H1={len(h1)}({h1_download_source})")
    return daily, h1, daily_csv, h1_path, "download" if h1_path else "download_partial", data_warning


def make_config(args: argparse.Namespace) -> UnifiedConfig:
    return UnifiedConfig(
        initial_cash=args.initial_cash,
        lots=1,
        commission_rate=0.0,
        slippage_ticks=0.0,
        atr_window=args.atr_window,
        gap=args.gap,
        max_same_direction_entries=1,
        futures_mode=False,
        spec=None,
    )


def safe_read_csv(path: Path) -> pd.DataFrame:
    if not path.exists() or path.stat().st_size <= 5:
        return pd.DataFrame()
    try:
        return pd.read_csv(path)
    except pd.errors.EmptyDataError:
        return pd.DataFrame()


def build_price_frame(daily_csv: Path, h1_csv: Path | None) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    for path, tf in [(daily_csv, "D1"), (h1_csv, "H1")]:
        if path is None or not Path(path).exists():
            continue
        frame = pd.read_csv(path)
        frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
        frame["timeframe"] = tf
        frames.append(frame[["date", "open", "high", "low", "close", "timeframe"]])
    out = pd.concat(frames, ignore_index=True).dropna(subset=["date"]).sort_values(["date", "timeframe"]).reset_index(drop=True)
    return out


def next_t1_open(price_frame: pd.DataFrame, entry_time: pd.Timestamp, exit_time: pd.Timestamp) -> tuple[pd.Timestamp, float, str]:
    entry_day = entry_time.date()
    if exit_time.date() > entry_day:
        return exit_time, math.nan, ""
    future = price_frame[price_frame["date"].dt.date > entry_day].sort_values("date")
    if future.empty:
        return exit_time, math.nan, "t1_no_next_bar"
    row = future.iloc[0]
    return pd.to_datetime(row["date"]), float(row["open"]), "t1_delayed_to_next_open"


def buy_cost(value: float, commission_rate: float, min_commission: float, transfer_fee_rate: float) -> float:
    commission = max(value * commission_rate, min_commission)
    transfer = value * transfer_fee_rate
    return commission + transfer


def sell_cost(value: float, commission_rate: float, min_commission: float, transfer_fee_rate: float, stamp_duty_rate: float) -> float:
    commission = max(value * commission_rate, min_commission)
    transfer = value * transfer_fee_rate
    stamp = value * stamp_duty_rate
    return commission + transfer + stamp


def max_affordable_shares(cash: float, price: float, args: argparse.Namespace) -> int:
    if price <= 0:
        return 0
    shares = int(cash // (price * args.lot_size)) * args.lot_size
    while shares >= args.lot_size:
        value = shares * price
        if value + buy_cost(value, args.commission_rate, args.min_commission, args.transfer_fee_rate) <= cash:
            return shares
        shares -= args.lot_size
    return 0


def score_stock_trades(accepted: pd.DataFrame, price_frame: pd.DataFrame, args: argparse.Namespace, out_dir: Path) -> dict:
    rejected_rows: list[dict] = []
    scored_rows: list[dict] = []
    cash = float(args.initial_cash)
    peak = cash
    max_dd = 0.0
    last_exit_time = pd.Timestamp.min

    if accepted.empty:
        return {
            "trades": 0,
            "wins": 0,
            "win_rate": 0.0,
            "net_pnl": 0.0,
            "final_equity": cash,
            "total_return": 0.0,
            "max_drawdown": 0.0,
            "stock_rejected": 0,
        }

    accepted = accepted.copy()
    accepted["entry_time"] = pd.to_datetime(accepted["entry_time"], errors="coerce")
    accepted["exit_time"] = pd.to_datetime(accepted["exit_time"], errors="coerce")
    accepted = accepted.dropna(subset=["entry_time", "exit_time"]).sort_values(["entry_time", "strategy_priority"]).reset_index(drop=True)

    for _, row in accepted.iterrows():
        item = row.to_dict()
        if int(row["side"]) != 1:
            item["stock_reject_reason"] = "a_share_long_only_reject_short"
            rejected_rows.append(item)
            continue

        entry_time = pd.to_datetime(row["entry_time"])
        exit_time = pd.to_datetime(row["exit_time"])
        if entry_time <= last_exit_time:
            item["stock_reject_reason"] = "cash_locked_by_previous_position"
            rejected_rows.append(item)
            continue

        entry_price = float(row["entry_price"]) * (1.0 + args.slippage_rate)
        adjusted_exit_time, t1_exit_price, t1_reason = next_t1_open(price_frame, entry_time, exit_time)
        raw_exit_price = float(row["exit_price"]) if math.isnan(t1_exit_price) else t1_exit_price
        exit_price = raw_exit_price * (1.0 - args.slippage_rate)

        shares = max_affordable_shares(cash, entry_price, args)
        if shares < args.lot_size:
            item["stock_reject_reason"] = "cash_less_than_one_lot"
            rejected_rows.append(item)
            continue

        cash_before = cash
        buy_value = shares * entry_price
        buy_fee = buy_cost(buy_value, args.commission_rate, args.min_commission, args.transfer_fee_rate)
        cash_after_buy = cash - buy_value - buy_fee

        sell_value = shares * exit_price
        sell_fee = sell_cost(sell_value, args.commission_rate, args.min_commission, args.transfer_fee_rate, args.stamp_duty_rate)
        cash = cash_after_buy + sell_value - sell_fee
        net = cash - cash_before
        peak = max(peak, cash)
        drawdown = cash / peak - 1.0
        max_dd = min(max_dd, drawdown)
        last_exit_time = adjusted_exit_time

        scored_rows.append(
            {
                **item,
                "stock_trade_no": len(scored_rows) + 1,
                "stock_entry_time": str(entry_time),
                "stock_exit_time": str(adjusted_exit_time),
                "stock_exit_adjustment": t1_reason,
                "stock_entry_price": entry_price,
                "stock_exit_price": exit_price,
                "shares": shares,
                "buy_value": buy_value,
                "sell_value": sell_value,
                "buy_fee": buy_fee,
                "sell_fee": sell_fee,
                "net_pnl": net,
                "cash_after": cash,
                "drawdown": drawdown,
            }
        )

    scored = pd.DataFrame(scored_rows)
    rejected = pd.DataFrame(rejected_rows)
    scored.to_csv(out_dir / "stock_scored_trades.csv", index=False, encoding="utf-8-sig")
    rejected.to_csv(out_dir / "stock_rejected_orders.csv", index=False, encoding="utf-8-sig")
    if scored.empty:
        return {
            "trades": 0,
            "wins": 0,
            "win_rate": 0.0,
            "net_pnl": 0.0,
            "final_equity": float(args.initial_cash),
            "total_return": 0.0,
            "max_drawdown": 0.0,
            "stock_rejected": len(rejected),
        }
    by_strategy = (
        scored.groupby("strategy_id", dropna=False)
        .agg(trades=("strategy_id", "size"), wins=("net_pnl", lambda x: int((x > 0).sum())), net_pnl=("net_pnl", "sum"))
        .reset_index()
    )
    by_strategy["win_rate"] = by_strategy["wins"] / by_strategy["trades"]
    by_strategy.to_csv(out_dir / "stock_by_strategy.csv", index=False, encoding="utf-8-sig")

    return {
        "trades": int(len(scored)),
        "wins": int((scored["net_pnl"] > 0).sum()),
        "win_rate": float((scored["net_pnl"] > 0).mean()),
        "net_pnl": float(scored["net_pnl"].sum()),
        "final_equity": float(scored["cash_after"].iloc[-1]),
        "total_return": float(scored["cash_after"].iloc[-1] / args.initial_cash - 1.0),
        "max_drawdown": float(max_dd),
        "stock_rejected": len(rejected),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Backtest FengJi Total Pattern DS01-DS09 on A-share stock data.")
    parser.add_argument("--symbol", default="002414", help="A-share code or known name, e.g. 002414 or 高德红外.")
    parser.add_argument("--name", default="高德红外")
    parser.add_argument("--start", default="20200101")
    parser.add_argument("--end", default="20500101")
    parser.add_argument("--db", default="data/market_data.sqlite")
    parser.add_argument("--data-source", choices=["auto", "db", "download"], default="auto")
    parser.add_argument("--cache-dir", default="data/a_stock")
    parser.add_argument("--out-dir", default="results/fengji_total_a_stock_002414")
    parser.add_argument("--strategies", default=DEFAULT_STRATEGIES_CSV)
    parser.add_argument("--initial-cash", type=float, default=20000.0)
    parser.add_argument("--commission-rate", type=float, default=0.0003)
    parser.add_argument("--min-commission", type=float, default=5.0)
    parser.add_argument("--stamp-duty-rate", type=float, default=0.0005)
    parser.add_argument("--transfer-fee-rate", type=float, default=0.00001)
    parser.add_argument("--slippage-rate", type=float, default=0.0003)
    parser.add_argument("--lot-size", type=int, default=100)
    parser.add_argument("--atr-window", type=int, default=14)
    parser.add_argument("--gap", type=int, default=3)
    parser.add_argument("--refresh", action="store_true")
    parser.add_argument("--no-update-db", action="store_true", help="Do not write downloaded stock data back to the local market DB.")
    parser.add_argument("--download-pause-seconds", type=float, default=1.0, help="Pause between Eastmoney daily and 60m requests.")
    return parser.parse_args()


def run_stock_backtest(args: argparse.Namespace) -> dict:
    code = normalize_code(args.symbol)
    strategies = [item.strip().upper() for item in args.strategies.split(",") if item.strip()]
    cache_root = Path(args.cache_dir)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    daily, h1, daily_csv, h1_csv, data_source_used, data_warning = load_or_fetch_stock_data(args, code, cache_root)
    strategies_requested = [item.strip().upper() for item in args.strategies.split(",") if item.strip()]

    m15_csv = cache_root / f"{code}_15m_qfq.csv"
    m15_rows = 0
    if m15_csv.exists() and m15_csv.stat().st_size > 5:
        try:
            m15_rows = len(pd.read_csv(m15_csv, usecols=["date"]))
        except Exception:
            m15_rows = 0

    strategies_to_run, skip_notes = filter_strategies_for_a_stock_data(
        strategies_requested,
        h1_rows=len(h1),
        m15_rows=m15_rows,
    )
    if skip_notes:
        note = "; ".join(skip_notes)
        data_warning = f"{data_warning}; {note}".strip("; ").strip()
        print(f"{args.name}({code}): {note}；运行 {','.join(strategies_to_run)}")

    ledger = run_unified_symbol(
        symbol=args.name or code,
        config=make_config(args),
        daily_csv=daily_csv,
        h1_csv=h1_csv,
        m15_csv=m15_csv if m15_csv.exists() and m15_csv.stat().st_size > 5 else None,
        strategies=strategies_to_run,
        out_dir=out_dir / "raw_fengji",
    )
    candidates = safe_read_csv(out_dir / "raw_fengji" / "candidate_trades.csv")
    long_candidates = candidates[candidates["side"].astype(int) == 1].copy() if not candidates.empty else pd.DataFrame()
    merged = merge_candidates(long_candidates, max_same_direction_entries=1)
    merged["accepted_trades"].to_csv(out_dir / "stock_long_accepted_trades.csv", index=False, encoding="utf-8-sig")
    merged["rejected_orders"].to_csv(out_dir / "stock_long_rejected_orders.csv", index=False, encoding="utf-8-sig")
    merged["ledger_events"].to_csv(out_dir / "stock_long_ledger_events.csv", index=False, encoding="utf-8-sig")

    price_frame = build_price_frame(daily_csv, h1_csv)
    score = score_stock_trades(merged["accepted_trades"], price_frame, args, out_dir)
    summary = {
        "symbol": code,
        "name": args.name,
        "start": args.start,
        "end": args.end,
        "d1_rows": len(daily),
        "h1_rows": len(h1),
        "candidates_all": int(len(candidates)),
        "candidates_long": int(len(long_candidates)),
        "ledger_candidates": ledger["candidates"],
        "bad_audits": ledger["bad_audits"],
        "data_source": data_source_used,
        "data_warning": data_warning,
        "strategies_run": ",".join(strategies_to_run),
        "db": args.db,
        **score,
        "daily_csv": str(daily_csv),
        "h1_csv": "" if h1_csv is None else str(h1_csv),
        "out_dir": str(out_dir),
    }
    pd.DataFrame([summary]).to_csv(out_dir / "stock_summary.csv", index=False, encoding="utf-8-sig")
    print(
        f"{args.name}({code}): candidates_all={summary['candidates_all']} "
        f"long={summary['candidates_long']} trades={summary['trades']} "
        f"return={summary['total_return']:.2%} dd={summary['max_drawdown']:.2%} "
        f"bad={summary['bad_audits']} out={out_dir}"
    )
    return summary


def main() -> None:
    run_stock_backtest(parse_args())


if __name__ == "__main__":
    main()
