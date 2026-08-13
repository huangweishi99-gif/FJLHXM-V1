"""Compare A-share backtest results: old ds07_fixed vs new os20260529."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]


def pack_stats(df: pd.DataFrame, label: str) -> dict:
    r = df["total_return"]
    return {
        "label": label,
        "stocks": len(df),
        "profit_rate": (r > 0).mean(),
        "avg_return": r.mean(),
        "median_return": r.median(),
        "win_rate": df.wins.sum() / df.trades.sum() if df.trades.sum() else 0.0,
        "trades": int(df.trades.sum()),
        "bad_audits": int(pd.to_numeric(df.get("bad_audits", 0), errors="coerce").fillna(0).sum()),
    }


def fmt_pct(x: float) -> str:
    return f"{x * 100:.1f}%"


def compare_hot20() -> tuple[pd.DataFrame, pd.DataFrame]:
    old = pd.read_csv(
        ROOT / "results/fengji_total_a_stock_hot20_ds07_fixed/a_stock_hot20_summary.csv",
        dtype={"symbol": str},
    )
    new = pd.read_csv(
        ROOT / "results/fengji_total_a_stock_hot20_os20260529/a_stock_hot20_summary.csv",
        dtype={"symbol": str},
    )
    old["symbol"] = old["symbol"].str.zfill(6)
    new["symbol"] = new["symbol"].str.zfill(6)

    summary = pd.DataFrame([pack_stats(old, "OLD_ds07_fixed"), pack_stats(new, "NEW_os20260529")])
    out_dir = ROOT / "results/fengji_total_a_stock_hot20_os20260529"
    summary.to_csv(out_dir / "hot20_old_vs_new_summary.csv", index=False, encoding="utf-8-sig")

    merged = old.merge(new, on="symbol", suffixes=("_old", "_new"))
    merged["delta_pp"] = (merged["total_return_new"] - merged["total_return_old"]) * 100
    by_stock = merged[
        ["symbol", "name_old", "total_return_old", "total_return_new", "trades_old", "trades_new", "delta_pp"]
    ].sort_values("delta_pp", ascending=False)
    by_stock.to_csv(out_dir / "hot20_old_vs_new_by_stock.csv", index=False, encoding="utf-8-sig")
    return summary, by_stock


def board_agg(df: pd.DataFrame, label: str, name_map: dict[str, str]) -> pd.DataFrame:
    rows: list[dict] = []
    for board_code, grp in df.groupby("board_code"):
        ret = grp["total_return"]
        board_name = name_map.get(str(board_code), grp["board_name"].iloc[0] if "board_name" in grp.columns else board_code)
        rows.append(
            {
                "board_code": board_code,
                "board_name": board_name,
                "version": label,
                "stocks_ok": len(grp),
                "profit_rate": (ret > 0).mean(),
                "avg_return": ret.mean(),
                "median_return": ret.median(),
                "trades": int(grp["trades"].sum()),
                "bad_audits": int(pd.to_numeric(grp.get("bad_audits", 0), errors="coerce").fillna(0).sum()),
            }
        )
    return pd.DataFrame(rows)


def compare_sectors() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    old = pd.read_csv(ROOT / "results/a_stock_all_sectors_master_summary.csv", dtype={"symbol": str})
    old = old[old["source_file"].astype(str).str.contains("ds07_fixed", na=False)]
    old["symbol"] = old["symbol"].str.zfill(6)
    old = old[old["status"] == "ok"].drop_duplicates(["board_code", "symbol"], keep="last")

    new = pd.read_csv(
        ROOT / "results/fengji_total_a_stock_sectors_os20260529/a_stock_sector_batch_summary.csv",
        dtype={"symbol": str},
    )
    new["symbol"] = new["symbol"].str.zfill(6)
    new = new[new["status"] == "ok"].drop_duplicates(["board_code", "symbol"], keep="last")

    out_dir = ROOT / "results/fengji_total_a_stock_sectors_os20260529"
    summary = pd.DataFrame([pack_stats(old, "OLD_ds07_fixed"), pack_stats(new, "NEW_os20260529")])
    summary.to_csv(out_dir / "sectors_old_vs_new_summary.csv", index=False, encoding="utf-8-sig")

    merged = old.merge(new, on=["board_code", "symbol"], how="inner", suffixes=("_old", "_new"))
    merged["delta_pp"] = (merged["total_return_new"] - merged["total_return_old"]) * 100
    by_stock = merged[
        [
            "board_code",
            "board_name_old",
            "symbol",
            "name_old",
            "total_return_old",
            "total_return_new",
            "trades_old",
            "trades_new",
            "delta_pp",
        ]
    ].sort_values(["board_code", "delta_pp"], ascending=[True, False])
    by_stock.to_csv(out_dir / "sectors_old_vs_new_by_stock.csv", index=False, encoding="utf-8-sig")

    name_map = dict(
        zip(
            pd.read_csv(ROOT / "results/a_stock_all_sectors_overview.csv")["board_code"].astype(str),
            pd.read_csv(ROOT / "results/a_stock_all_sectors_overview.csv")["board_name"].astype(str),
        )
    )
    old_board = board_agg(old, "OLD", name_map)
    new_board = board_agg(new, "NEW", name_map)
    by_board = old_board.merge(new_board, on="board_code", suffixes=("_old", "_new"))
    for col in ("profit_rate", "avg_return", "median_return"):
        by_board[f"{col}_delta_pp"] = (by_board[f"{col}_new"] - by_board[f"{col}_old"]) * 100
    by_board["board_name"] = by_board["board_name_old"]
    by_board = by_board.sort_values("avg_return_delta_pp", ascending=False)
    by_board.to_csv(out_dir / "sectors_old_vs_new_by_board.csv", index=False, encoding="utf-8-sig")
    return summary, by_board, by_stock


def main() -> None:
    hot_summary, hot_stocks = compare_hot20()
    sec_summary, sec_board, sec_stocks = compare_sectors()

    print("=== 热门20（OLD ds07_fixed vs NEW os20260529）===")
    for _, row in hot_summary.iterrows():
        print(
            f"{row['label']}: 盈利比={fmt_pct(row['profit_rate'])} "
            f"平均={fmt_pct(row['avg_return'])} 中位={fmt_pct(row['median_return'])} "
            f"胜率={fmt_pct(row['win_rate'])} 成交={row['trades']} bad={row['bad_audits']}"
        )
    print("\n个股变化 Top5↑:")
    for _, r in hot_stocks.head(5).iterrows():
        print(
            f"  {r['name_old']}: {r['total_return_old']*100:.1f}% -> {r['total_return_new']*100:.1f}% ({r['delta_pp']:+.1f}pp)"
        )
    print("个股变化 Top5↓:")
    for _, r in hot_stocks.tail(5).sort_values("delta_pp").iterrows():
        print(
            f"  {r['name_old']}: {r['total_return_old']*100:.1f}% -> {r['total_return_new']*100:.1f}% ({r['delta_pp']:+.1f}pp)"
        )

    print("\n=== 11板块（匹配个股", len(sec_stocks), "只）===")
    for _, row in sec_summary.iterrows():
        print(
            f"{row['label']}: 盈利比={fmt_pct(row['profit_rate'])} "
            f"平均={fmt_pct(row['avg_return'])} 中位={fmt_pct(row['median_return'])} "
            f"胜率={fmt_pct(row['win_rate'])} 成交={row['trades']} bad={row['bad_audits']}"
        )
    print("\n板块平均收益变化:")
    for _, r in sec_board.iterrows():
        print(
            f"  {r['board_name']}: {r['avg_return_old']*100:.1f}% -> {r['avg_return_new']*100:.1f}% "
            f"({r['avg_return_delta_pp']:+.1f}pp) 盈利比 {r['profit_rate_old']*100:.0f}% -> {r['profit_rate_new']*100:.0f}%"
        )


if __name__ == "__main__":
    main()
