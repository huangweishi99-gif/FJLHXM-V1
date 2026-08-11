from __future__ import annotations

import argparse
import json
import re
import time
from pathlib import Path

import pandas as pd

from backtest_us_stock_fengji import normalize_ticker, run_us_stock_backtest


DEFAULT_CATALOG = Path("data/us_stock/gics_sectors.json")


def clean_filename(value: str) -> str:
    text = re.sub(r'[\\/:*?"<>|]+', "_", value.strip())
    text = re.sub(r"\s+", "_", text)
    return text[:80] or "sector"


def load_catalog(path: Path) -> list[dict]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return list(payload.get("sectors", []))


def select_top_tickers(sector: dict, top_n: int) -> pd.DataFrame:
    tickers = [normalize_ticker(t) for t in sector.get("tickers", []) if str(t).strip()]
    tickers = list(dict.fromkeys(tickers))
    rows = [{"rank": i + 1, "symbol": sym, "name": sym} for i, sym in enumerate(tickers[:top_n])]
    return pd.DataFrame(rows)


def run_sector_backtest(sector: dict, pool: pd.DataFrame, args: argparse.Namespace, out_root: Path) -> pd.DataFrame:
    sector_name = str(sector.get("sector_name", "sector"))
    sector_code = str(sector.get("sector_code", "GICS"))
    sector_dir = out_root / f"{clean_filename(sector_name)}_{sector_code}"
    sector_dir.mkdir(parents=True, exist_ok=True)
    pool.to_csv(sector_dir / "stock_pool.csv", index=False, encoding="utf-8-sig")

    summary_path = sector_dir / "sector_summary_partial.csv"
    summary_by_symbol: dict[str, dict] = {}
    if args.resume and summary_path.exists():
        existing = pd.read_csv(summary_path, dtype={"symbol": str})
        for _, item in existing.iterrows():
            sym = str(item.get("symbol", "")).upper()
            if sym:
                summary_by_symbol[sym] = item.to_dict()

    for index, row in pool.iterrows():
        symbol = str(row["symbol"]).upper()
        name = str(row.get("name", symbol))
        previous = summary_by_symbol.get(symbol)
        if args.resume and previous and str(previous.get("status", "")) == "ok":
            print(f"\n[{sector_name} {index + 1}/{len(pool)}] {symbol} 已成功，跳过")
            continue

        stock_args = argparse.Namespace(**vars(args))
        stock_args.symbol = symbol
        stock_args.name = name
        stock_args.out_dir = str(sector_dir / f"{symbol}_{clean_filename(name)}")
        print(f"\n[{sector_name} {index + 1}/{len(pool)}] {name}({symbol})")
        try:
            summary = run_us_stock_backtest(stock_args)
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
            print(f"{symbol}: error {exc}")
        summary["sector_code"] = sector_code
        summary["sector_name"] = sector_name
        summary["sector_name_zh"] = sector.get("sector_name_zh", "")
        summary["sector_rank"] = int(row.get("rank", index + 1))
        summary_by_symbol[symbol] = summary
        partial = pd.DataFrame(summary_by_symbol.values())
        if "sector_rank" in partial.columns:
            partial = partial.sort_values("sector_rank")
        partial.to_csv(summary_path, index=False, encoding="utf-8-sig")
        if args.sleep_seconds > 0:
            time.sleep(args.sleep_seconds)

    summary_df = pd.DataFrame(summary_by_symbol.values())
    if "total_return" in summary_df.columns:
        summary_df = summary_df.sort_values(["status", "total_return"], ascending=[True, False])
    summary_df.to_csv(sector_dir / "sector_summary.csv", index=False, encoding="utf-8-sig")
    return summary_df


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Batch backtest FengJi Total Pattern on US GICS sectors (21 stocks each).")
    parser.add_argument("--catalog", default=str(DEFAULT_CATALOG), help="GICS sector catalog JSON")
    parser.add_argument("--sectors", default="", help="Comma sector names/codes; empty = all 11 GICS")
    parser.add_argument("--top-n", type=int, default=21, help="Stocks per sector (default 21)")
    parser.add_argument("--dry-run", action="store_true", help="Only export stock pools")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--start", default="2020-01-01")
    parser.add_argument("--end", default="2050-01-01")
    parser.add_argument("--cache-dir", default="data/us_stock")
    parser.add_argument("--out-dir", default="results/fengji_total_us_stock_sectors")
    parser.add_argument("--strategies", default="DS01,DS02,DS03,DS04,DS05,DS06,DS07,DS08")
    parser.add_argument("--initial-cash", type=float, default=100000.0)
    parser.add_argument("--commission-rate", type=float, default=0.0005)
    parser.add_argument("--slippage-rate", type=float, default=0.0002)
    parser.add_argument("--atr-window", type=int, default=14)
    parser.add_argument("--gap", type=int, default=3)
    parser.add_argument("--refresh", action="store_true")
    parser.add_argument("--data-source", default="auto", choices=["auto", "yahoo_chart", "yfinance"])
    parser.add_argument("--download-pause-seconds", type=float, default=0.8)
    parser.add_argument("--sleep-seconds", type=float, default=1.0, help="Pause between tickers")
    return parser.parse_args()


def resolve_sectors(catalog: list[dict], terms: str) -> list[dict]:
    if not terms.strip():
        return catalog
    wanted = [t.strip().lower() for t in terms.split(",") if t.strip()]
    out = []
    for sector in catalog:
        name = str(sector.get("sector_name", "")).lower()
        code = str(sector.get("sector_code", "")).lower()
        zh = str(sector.get("sector_name_zh", "")).lower()
        if any(w in name or w in code or w in zh or name in w for w in wanted):
            out.append(sector)
    if not out:
        raise ValueError(f"No sector matched: {terms}")
    return out


def main() -> None:
    args = parse_args()
    catalog = load_catalog(Path(args.catalog))
    sectors = resolve_sectors(catalog, args.sectors)
    out_root = Path(args.out_dir)
    out_root.mkdir(parents=True, exist_ok=True)

    batch_rows = []
    for sector in sectors:
        pool = select_top_tickers(sector, args.top_n)
        sector_name = sector.get("sector_name", "")
        print(f"\n=== {sector_name} ({len(pool)} tickers) ===")
        if args.dry_run:
            sector_dir = out_root / f"{clean_filename(str(sector_name))}_{sector.get('sector_code', '')}"
            sector_dir.mkdir(parents=True, exist_ok=True)
            pool.to_csv(sector_dir / "stock_pool.csv", index=False, encoding="utf-8-sig")
            continue
        summary = run_sector_backtest(sector, pool, args, out_root)
        ok = int((summary["status"] == "ok").sum()) if not summary.empty else 0
        batch_rows.append(
            {
                "sector_code": sector.get("sector_code"),
                "sector_name": sector_name,
                "sector_name_zh": sector.get("sector_name_zh", ""),
                "pool_size": len(pool),
                "ok": ok,
                "error": int((summary["status"] == "error").sum()) if not summary.empty else len(pool),
                "out_dir": str(out_root / f"{clean_filename(str(sector_name))}_{sector.get('sector_code', '')}"),
            }
        )

    if batch_rows:
        pd.DataFrame(batch_rows).to_csv(out_root / "us_sector_batch_summary.csv", index=False, encoding="utf-8-sig")


if __name__ == "__main__":
    main()
