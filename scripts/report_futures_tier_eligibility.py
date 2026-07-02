"""FUTURES signal_tier eligibility audit (read-only PG + optional CSV staleness)."""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for rel in ("services", "packages/fengji_core", "scripts", "src"):
    p = str(ROOT / rel)
    if p not in sys.path:
        sys.path.insert(0, p)

from calibrate_context_market_tiers import calibrate_market  # noqa: E402
from db.models import ContextBucketStat, TradeContextSnapshot  # noqa: E402
from db.session import get_engine  # noqa: E402
from discover_backtest_results import discover  # noqa: E402
from fengji_core.symbol_names import FUTURES_CN_NAMES  # noqa: E402
from sqlalchemy import func, select  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402


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


def csv_last_date(csv_path: Path) -> str | None:
    if not csv_path.exists():
        return None
    try:
        import pandas as pd

        df = pd.read_csv(csv_path, usecols=[0], nrows=0)
        col = df.columns[0]
        tail = pd.read_csv(csv_path, usecols=[col]).iloc[-1, 0]
        return str(pd.to_datetime(tail, errors="coerce").date())
    except Exception:
        return None


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit FUTURES tier eligibility from PG.")
    parser.add_argument("--out-dir", default=str(ROOT / "results" / "futures_tier_audit"))
    parser.add_argument("--check-csv-stale", action="store_true", help="Compare data/futures/1d vs backtest dirs")
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    with Session(get_engine()) as s:
        rows = s.scalars(select(ContextBucketStat).where(ContextBucketStat.market == "FUTURES")).all()
        snap_count = s.scalar(
            select(func.count()).select_from(TradeContextSnapshot).where(TradeContextSnapshot.market == "FUTURES")
        )

    counts = [int(r.count or 0) for r in rows]
    cal = calibrate_market("FUTURES", rows, min_bucket_samples=30, min_eligible_buckets=30, medium_quantile=0.5, strong_quantile=0.85)
    top = sorted(rows, key=lambda r: int(r.count or 0), reverse=True)[:10]

    payload: dict = {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "snapshots": int(snap_count or 0),
        "buckets": len(rows),
        "eligible_buckets": cal.eligible_buckets,
        "status": cal.status,
        "current_tiers": cal.current_tiers,
        "recommended": cal.recommended,
        "bucket_bins": bucket_bins(counts),
        "top_buckets": [
            {
                "strategy_id": r.strategy_id,
                "count": int(r.count or 0),
                "signal_tier": r.signal_tier,
                "signal_score": float(r.signal_score) if r.signal_score is not None else None,
                "bucket_key": (r.bucket_key or "")[:100],
            }
            for r in top
        ],
    }

    stale: list[dict] = []
    if args.check_csv_stale:
        code_to_name = {v: k for k, v in FUTURES_CN_NAMES.items()}
        for item in discover(ROOT / "results"):
            if item["market"] != "FUTURES":
                continue
            sym = item["symbol"]
            batch = FUTURES_CN_NAMES.get(sym) or sym
            csv_path = ROOT / "data" / "futures" / "1d" / f"{batch}.csv"
            last = csv_last_date(csv_path)
            stale.append(
                {
                    "symbol": sym,
                    "batch_csv": str(csv_path.name),
                    "csv_last": last,
                    "trade_count": int(item.get("trade_count") or 0),
                    "result_dir": item["result_dir"],
                }
            )
        payload["futures_dirs"] = len(stale)

    json_path = out_dir / "futures_tier_audit.json"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    md = [
        "# FUTURES signal_tier 审计",
        "",
        f"- snapshots: **{payload['snapshots']}**",
        f"- buckets: **{payload['buckets']}** · eligible (N≥30): **{payload['eligible_buckets']}**",
        f"- status: **{payload['status']}**",
        f"- tier 分布: `{json.dumps(payload['current_tiers'], ensure_ascii=False)}`",
        f"- 桶分布: `{json.dumps(payload['bucket_bins'], ensure_ascii=False)}`",
        "",
        "## 裁定",
        "",
    ]
    if payload["eligible_buckets"] >= 30 and payload.get("recommended", {}).get("activate"):
        rec = payload["recommended"]
        md.extend(
            [
                f"eligible **{payload['eligible_buckets']}** ≥ 30 · 已可激活/维持分位 "
                f"`tier_medium={rec.get('tier_medium')}` / `tier_strong={rec.get('tier_strong')}`。",
                "FUTURES 使用 `futures_v2` 桶配置；CRYPTO/A_STOCK 仍为 V1。",
            ]
        )
    else:
        md.extend(
            [
                "维持旧分位直至 eligible≥30。",
                "瓶颈多为 **桶碎片化** 或 snapshot 不足，非 PG 导入缺失。",
            ]
        )
    md.extend(
        [
        "",
        "## Top buckets",
        "",
    ]
    )
    for row in payload["top_buckets"]:
        md.append(f"- {row['strategy_id']} count={row['count']} tier={row['signal_tier']} score={row['signal_score']}")
    md_path = out_dir / "futures_tier_audit.md"
    md_path.write_text("\n".join(md) + "\n", encoding="utf-8")

    print(json.dumps({k: payload[k] for k in ("snapshots", "buckets", "eligible_buckets", "status", "bucket_bins")}, ensure_ascii=False))
    print(f"saved {json_path}")
    print(f"saved {md_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
