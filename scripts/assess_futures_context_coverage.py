"""Offline FUTURES context / tier eligibility assessment from local CSV (no PG required)."""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
for rel in ("scripts", "packages/fengji_core", "services", "src"):
    p = str(ROOT / rel)
    if p not in sys.path:
        sys.path.insert(0, p)

from discover_backtest_results import discover  # noqa: E402
from fengji_core.context_stats import aggregate_bucket_stats  # noqa: E402
from fengji_core.symbol_names import FUTURES_CN_NAMES  # noqa: E402

MIN_BUCKET_SAMPLES = 30
MIN_ELIGIBLE_BUCKETS = 30


def bucket_bins(counts: list[int]) -> dict[str, int]:
    bins: Counter[str] = Counter()
    for c in counts:
        if c >= 30:
            bins[">=30"] += 1
        elif c >= 25:
            bins["25-29"] += 1
        elif c >= 20:
            bins["20-24"] += 1
        elif c >= 10:
            bins["10-19"] += 1
        else:
            bins["<10"] += 1
    return dict(bins)


def load_futures_snapshots(root: Path) -> tuple[pd.DataFrame, list[dict]]:
    rows_meta: list[dict] = []
    frames: list[pd.DataFrame] = []
    for item in discover(root):
        if item.get("market") != "FUTURES":
            continue
        csv_path = Path(item["result_dir"]) / "trade_context_snapshots.csv"
        if not csv_path.exists():
            rows_meta.append({**item, "snapshots": 0, "status": "missing_context"})
            continue
        df = pd.read_csv(csv_path)
        n = len(df)
        rows_meta.append({**item, "snapshots": n, "status": "ok"})
        if n:
            frames.append(df)
    if not frames:
        return pd.DataFrame(), rows_meta
    return pd.concat(frames, ignore_index=True), rows_meta


def main() -> int:
    parser = argparse.ArgumentParser(description="Offline FUTURES tier eligibility from context CSV.")
    parser.add_argument("--results-root", default=str(ROOT / "results"))
    parser.add_argument("--out-dir", default=str(ROOT / "results" / "futures_tier_offline_assess"))
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    snaps, per_dir = load_futures_snapshots(Path(args.results_root))
    futures_dirs = [m for m in per_dir if m.get("market") == "FUTURES"]
    with_ctx = [m for m in futures_dirs if m.get("status") == "ok" and int(m.get("snapshots") or 0) > 0]

    if snaps.empty:
        payload = {
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "mode": "offline_csv",
            "error": "no_futures_snapshots",
            "futures_result_dirs": len(futures_dirs),
        }
        (out_dir / "futures_context_coverage.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(payload, ensure_ascii=False))
        return 1

    futures_snaps = snaps[snaps["market"] == "FUTURES"] if "market" in snaps.columns else snaps
    agg = aggregate_bucket_stats(futures_snaps)
    counts = [int(r["count"]) for _, r in agg.iterrows()]
    eligible_mask = (agg["count"] >= MIN_BUCKET_SAMPLES) & agg["signal_score"].notna()
    eligible_count = int(eligible_mask.sum())
    status = "INSUFFICIENT_MARKET_DATA" if eligible_count < MIN_ELIGIBLE_BUCKETS else "READY_FOR_REVIEW"

    top_symbols = (
        futures_snaps.groupby("symbol").size().sort_values(ascending=False).head(10).to_dict()
        if "symbol" in futures_snaps.columns
        else {}
    )

    payload = {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "mode": "offline_csv",
        "futures_result_dirs": len(futures_dirs),
        "dirs_with_context": len(with_ctx),
        "snapshots": int(len(futures_snaps)),
        "buckets": len(agg),
        "eligible_buckets": eligible_count,
        "status": status,
        "bucket_count_bins": bucket_bins(counts),
        "recommended_tiers": {
            "activate": eligible_count >= MIN_ELIGIBLE_BUCKETS,
            "note": "offline replay; activation still requires PG audit + manual review",
        },
        "note": (
            "Offline replay from trade_context_snapshots.csv; PG import cannot increase eligible "
            "if all 34 FUTURES dirs already have context. New tier activation needs eligible>=30 "
            "or a separate bucket-dimension reduction project — do not change OS/定式 rules to inflate samples."
        ),
        "top_symbols_by_snapshots": {str(k): int(v) for k, v in top_symbols.items()},
        "per_dir": per_dir,
    }

    out_json = out_dir / "futures_context_coverage.json"
    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    md_lines = [
        "# FUTURES context 离线评估",
        "",
        f"- 生成时间：{payload['generated_at']}",
        f"- FUTURES 回测目录：**{payload['futures_result_dirs']}** · 有 context：**{payload['dirs_with_context']}**",
        f"- 快照总数：**{payload['snapshots']}** · 桶数：**{payload['buckets']}**",
        f"- eligible_buckets：**{eligible_count}/{payload['buckets']}** · status=`{status}`",
        f"- 桶样本分布：{payload['bucket_count_bins']}",
        "",
        "## 结论",
        "",
        payload["note"],
        "",
        "## Top 品种（快照数）",
        "",
    ]
    for sym, n in top_symbols.items():
        cn = FUTURES_CN_NAMES.get(sym, sym)
        md_lines.append(f"- {cn}({sym}): {n}")
    (out_dir / "futures_context_coverage.md").write_text("\n".join(md_lines), encoding="utf-8")

    print(json.dumps({k: payload[k] for k in (
        "snapshots", "buckets", "eligible_buckets", "status", "bucket_count_bins", "dirs_with_context"
    )}, ensure_ascii=False))
    print(f"Saved {out_json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
