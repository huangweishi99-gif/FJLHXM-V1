"""Audit simulated paper fills against FengJi open logic (post-fill supervision)."""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PKG = ROOT / "packages" / "fengji_core"
if str(PKG) not in sys.path:
    sys.path.insert(0, str(PKG))

from fengji_core.fill_supervision import (  # noqa: E402
    FillAuditResult,
    apply_radar_ohlcv_tail,
    audit_fill_record,
    build_os_detail_frame,
    infer_record_timeframe,
    load_d1_csv,
    load_exec_gap_order_ids,
    parse_events_jsonl,
    resolve_ohlcv_csv,
)
from fengji_core.futures_main_contract import detect_order_contract_switch, load_manifest  # noqa: E402

PROFILES = {
    "domestic": {
        "events": "runtime/fengji_pending_orders/events.jsonl",
        "data_dir": "data",
        "market": "domestic",
    },
    "overseas": {
        "events": "runtime/fengji_pending_orders/events.jsonl",
        "data_dir": "data",
        "market": "crypto",
    },
}


def now_text() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def audit_exit_code(
    *,
    fail_on_invalid: bool,
    new_invalid_count: int,
    needs_data_count: int,
    invalid_count: int,
) -> int:
    """Watchdog exit: 2=new invalid; with --fail-on-invalid, needs_data alone is not a failure."""
    if fail_on_invalid and new_invalid_count:
        return 2
    if fail_on_invalid:
        return 0
    if needs_data_count and not invalid_count:
        return 1
    return 0


def dedupe_fills(fills: list[dict]) -> list[dict]:
    seen: set[str] = set()
    out: list[dict] = []
    for row in fills:
        key = str(row.get("order_id") or row.get("setup_key") or f"{row.get('symbol')}|{row.get('time')}")
        if key in seen:
            continue
        seen.add(key)
        out.append(row)
    return out


def audit_fills(
    fills: list[dict],
    data_dir: Path,
    market: str,
    gap: int,
    contract_manifest: dict | None = None,
) -> tuple[list[FillAuditResult], dict[str, tuple]]:
    cache: dict[str, tuple] = {}
    results: list[FillAuditResult] = []

    for record in fills:
        symbol = str(record.get("symbol", ""))
        if not symbol:
            results.append(
                FillAuditResult(
                    strategy_id=str(record.get("strategy_id", "")),
                    symbol="",
                    side=str(record.get("side", "")),
                    entry_date=str(record.get("bar_time", "")),
                    verdict="needs-data",
                    issues=["missing symbol"],
                    order_id=str(record.get("order_id", "")),
                )
            )
            continue

        if market == "domestic":
            contract_switch = detect_order_contract_switch(
                record,
                contract_manifest,
                observed_at=record.get("time") or record.get("fill_time"),
            )
            if contract_switch is not None:
                results.append(
                    FillAuditResult(
                        strategy_id=str(record.get("strategy_id", record.get("strategy", ""))).upper(),
                        symbol=symbol,
                        side=str(record.get("side", "")),
                        entry_date=str(record.get("bar_time", record.get("entry_date", ""))),
                        verdict="exec_gap",
                        issues=["main contract switched between order creation and simulated fill"],
                        checks={"contract_switch": contract_switch},
                        order_id=str(record.get("order_id", "")),
                        setup_key=str(record.get("setup_key", "")),
                        fill_time=str(record.get("time", "")),
                    )
                )
                continue

        tf = infer_record_timeframe(record)
        cache_key = (symbol, tf)
        if cache_key not in cache:
            csv_path = resolve_ohlcv_csv(data_dir, symbol, tf, market=market)
            if csv_path is None:
                cache[cache_key] = (None, None)
            else:
                raw = load_d1_csv(csv_path)
                raw = apply_radar_ohlcv_tail(raw, tf)
                cache[cache_key] = build_os_detail_frame(raw, gap=gap)

        os_df, engine = cache[cache_key]
        d1_os_df = None
        strategy = str(record.get("strategy_id", record.get("strategy", ""))).upper()
        if strategy == "DS07":
            d1_key = (symbol, "1d")
            if d1_key not in cache:
                d1_csv = resolve_ohlcv_csv(data_dir, symbol, "1d", market=market)
                if d1_csv is None:
                    cache[d1_key] = (None, None)
                else:
                    raw_d1 = load_d1_csv(d1_csv)
                    raw_d1 = apply_radar_ohlcv_tail(raw_d1, "1d")
                    cache[d1_key] = build_os_detail_frame(raw_d1, gap=gap)
            d1_os_df, _ = cache[d1_key]

        if os_df is None or engine is None:
            res = FillAuditResult(
                strategy_id=str(record.get("strategy_id", record.get("strategy", ""))).upper(),
                symbol=symbol,
                side=str(record.get("side", "")),
                entry_date=str(record.get("bar_time", "")),
                verdict="needs-data",
                issues=[f"no {tf} csv under {data_dir} for {symbol}"],
                order_id=str(record.get("order_id", "")),
                setup_key=str(record.get("setup_key", "")),
                fill_time=str(record.get("time", "")),
            )
            results.append(res)
            continue

        results.append(audit_fill_record(record, os_df, engine, d1_os_df=d1_os_df, market=market))

    return results, cache


def load_ack_order_ids(ack_path: Path) -> set[str]:
    """已人工确认的 invalid order_id 集合（M4 清单处置后登记，不再重复告警）。"""
    if not ack_path.exists():
        return set()
    try:
        payload = json.loads(ack_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return set()
    if isinstance(payload, dict):
        rows = payload.get("acknowledged", payload)
        if isinstance(rows, dict):
            return {str(k) for k in rows.keys() if k}
        if isinstance(rows, list):
            payload = rows
        else:
            return set()
    if isinstance(payload, list):
        out: set[str] = set()
        for item in payload:
            if isinstance(item, str):
                out.add(item)
            elif isinstance(item, dict) and item.get("order_id"):
                out.add(str(item["order_id"]))
        return out
    return set()


def write_report(
    out_dir: Path,
    profile: str,
    results: list[FillAuditResult],
    fills_count: int,
    ack_ids: set[str] | None = None,
    exec_gap_ids: set[str] | None = None,
) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = out_dir / f"fill_supervision_{profile}_{stamp}.json"
    invalid = [r for r in results if r.verdict == "invalid"]
    needs_data = [r for r in results if r.verdict == "needs-data"]
    valid = [r for r in results if r.verdict == "valid"]
    skipped = [r for r in results if r.verdict == "skipped"]
    exec_gap = [r for r in results if r.verdict == "exec_gap"]
    ack_ids = ack_ids or set()
    exec_gap_ids = exec_gap_ids or set()
    invalid_ack = [r for r in invalid if r.order_id in ack_ids]
    invalid_new = [r for r in invalid if r.order_id not in ack_ids]

    payload = {
        "generated_at": now_text(),
        "profile": profile,
        "fills_scanned": fills_count,
        "summary": {
            "valid": len(valid),
            "invalid": len(invalid),
            "invalid_acknowledged": len(invalid_ack),
            "invalid_new": len(invalid_new),
            "exec_gap": len(exec_gap),
            "needs_data": len(needs_data),
            "skipped": len(skipped),
        },
        "invalid_fills": [r.to_dict() for r in invalid],
        "invalid_new_fills": [r.to_dict() for r in invalid_new],
        "exec_gap_fills": [r.to_dict() for r in exec_gap],
        "needs_data": [r.to_dict() for r in needs_data],
        "all_results": [r.to_dict() for r in results],
    }
    report_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    latest = out_dir / f"fill_supervision_{profile}_latest.json"
    latest.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return report_path


def append_audited_events(events_path: Path, results: list[FillAuditResult]) -> int:
    if not events_path.exists():
        return 0
    count = 0
    with events_path.open("a", encoding="utf-8") as handle:
        for res in results:
            if res.verdict not in {"valid", "invalid"}:
                continue
            row = {
                "time": now_text(),
                "event_type": "fill_audited",
                "order_id": res.order_id,
                "setup_key": res.setup_key,
                "symbol": res.symbol,
                "strategy_id": res.strategy_id,
                "side": res.side,
                "entry_date": res.entry_date,
                "audit_verdict": res.verdict,
                "audit_issues": res.issues,
            }
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
            count += 1
    return count


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Post-fill supervision: audit simulated opens against DS01 rules.")
    parser.add_argument("--root", default=str(ROOT), help="Project root")
    parser.add_argument(
        "--profile",
        choices=sorted(PROFILES.keys()),
        default="domestic",
        help="Runtime profile (paths preset)",
    )
    parser.add_argument("--events", help="Override events.jsonl path")
    parser.add_argument("--data-dir", help="Override K-line data directory")
    parser.add_argument("--since-hours", type=float, default=168.0, help="Only audit fills within N hours (0=all)")
    parser.add_argument("--gap", type=int, default=3, help="OS gap for rebuild")
    parser.add_argument(
        "--out-dir",
        default="runtime/logs/fill_supervision",
        help="JSON report output directory",
    )
    parser.add_argument("--append-events", action="store_true", help="Append fill_audited rows to events.jsonl")
    parser.add_argument("--fail-on-invalid", action="store_true", help="Exit code 2 when any NEW (unacknowledged) invalid fill found")
    parser.add_argument(
        "--ack-file",
        default="runtime/fill_supervision_acknowledged.json",
        help="JSON list of acknowledged invalid order_ids (skip re-alerting)",
    )
    parser.add_argument(
        "--exec-gap-file",
        default="runtime/fill_exec_gap_acknowledged.json",
        help="JSON registry of EXEC_GAP order_ids (structure valid, execution deviation)",
    )
    parser.add_argument("--quiet", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = Path(args.root)
    preset = PROFILES[args.profile]
    events_path = Path(args.events) if args.events else root / preset["events"]
    if args.data_dir:
        data_dir = Path(args.data_dir)
    elif preset["market"] == "crypto":
        snap = root / "runtime" / "audit_overseas_snapshot"
        if (snap / "1d").is_dir() and any((snap / "1d").glob("*.csv")):
            data_dir = snap
        else:
            data_dir = root / preset["data_dir"]
    else:
        data_dir = root / preset["data_dir"]
    out_dir = root / args.out_dir

    since = None if args.since_hours <= 0 else args.since_hours
    fills = dedupe_fills(parse_events_jsonl(events_path, since_hours=since))
    contract_manifest = load_manifest(root) if preset["market"] == "domestic" else {}
    results, _ = audit_fills(
        fills,
        data_dir,
        market=preset["market"],
        gap=args.gap,
        contract_manifest=contract_manifest,
    )
    ack_ids = load_ack_order_ids(root / args.ack_file)
    exec_gap_ids = load_exec_gap_order_ids(root / args.exec_gap_file)
    report_path = write_report(
        out_dir, args.profile, results, len(fills), ack_ids=ack_ids, exec_gap_ids=exec_gap_ids
    )

    invalid = [r for r in results if r.verdict == "invalid"]
    new_invalid = [r for r in invalid if r.order_id not in ack_ids]
    exec_gap = [r for r in results if r.verdict == "exec_gap"]
    needs_data = [r for r in results if r.verdict == "needs-data"]

    if not args.quiet:
        print(f"[fill_supervision] profile={args.profile} fills={len(fills)} report={report_path}")
        print(
            f"  valid={sum(1 for r in results if r.verdict == 'valid')} "
            f"invalid={len(invalid)} (new={len(new_invalid)} ack={len(invalid) - len(new_invalid)}) "
            f"exec_gap={len(exec_gap)} "
            f"needs_data={len(needs_data)} "
            f"skipped={sum(1 for r in results if r.verdict == 'skipped')}"
        )
        for row in invalid:
            tag = "INVALID" if row.order_id not in ack_ids else "INVALID(ack)"
            print(f"  {tag} {row.symbol} {row.strategy_id} {row.side} {row.entry_date}: {row.issues}")

    if args.append_events and results:
        n = append_audited_events(events_path, results)
        if not args.quiet:
            print(f"  appended fill_audited events: {n}")

    return audit_exit_code(
        fail_on_invalid=args.fail_on_invalid,
        new_invalid_count=len(new_invalid),
        needs_data_count=len(needs_data),
        invalid_count=len(invalid),
    )


if __name__ == "__main__":
    raise SystemExit(main())
