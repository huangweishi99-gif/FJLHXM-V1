from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from backtest_a_stock_fengji import run_stock_backtest


HOT20_STOCKS = [
    ("300308", "中际旭创"),
    ("300502", "新易盛"),
    ("300059", "东方财富"),
    ("002475", "立讯精密"),
    ("002594", "比亚迪"),
    ("300750", "宁德时代"),
    ("600519", "贵州茅台"),
    ("601899", "紫金矿业"),
    ("002241", "歌尔股份"),
    ("002230", "科大讯飞"),
    ("603019", "中科曙光"),
    ("000977", "浪潮信息"),
    ("002371", "北方华创"),
    ("688981", "中芯国际"),
    ("601138", "工业富联"),
    ("000725", "京东方A"),
    ("600036", "招商银行"),
    ("601318", "中国平安"),
    ("300760", "迈瑞医疗"),
    ("002414", "高德红外"),
]


def read_stock_list(value: str) -> list[tuple[str, str]]:
    if value.upper() == "HOT20":
        return HOT20_STOCKS
    path = Path(value)
    if path.exists():
        frame = pd.read_csv(path, dtype=str)
        columns = {column.lower(): column for column in frame.columns}
        code_col = columns.get("symbol") or columns.get("code") or columns.get("股票代码")
        name_col = columns.get("name") or columns.get("股票名称")
        if code_col is None:
            raise ValueError(f"Stock list must contain symbol/code column: {path}")
        return [
            (str(row[code_col]).strip().zfill(6), str(row[name_col]).strip() if name_col else str(row[code_col]).strip())
            for _, row in frame.iterrows()
            if str(row[code_col]).strip()
        ]
    rows: list[tuple[str, str]] = []
    for item in value.split(","):
        text = item.strip()
        if not text:
            continue
        if ":" in text:
            code, name = text.split(":", 1)
            rows.append((code.strip().zfill(6), name.strip()))
        else:
            rows.append((text.zfill(6), text))
    return rows


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Batch backtest FengJi Total Pattern DS01-DS08 on A-share stocks.")
    parser.add_argument("--stocks", default="HOT20", help="HOT20, CSV path, or code:name comma list.")
    parser.add_argument("--start", default="20200101")
    parser.add_argument("--end", default="20500101")
    parser.add_argument("--db", default="data/market_data.sqlite")
    parser.add_argument("--data-source", choices=["auto", "db", "download"], default="auto")
    parser.add_argument("--cache-dir", default="data/a_stock")
    parser.add_argument("--out-dir", default="results/fengji_total_a_stock_hot20")
    parser.add_argument("--strategies", default="DS01,DS02,DS03,DS04,DS05,DS06,DS07,DS08,DS09")
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
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    stocks = read_stock_list(args.stocks)
    out_root = Path(args.out_dir)
    out_root.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(stocks, columns=["symbol", "name"]).to_csv(out_root / "stock_pool.csv", index=False, encoding="utf-8-sig")

    summaries: list[dict] = []
    for index, (symbol, name) in enumerate(stocks, start=1):
        stock_args = argparse.Namespace(**vars(args))
        stock_args.symbol = symbol
        stock_args.name = name
        stock_args.out_dir = str(out_root / f"{symbol}_{name}")
        print(f"\n[{index}/{len(stocks)}] {name}({symbol})")
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
        summaries.append(summary)
        pd.DataFrame(summaries).to_csv(out_root / "a_stock_hot20_summary_partial.csv", index=False, encoding="utf-8-sig")

    summary_df = pd.DataFrame(summaries)
    if "total_return" in summary_df.columns:
        summary_df = summary_df.sort_values(["status", "total_return"], ascending=[True, False])
    summary_df.to_csv(out_root / "a_stock_hot20_summary.csv", index=False, encoding="utf-8-sig")
    print(f"\nSaved summary to {out_root / 'a_stock_hot20_summary.csv'}")


if __name__ == "__main__":
    main()
