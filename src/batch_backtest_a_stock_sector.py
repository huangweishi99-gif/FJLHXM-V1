from __future__ import annotations

import argparse
import json
import re
import time
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import pandas as pd

from backtest_a_stock_fengji import run_stock_backtest


DEFAULT_SECTORS = [
    "CPO概念",
    "算力概念",
    "半导体",
    "机器人概念",
    "低空经济",
    "军工",
    "新能源车",
    "证券",
    "互联网金融",
]


BOARD_FIELDS = "f12,f14,f3,f6,f8,f20,f21,f62"
STOCK_FIELDS = "f12,f14,f2,f3,f5,f6,f8,f20,f21,f62"


def request_eastmoney(params: dict, retries: int = 4) -> dict:
    url = "https://push2.eastmoney.com/api/qt/clist/get"
    query = urlencode(params)
    request = Request(f"{url}?{query}", headers={"User-Agent": "Mozilla/5.0"})
    last_exc: Exception | None = None
    for attempt in range(retries):
        try:
            with urlopen(request, timeout=30) as response:
                payload = json.loads(response.read().decode("utf-8"))
            if payload.get("data") is None:
                raise ValueError(f"Eastmoney returned empty data: {payload}")
            return payload
        except Exception as exc:
            last_exc = exc
            time.sleep(0.8 * (attempt + 1))
    raise RuntimeError(f"Eastmoney request failed: {last_exc}") from last_exc


def parse_diff(payload: dict) -> list[dict]:
    diff = payload.get("data", {}).get("diff", [])
    if isinstance(diff, dict):
        return list(diff.values())
    return list(diff or [])


def fetch_board_list(source: str) -> pd.DataFrame:
    fs_values: list[str]
    if source == "concept":
        fs_values = ["m:90+t:2"]
    elif source == "industry":
        fs_values = ["m:90+t:3"]
    else:
        fs_values = ["m:90+t:2", "m:90+t:3"]

    rows: list[dict] = []
    for fs in fs_values:
        payload = request_eastmoney(
            {
                "pn": "1",
                "pz": "10000",
                "po": "1",
                "np": "1",
                "fid": "f62",
                "fs": fs,
                "fields": BOARD_FIELDS,
            }
        )
        board_type = "concept" if "t:2" in fs else "industry"
        for item in parse_diff(payload):
            code = str(item.get("f12", "")).strip()
            name = str(item.get("f14", "")).strip()
            if not code or not name:
                continue
            rows.append(
                {
                    "board_code": code,
                    "board_name": name,
                    "board_type": board_type,
                    "pct_chg": to_float(item.get("f3")),
                    "amount": to_float(item.get("f6")),
                    "turnover": to_float(item.get("f8")),
                    "total_market_cap": to_float(item.get("f20")),
                    "main_net_inflow": to_float(item.get("f62")),
                }
            )
    return pd.DataFrame(rows).drop_duplicates("board_code").reset_index(drop=True)


def to_float(value) -> float:
    try:
        if value in {None, "-", ""}:
            return 0.0
        return float(value)
    except Exception:
        return 0.0


def resolve_board(term: str, boards: pd.DataFrame) -> dict:
    text = term.strip()
    if not text:
        raise ValueError("Empty board term")
    if text.upper().startswith("BK"):
        hit = boards[boards["board_code"].str.upper() == text.upper()]
        if hit.empty:
            return {"board_code": text.upper(), "board_name": text.upper(), "board_type": "manual"}
        return hit.iloc[0].to_dict()

    exact = boards[boards["board_name"] == text]
    if not exact.empty:
        return exact.iloc[0].to_dict()

    contains = boards[boards["board_name"].str.contains(re.escape(text), na=False)]
    if contains.empty:
        contains = boards[boards["board_name"].apply(lambda name: text in str(name) or str(name) in text)]
    if contains.empty:
        choices = ", ".join(boards["board_name"].head(30).astype(str).tolist())
        raise ValueError(f"找不到板块: {text}. 可用样例: {choices}")

    contains = contains.copy()
    contains["match_score"] = contains["board_name"].apply(lambda name: 0 if str(name) == text else len(str(name)))
    return contains.sort_values(["match_score", "amount"], ascending=[True, False]).iloc[0].to_dict()


def fetch_board_stocks(board_code: str) -> pd.DataFrame:
    payload = request_eastmoney(
        {
            "pn": "1",
            "pz": "1000",
            "po": "1",
            "np": "1",
            "fid": "f6",
            "fs": f"b:{board_code}",
            "fields": STOCK_FIELDS,
        }
    )
    rows: list[dict] = []
    for item in parse_diff(payload):
        code = str(item.get("f12", "")).strip().zfill(6)
        name = str(item.get("f14", "")).strip()
        if not code or not name:
            continue
        rows.append(
            {
                "symbol": code,
                "name": name,
                "price": to_float(item.get("f2")),
                "pct_chg": to_float(item.get("f3")),
                "volume": to_float(item.get("f5")),
                "amount": to_float(item.get("f6")),
                "turnover": to_float(item.get("f8")),
                "total_market_cap": to_float(item.get("f20")),
                "free_market_cap": to_float(item.get("f21")),
                "main_net_inflow": to_float(item.get("f62")),
            }
        )
    return pd.DataFrame(rows).drop_duplicates("symbol").reset_index(drop=True)


def valid_a_stock(row: pd.Series, include_bj: bool) -> bool:
    symbol = str(row["symbol"]).zfill(6)
    name = str(row["name"]).upper()
    if "ST" in name or "退" in name:
        return False
    if symbol.startswith(("2", "9")):
        return False
    if not include_bj and symbol.startswith(("4", "8")):
        return False
    return symbol.startswith(("0", "3", "6")) or (include_bj and symbol.startswith(("4", "8")))


def clean_filename(value: str) -> str:
    text = re.sub(r'[\\/:*?"<>|]+', "_", value.strip())
    text = re.sub(r"\s+", "_", text)
    return text[:80] or "sector"


def select_top_stocks(frame: pd.DataFrame, top_n: int, sort_by: str, include_bj: bool) -> pd.DataFrame:
    if frame.empty:
        return frame
    out = frame[frame.apply(lambda row: valid_a_stock(row, include_bj), axis=1)].copy()
    sort_column = {
        "amount": "amount",
        "market_cap": "total_market_cap",
        "free_market_cap": "free_market_cap",
        "main_net_inflow": "main_net_inflow",
        "turnover": "turnover",
    }[sort_by]
    out = out.sort_values(sort_column, ascending=False).head(top_n).reset_index(drop=True)
    out.insert(0, "rank", range(1, len(out) + 1))
    return out


def run_sector_backtest(board: dict, pool: pd.DataFrame, args: argparse.Namespace, out_root: Path) -> pd.DataFrame:
    sector_name = str(board["board_name"])
    sector_code = str(board["board_code"])
    sector_dir = out_root / f"{clean_filename(sector_name)}_{sector_code}"
    sector_dir.mkdir(parents=True, exist_ok=True)
    pool.to_csv(sector_dir / "stock_pool.csv", index=False, encoding="utf-8-sig")

    summary_path = sector_dir / "sector_summary_partial.csv"
    summary_by_symbol: dict[str, dict] = {}
    if args.resume and summary_path.exists():
        existing = pd.read_csv(summary_path, dtype={"symbol": str})
        for _, item in existing.iterrows():
            row = item.to_dict()
            symbol = str(row.get("symbol", "")).zfill(6)
            if symbol:
                summary_by_symbol[symbol] = row

    for index, row in pool.iterrows():
        symbol = str(row["symbol"]).zfill(6)
        name = str(row["name"])
        previous = summary_by_symbol.get(symbol)
        if args.resume and previous and str(previous.get("status", "")) == "ok":
            print(f"\n[{sector_name} {index + 1}/{len(pool)}] {name}({symbol}) 已成功，跳过")
            continue

        stock_args = argparse.Namespace(**vars(args))
        stock_args.symbol = symbol
        stock_args.name = name
        stock_args.out_dir = str(sector_dir / f"{symbol}_{clean_filename(name)}")
        print(f"\n[{sector_name} {index + 1}/{len(pool)}] {name}({symbol})")
        try:
            summary = run_stock_backtest(stock_args)
            summary["status"] = "ok"
            summary["error"] = ""
        except Exception as exc:
            summary = {
                "symbol": symbol,
                "name": name,
                "status": "error",
                "error": str(exc),
                "out_dir": str(stock_args.out_dir),
            }
            print(f"{name}({symbol}): error {exc}")
        summary["board_code"] = sector_code
        summary["board_name"] = sector_name
        summary["board_type"] = board.get("board_type", "")
        summary["board_rank"] = int(row.get("rank", index + 1))
        summary_by_symbol[symbol] = summary
        partial = pd.DataFrame(summary_by_symbol.values())
        if "board_rank" in partial.columns:
            partial = partial.sort_values("board_rank")
        partial.to_csv(summary_path, index=False, encoding="utf-8-sig")
        if args.sleep_seconds > 0:
            time.sleep(args.sleep_seconds)

    summary_df = pd.DataFrame(summary_by_symbol.values())
    if "total_return" in summary_df.columns:
        summary_df = summary_df.sort_values(["status", "total_return"], ascending=[True, False])
    summary_df.to_csv(sector_dir / "sector_summary.csv", index=False, encoding="utf-8-sig")
    return summary_df


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Backtest FengJi Total Pattern by A-share sector top stocks.")
    parser.add_argument("--boards", default=",".join(DEFAULT_SECTORS), help="板块名称或BK代码，逗号分隔。")
    parser.add_argument("--board-source", choices=["all", "concept", "industry"], default="all")
    parser.add_argument("--top-n", type=int, default=28)
    parser.add_argument("--sort-by", choices=["amount", "market_cap", "free_market_cap", "main_net_inflow", "turnover"], default="amount")
    parser.add_argument("--include-bj", action="store_true", help="包含北交所股票。默认剔除。")
    parser.add_argument("--dry-run", action="store_true", help="只生成板块股票池，不执行回测。")
    parser.add_argument("--resume", action="store_true", help="同一输出目录下跳过已成功股票，只重试失败或未完成股票。")
    parser.add_argument("--start", default="20200101")
    parser.add_argument("--end", default="20500101")
    parser.add_argument("--db", default="data/market_data.sqlite")
    parser.add_argument("--data-source", choices=["auto", "db", "download"], default="auto")
    parser.add_argument("--cache-dir", default="data/a_stock")
    parser.add_argument("--out-dir", default="results/fengji_total_a_stock_sectors")
    parser.add_argument("--strategies", default="DS01,DS02,DS03,DS04,DS05,DS06,DS07,DS08")
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
    parser.add_argument("--no-update-db", action="store_true")
    parser.add_argument("--download-pause-seconds", type=float, default=2.0, help="Pause between Eastmoney daily and 60m requests for each stock.")
    parser.add_argument("--sleep-seconds", type=float, default=3.0, help="Pause between stocks to reduce Eastmoney disconnects.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    out_root = Path(args.out_dir)
    out_root.mkdir(parents=True, exist_ok=True)

    board_terms = [item.strip() for item in args.boards.split(",") if item.strip()]
    boards = fetch_board_list(args.board_source)
    boards.to_csv(out_root / "eastmoney_board_catalog.csv", index=False, encoding="utf-8-sig")

    all_summaries: list[pd.DataFrame] = []
    board_rows: list[dict] = []
    for term in board_terms:
        board = resolve_board(term, boards)
        print(f"\n===== 板块: {term} => {board['board_name']}({board['board_code']}) =====")
        constituents = fetch_board_stocks(str(board["board_code"]))
        pool = select_top_stocks(constituents, args.top_n, args.sort_by, args.include_bj)
        if pool.empty:
            print(f"{board['board_name']}({board['board_code']}): 没有可回测股票")
            continue
        sector_dir = out_root / f"{clean_filename(str(board['board_name']))}_{board['board_code']}"
        sector_dir.mkdir(parents=True, exist_ok=True)
        constituents.to_csv(sector_dir / "stock_pool_all.csv", index=False, encoding="utf-8-sig")
        pool.to_csv(sector_dir / "stock_pool.csv", index=False, encoding="utf-8-sig")
        board_rows.append({**board, "selected": len(pool), "stock_pool": str(sector_dir / "stock_pool.csv")})
        print(pool[["rank", "symbol", "name", args.sort_by if args.sort_by != "market_cap" else "total_market_cap"]].to_string(index=False))
        if args.dry_run:
            continue
        summary = run_sector_backtest(board, pool, args, out_root)
        all_summaries.append(summary)

    pd.DataFrame(board_rows).to_csv(out_root / "selected_boards.csv", index=False, encoding="utf-8-sig")
    if all_summaries:
        combined = pd.concat(all_summaries, ignore_index=True)
        if "total_return" in combined.columns:
            combined = combined.sort_values(["status", "total_return"], ascending=[True, False])
        combined.to_csv(out_root / "a_stock_sector_batch_summary.csv", index=False, encoding="utf-8-sig")
        print(f"\nSaved combined summary to {out_root / 'a_stock_sector_batch_summary.csv'}")


if __name__ == "__main__":
    main()
