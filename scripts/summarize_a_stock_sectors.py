"""Aggregate A-share sector backtest summaries into one master table."""
from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


SECTOR_ROOT_PATTERNS = [
    "results/fengji_total_a_stock_sectors_*",
    "results/a_stock_sector_archive_ds07_fixed",
]


def collect_sector_summaries(roots: list[Path]) -> pd.DataFrame:
    rows: list[pd.DataFrame] = []
    for root in roots:
        if not root.exists():
            continue
        if root.is_file() and root.suffix == ".csv":
            df = pd.read_csv(root)
            df["source_file"] = str(root)
            rows.append(df)
            continue
        for path in sorted(root.rglob("sector_summary.csv")):
            df = pd.read_csv(path, dtype={"symbol": str})
            df["sector_dir"] = str(path.parent.name)
            df["source_file"] = str(path)
            rows.append(df)
        for path in sorted(root.glob("*_sector_summary.csv")):
            df = pd.read_csv(path, dtype={"symbol": str})
            df["sector_dir"] = path.stem.replace("_sector_summary", "")
            df["source_file"] = str(path)
            rows.append(df)
    if not rows:
        return pd.DataFrame()
    out = pd.concat(rows, ignore_index=True)
    if "symbol" in out.columns:
        out["symbol"] = out["symbol"].astype(str).str.zfill(6)
    if not out.empty and {"board_code", "symbol"}.issubset(out.columns):
        out = out.sort_values("source_file").drop_duplicates(["board_code", "symbol"], keep="last")
    return out


def build_overview(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    group_cols = ["board_name", "board_code"] if "board_name" in df.columns else ["sector_dir"]
    records: list[dict] = []
    for key, grp in df.groupby(group_cols, dropna=False):
        ok = grp[grp.get("status", pd.Series(["ok"] * len(grp))) == "ok"] if "status" in grp.columns else grp
        records.append(
            {
                "board_name": grp["board_name"].iloc[0] if "board_name" in grp.columns else key,
                "board_code": grp["board_code"].iloc[0] if "board_code" in grp.columns else "",
                "sector_dir": grp["sector_dir"].iloc[0] if "sector_dir" in grp.columns else "",
                "stocks_total": len(grp),
                "stocks_ok": int((grp["status"] == "ok").sum()) if "status" in grp.columns else len(grp),
                "stocks_error": int((grp["status"] == "error").sum()) if "status" in grp.columns else 0,
                "avg_return": float(ok["total_return"].mean()) if "total_return" in ok.columns and len(ok) else None,
                "median_return": float(ok["total_return"].median()) if "total_return" in ok.columns and len(ok) else None,
                "best_symbol": ok.sort_values("total_return", ascending=False)["symbol"].iloc[0]
                if "total_return" in ok.columns and len(ok)
                else "",
                "best_name": ok.sort_values("total_return", ascending=False)["name"].iloc[0]
                if "total_return" in ok.columns and len(ok)
                else "",
                "best_return": float(ok["total_return"].max()) if "total_return" in ok.columns and len(ok) else None,
                "bad_audits_sum": int(pd.to_numeric(ok.get("bad_audits", 0), errors="coerce").fillna(0).sum())
                if len(ok)
                else 0,
            }
        )
    overview = pd.DataFrame(records)
    if "avg_return" in overview.columns:
        overview = overview.sort_values("avg_return", ascending=False, na_position="last")
    return overview


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Summarize A-share sector backtests.")
    p.add_argument("--results-root", default="results", help="Scan under this directory.")
    p.add_argument(
        "--extra",
        action="append",
        default=[],
        help="Extra glob or directory to include (repeatable).",
    )
    p.add_argument("--out", default="results/a_stock_all_sectors_master_summary.csv")
    p.add_argument("--overview-out", default="results/a_stock_all_sectors_overview.csv")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    roots: list[Path] = [Path(args.results_root)]
    for pattern in SECTOR_ROOT_PATTERNS:
        roots.extend(Path(".").glob(pattern))
    for extra in args.extra:
        roots.extend(Path(".").glob(extra))
    roots = [p for p in dict.fromkeys(roots) if p.exists()]

    detail = collect_sector_summaries(roots)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    detail.to_csv(out, index=False, encoding="utf-8-sig")

    overview = build_overview(detail)
    overview_out = Path(args.overview_out)
    overview.to_csv(overview_out, index=False, encoding="utf-8-sig")

    print(f"roots={len(roots)} detail_rows={len(detail)} -> {out}")
    print(f"sectors={len(overview)} -> {overview_out}")
    if not overview.empty:
        print(overview[["board_name", "stocks_ok", "stocks_error", "avg_return", "best_name", "best_return"]].head(15).to_string(index=False))


if __name__ == "__main__":
    main()
