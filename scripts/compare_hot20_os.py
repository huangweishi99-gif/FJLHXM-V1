import pandas as pd

old = pd.read_csv("results/fengji_total_a_stock_hot20_ds07_fixed/a_stock_hot20_summary.csv", dtype={"symbol": str})
new = pd.read_csv("results/fengji_total_a_stock_hot20_os20260529/a_stock_hot20_summary.csv", dtype={"symbol": str})
m = old.merge(new, on="symbol", suffixes=("_old", "_new"))


def stats(df, label):
    r = df["total_return"]
    print(
        f"{label}: profit_rate={(r > 0).mean()*100:.1f}% "
        f"avg={r.mean()*100:.1f}% med={r.median()*100:.1f}% "
        f"win={df.wins.sum()/df.trades.sum()*100:.1f}% trades={int(df.trades.sum())} "
        f"bad={int(df.bad_audits.sum())}"
    )


stats(old, "OLD")
stats(new, "NEW")
m["d"] = m.total_return_new - m.total_return_old
print("\nTop gainers:")
for _, r in m.sort_values("d", ascending=False).head(5).iterrows():
    print(f"  {r.name_old}: {r.total_return_old*100:.1f}% -> {r.total_return_new*100:.1f}% ({r.d*100:+.1f}pp)")
print("Top losers:")
for _, r in m.sort_values("d").head(5).iterrows():
    print(f"  {r.name_old}: {r.total_return_old*100:.1f}% -> {r.total_return_new*100:.1f}% ({r.d*100:+.1f}pp)")
