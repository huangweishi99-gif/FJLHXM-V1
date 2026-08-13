"""Simulate FUTURES bucket merge profiles (read-only, no OS/定式 changes)."""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
for rel in ("scripts", "packages/fengji_core", "services", "src"):
    p = str(ROOT / rel)
    if p not in sys.path:
        sys.path.insert(0, p)

from discover_backtest_results import discover  # noqa: E402
from fengji_core.context_stats import (  # noqa: E402
    BUCKET_SPECS,
    STRATEGY_EXTRA_BUCKETS,
    aggregate_bucket_stats,
    bucket_atr_dist,
    bucket_range_pos,
    bucketize_value,
)


@dataclass(frozen=True)
class MergeProfile:
    name: str
    fields: tuple[tuple[str, str], ...]
    strategy_extras: dict[str, list[str]]
    atr_mode: str = "default"  # default | coarse2
    note: str = ""


def load_futures_snapshots(results_root: Path) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    for item in discover(results_root):
        if item.get("market") != "FUTURES":
            continue
        csv_path = Path(item["result_dir"]) / "trade_context_snapshots.csv"
        if csv_path.exists():
            frames.append(pd.read_csv(csv_path))
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)


def bucketize_row(row: pd.Series, field: str, kind: str, *, atr_mode: str) -> str:
    if field == "dist_active_high_atr" and atr_mode == "coarse2":
        base = bucket_atr_dist(row.get(field))
        if base in ("NEAR", "MID"):
            return "NEAR_MID"
        if base == "FAR":
            return "FAR"
        return "UNKNOWN"
    if field == "position_in_range_20" and atr_mode == "coarse2":
        base = bucket_range_pos(row.get(field))
        if base in ("LOW", "MID"):
            return "LOW_MID"
        if base == "HIGH":
            return "HIGH"
        return "UNKNOWN"
    return bucketize_value(field, kind, row.get(field))


def build_profile_bucket_key(row: pd.Series, strategy_id: str, profile: MergeProfile) -> str:
    parts = [str(strategy_id)]
    for field, kind in profile.fields:
        parts.append(f"{field}={bucketize_row(row, field, kind, atr_mode=profile.atr_mode)}")
    for extra in profile.strategy_extras.get(strategy_id, []):
        val = row.get(extra)
        if val is not None and not (isinstance(val, float) and pd.isna(val)) and str(val).strip():
            parts.append(f"{extra}={val}")
    return "|".join(parts)


def evaluate_profile(snapshots: pd.DataFrame, profile: MergeProfile, *, min_samples: int = 30) -> dict:
    work = snapshots.copy()
    work["bucket_key"] = work.apply(
        lambda r: build_profile_bucket_key(r, str(r["strategy_id"]), profile),
        axis=1,
    )
    work["is_win"] = work["net_pnl"].astype(float) > 0
    grouped = (
        work.groupby(["strategy_id", "market", "bucket_key"], dropna=False)
        .agg(count=("trade_id", "size"), wins=("is_win", "sum"))
        .reset_index()
    )
    counts = grouped["count"].astype(int).tolist()
    eligible = grouped[grouped["count"] >= min_samples]
    bins = {"<10": 0, "10-19": 0, "20-24": 0, "25-29": 0, ">=30": 0}
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
    top = grouped.sort_values("count", ascending=False).head(5)
    return {
        "profile": profile.name,
        "note": profile.note,
        "fields": [f"{f}({k})" for f, k in profile.fields],
        "strategy_extras": profile.strategy_extras,
        "atr_mode": profile.atr_mode,
        "buckets": int(len(grouped)),
        "eligible_buckets": int(len(eligible)),
        "eligible_trades": int(eligible["count"].sum()) if not eligible.empty else 0,
        "bucket_bins": bins,
        "top_buckets": [
            {
                "strategy_id": str(r["strategy_id"]),
                "count": int(r["count"]),
                "bucket_key": str(r["bucket_key"])[:120],
            }
            for _, r in top.iterrows()
        ],
    }


def profiles() -> list[MergeProfile]:
    base_extras = STRATEGY_EXTRA_BUCKETS
    full = tuple(BUCKET_SPECS)
    no_regime = tuple(x for x in BUCKET_SPECS if x[0] != "market_regime_vol")
    no_range = tuple(x for x in BUCKET_SPECS if x[0] != "position_in_range_20")
    no_camp_dup = tuple(x for x in BUCKET_SPECS if x[0] != "camp")
    core4 = tuple(x for x in BUCKET_SPECS if x[0] in ("camp_confirmed", "dist_active_high_atr", "bar_direction", "market_regime_vol"))
    core3 = tuple(x for x in BUCKET_SPECS if x[0] in ("camp_confirmed", "dist_active_high_atr", "bar_direction"))
    strategy_only: tuple[tuple[str, str], ...] = ()
    return [
        MergeProfile("V1_current", full, base_extras, note="现行 6 维 + 定式 extra"),
        MergeProfile("A_drop_camp_dup", no_camp_dup, base_extras, note="去掉与 camp_confirmed 重复的 camp"),
        MergeProfile("B_drop_market_regime_vol", no_regime, base_extras, note="去掉 market_regime_vol"),
        MergeProfile("C_drop_position_in_range_20", no_range, base_extras, note="去掉 position_in_range_20"),
        MergeProfile("D_coarse_atr_2bin", full, base_extras, atr_mode="coarse2", note="ATR 距离 NEAR+MID / FAR"),
        MergeProfile("E_core4", core4, base_extras, note="camp_confirmed + ATR + bar_direction + regime"),
        MergeProfile("F_core3", core3, base_extras, note="camp_confirmed + ATR + bar_direction"),
        MergeProfile("G_core3_no_extras", core3, {}, note="core3 且去掉 DS03/DS07/DS09 extra"),
        MergeProfile("H_strategy_only", strategy_only, {}, note="仅 strategy 级（对照基线，过粗）"),
        MergeProfile(
            "I_recommended_v1",
            core3,
            {"DS03": ["peak_key"]},
            atr_mode="coarse2",
            note="立项推荐：core3 + 粗 ATR + 保留 DS03 peak_key",
        ),
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description="Simulate FUTURES bucket merge profiles.")
    parser.add_argument("--results-root", default=str(ROOT / "results"))
    parser.add_argument("--out-dir", default=str(ROOT / "results" / "futures_bucket_merge_sim"))
    parser.add_argument("--min-samples", type=int, default=30)
    parser.add_argument("--min-eligible-target", type=int, default=30)
    args = parser.parse_args()

    snaps = load_futures_snapshots(Path(args.results_root))
    if snaps.empty:
        print("NO_FUTURES_SNAPSHOTS")
        return 1

    # Redundancy audit
    camp_match = float((snaps["camp"].astype(str) == snaps["camp_confirmed"].astype(str)).mean())
    v1 = evaluate_profile(snaps, profiles()[0], min_samples=args.min_samples)
    results = [evaluate_profile(snaps, p, min_samples=args.min_samples) for p in profiles()]
    passing = [r for r in results if r["eligible_buckets"] >= args.min_eligible_target]

    payload = {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "snapshots": int(len(snaps)),
        "v1_baseline": v1,
        "camp_equals_camp_confirmed_pct": round(camp_match * 100, 2),
        "min_bucket_samples": args.min_samples,
        "min_eligible_target": args.min_eligible_target,
        "profiles": results,
        "profiles_meeting_target": [r["profile"] for r in passing],
        "recommended_for_review": "I_recommended_v1" if any(r["profile"] == "I_recommended_v1" for r in passing) else (passing[0]["profile"] if passing else None),
    }

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_json = out_dir / "futures_bucket_merge_simulation.json"
    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps({
        "snapshots": payload["snapshots"],
        "camp_dup_pct": payload["camp_equals_camp_confirmed_pct"],
        "profiles_meeting_target": payload["profiles_meeting_target"],
        "recommended": payload["recommended_for_review"],
    }, ensure_ascii=False))
    for r in results:
        mark = " *" if r["eligible_buckets"] >= args.min_eligible_target else ""
        print(f"  {r['profile']}: buckets={r['buckets']} eligible={r['eligible_buckets']}{mark}")
    print(f"Saved {out_json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
