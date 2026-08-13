from __future__ import annotations

import argparse
import json
import socket
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

import sys

ROOT = Path(__file__).resolve().parents[1]
for rel in ("services", "packages/fengji_core", "src"):
    path = str(ROOT / rel)
    if path not in sys.path:
        sys.path.insert(0, path)

from db.models import ContextBucketStat  # noqa: E402
from db.session import get_database_url, get_engine  # noqa: E402


DEFAULT_MARKETS = ("A_STOCK", "CRYPTO", "FUTURES")
DEFAULT_WEIGHTS = {"w_wr": 0.45, "w_r": 0.35, "w_conf": 0.20}


@dataclass
class CalibrationResult:
    market: str
    status: str
    total_buckets: int
    eligible_buckets: int
    total_bucket_trades: int
    eligible_bucket_trades: int
    min_bucket_samples: int
    min_eligible_buckets: int
    current_tiers: dict[str, int]
    score_quantiles_all: dict[str, float | None]
    score_quantiles_eligible: dict[str, float | None]
    recommended: dict[str, Any]
    note: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Calibrate context signal tiers per market from PG bucket stats.")
    parser.add_argument("--markets", default=",".join(DEFAULT_MARKETS), help="Comma-separated markets to calibrate.")
    parser.add_argument("--min-bucket-samples", type=int, default=30)
    parser.add_argument("--min-eligible-buckets", type=int, default=30)
    parser.add_argument("--medium-quantile", type=float, default=0.50)
    parser.add_argument("--strong-quantile", type=float, default=0.85)
    parser.add_argument("--out-dir", default="results/context_market_calibration_2026-06-02")
    parser.add_argument("--connect-timeout", type=float, default=3.0)
    return parser.parse_args()


def assert_database_port_reachable(timeout: float) -> None:
    url = make_url(get_database_url())
    host = url.host or "localhost"
    port = int(url.port or 5432)
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return
    except OSError as exc:
        raise RuntimeError(
            f"database is not reachable at {host}:{port}; run `docker compose up -d` first"
        ) from exc


def quantile(values: list[float], q: float) -> float | None:
    if not values:
        return None
    vals = sorted(values)
    idx = round((len(vals) - 1) * q)
    return round(float(vals[idx]), 6)


def quantile_map(values: list[float]) -> dict[str, float | None]:
    return {
        "q50": quantile(values, 0.50),
        "q70": quantile(values, 0.70),
        "q85": quantile(values, 0.85),
        "q90": quantile(values, 0.90),
        "q95": quantile(values, 0.95),
    }


def calibrate_market(
    market: str,
    rows: list[ContextBucketStat],
    *,
    min_bucket_samples: int,
    min_eligible_buckets: int,
    medium_quantile: float,
    strong_quantile: float,
) -> CalibrationResult:
    total_buckets = len(rows)
    total_bucket_trades = sum(int(r.count or 0) for r in rows)
    current_tiers = dict(Counter(str(r.signal_tier or "UNKNOWN") for r in rows))
    scored = [float(r.signal_score) for r in rows if r.signal_score is not None]
    eligible = [
        r
        for r in rows
        if int(r.count or 0) >= min_bucket_samples and r.signal_score is not None
    ]
    eligible_scores = [float(r.signal_score) for r in eligible]
    eligible_trades = sum(int(r.count or 0) for r in eligible)

    if len(eligible) < min_eligible_buckets:
        recommended = {
            "activate": False,
            "tier_medium": None,
            "tier_strong": None,
            "min_bucket_samples": min_bucket_samples,
            **DEFAULT_WEIGHTS,
        }
        note = (
            f"eligible buckets {len(eligible)} < {min_eligible_buckets}; keep current/default thresholds "
            "and collect more samples before activation"
        )
        status = "INSUFFICIENT_MARKET_DATA"
    else:
        tier_medium = quantile(eligible_scores, medium_quantile)
        tier_strong = quantile(eligible_scores, strong_quantile)
        if tier_medium is not None and tier_strong is not None and tier_medium >= tier_strong:
            tier_strong = round(min(1.0, tier_medium + 0.01), 6)
        recommended = {
            "activate": True,
            "tier_medium": tier_medium,
            "tier_strong": tier_strong,
            "min_bucket_samples": min_bucket_samples,
            **DEFAULT_WEIGHTS,
        }
        note = (
            f"thresholds from eligible bucket score quantiles: medium=q{int(medium_quantile*100)}, "
            f"strong=q{int(strong_quantile*100)}; weights unchanged pending out-of-sample validation"
        )
        status = "READY_FOR_REVIEW"

    return CalibrationResult(
        market=market,
        status=status,
        total_buckets=total_buckets,
        eligible_buckets=len(eligible),
        total_bucket_trades=total_bucket_trades,
        eligible_bucket_trades=eligible_trades,
        min_bucket_samples=min_bucket_samples,
        min_eligible_buckets=min_eligible_buckets,
        current_tiers=current_tiers,
        score_quantiles_all=quantile_map(scored),
        score_quantiles_eligible=quantile_map(eligible_scores),
        recommended=recommended,
        note=note,
    )


def load_existing_config(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def markdown_report(results: list[CalibrationResult], existing: dict[str, Any] | None) -> str:
    lines: list[str] = []
    lines.append("# Context Market Calibration Report 2026-06-02")
    lines.append("")
    lines.append("## Scope")
    lines.append("")
    lines.append("- Data source: PostgreSQL `context_bucket_stats`.")
    lines.append("- Target markets: A_STOCK, CRYPTO, FUTURES.")
    lines.append("- This report does not change FengJi OS rules or DS01-DS09 strategy logic.")
    lines.append(
        "- Recommended thresholds are candidates unless the existing config row already matches; "
        "matching rows are active in `data/context_market_calibration.json` after PG rebuild."
    )
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append("| market | status | buckets | eligible buckets | trades in buckets | recommended medium | recommended strong | note |")
    lines.append("| --- | --- | ---: | ---: | ---: | ---: | ---: | --- |")
    for r in results:
        rec = r.recommended
        lines.append(
            "| {market} | {status} | {buckets} | {eligible} | {trades} | {medium} | {strong} | {note} |".format(
                market=r.market,
                status=r.status,
                buckets=r.total_buckets,
                eligible=r.eligible_buckets,
                trades=r.total_bucket_trades,
                medium=rec.get("tier_medium"),
                strong=rec.get("tier_strong"),
                note=r.note.replace("|", "/"),
            )
        )
    lines.append("")
    lines.append("## Existing Config Comparison")
    lines.append("")
    if not existing:
        lines.append("- No existing `data/context_market_calibration.json` found.")
    else:
        markets = existing.get("markets", {})
        lines.append("| market | existing medium | existing strong | candidate medium | candidate strong | action |")
        lines.append("| --- | ---: | ---: | ---: | ---: | --- |")
        for r in results:
            cur = markets.get(r.market, {})
            action = "review candidate" if r.recommended.get("activate") else "do not activate yet"
            lines.append(
                f"| {r.market} | {cur.get('tier_medium')} | {cur.get('tier_strong')} | "
                f"{r.recommended.get('tier_medium')} | {r.recommended.get('tier_strong')} | {action} |"
            )
    lines.append("")
    lines.append("## Market Details")
    for r in results:
        lines.append("")
        lines.append(f"### {r.market}")
        lines.append("")
        lines.append(f"- Status: `{r.status}`")
        lines.append(f"- Current tiers: `{json.dumps(r.current_tiers, ensure_ascii=False)}`")
        lines.append(f"- All-score quantiles: `{json.dumps(r.score_quantiles_all, ensure_ascii=False)}`")
        lines.append(f"- Eligible-score quantiles: `{json.dumps(r.score_quantiles_eligible, ensure_ascii=False)}`")
        lines.append(f"- Recommendation: `{json.dumps(r.recommended, ensure_ascii=False)}`")
    lines.append("")
    lines.append("## Next Step")
    lines.append("")
    active_markets = [r.market for r in results if r.recommended.get("activate")]
    inactive_markets = [r.market for r in results if not r.recommended.get("activate")]
    active_text = ", ".join(active_markets) if active_markets else "none"
    inactive_text = ", ".join(inactive_markets) if inactive_markets else "none"
    lines.append(f"1. Keep active market thresholds in sync after each PG rebuild: {active_text}.")
    lines.append(f"2. Keep inactive markets collecting samples until enough eligible buckets exist: {inactive_text}.")
    lines.append("3. Rebuild PG bucket stats and rerun API consistency smoke after any calibration change.")
    return "\n".join(lines) + "\n"


def main() -> int:
    args = parse_args()
    assert_database_port_reachable(args.connect_timeout)
    markets = [m.strip().upper() for m in args.markets.split(",") if m.strip()]
    out_dir = ROOT / args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    with Session(get_engine()) as session:
        all_rows = session.scalars(select(ContextBucketStat).where(ContextBucketStat.market.in_(markets))).all()

    by_market: dict[str, list[ContextBucketStat]] = {m: [] for m in markets}
    for row in all_rows:
        by_market.setdefault(row.market, []).append(row)

    results = [
        calibrate_market(
            market,
            by_market.get(market, []),
            min_bucket_samples=args.min_bucket_samples,
            min_eligible_buckets=args.min_eligible_buckets,
            medium_quantile=args.medium_quantile,
            strong_quantile=args.strong_quantile,
        )
        for market in markets
    ]

    existing = load_existing_config(ROOT / "data" / "context_market_calibration.json")
    candidate = {
        "version": "candidate-2026-06-02",
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "source": "postgresql.context_bucket_stats",
        "activation_policy": "Only activate markets with status READY_FOR_REVIEW after manual review.",
        "markets": {r.market: r.recommended for r in results},
        "audit": {r.market: asdict(r) for r in results},
    }
    json_path = out_dir / "context_market_calibration_candidate.json"
    report_path = out_dir / "CONTEXT_MARKET_CALIBRATION_REPORT.md"
    json_path.write_text(json.dumps(candidate, ensure_ascii=False, indent=2), encoding="utf-8")
    report_path.write_text(markdown_report(results, existing), encoding="utf-8")

    print(f"saved_json={json_path}")
    print(f"saved_report={report_path}")
    for r in results:
        print(
            f"{r.market} status={r.status} eligible={r.eligible_buckets}/{r.total_buckets} "
            f"medium={r.recommended.get('tier_medium')} strong={r.recommended.get('tier_strong')}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
