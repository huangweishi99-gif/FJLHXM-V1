#!/usr/bin/env python3
"""Recalculate / reconcile domestic paper_state after tq_actual_main_contract switch.

Actions (with --apply):
  1. Archive open positions with entry_time < cutoff (default 2026-06-03).
  2. Re-supervise remaining opens against actual-contract CSV via fill_supervision.
  3. Archive opens that fail re-supervision (verdict=invalid) to audit_invalid_positions.

Does NOT delete history; does NOT auto-adjust equity (see apply_equity_rollback.py).
"""
from __future__ import annotations

import argparse
import json
import shutil
from contextlib import nullcontext
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]

try:
    from fengji_core.fill_supervision import (
        FillAuditResult,
        apply_radar_ohlcv_tail,
        audit_fill_record,
        build_os_detail_frame,
    )
    from fengji_core.state_lock import file_lock
except ImportError:
    import sys

    sys.path.insert(0, str(ROOT / "packages" / "fengji_core"))
    from fengji_core.fill_supervision import (
        FillAuditResult,
        apply_radar_ohlcv_tail,
        audit_fill_record,
        build_os_detail_frame,
    )
    from fengji_core.state_lock import file_lock


CUTOFF_DEFAULT = datetime(2026, 6, 3, 0, 0, 0)
REASON_CUTOFF = "main_contract_recalc: entry before tq_actual_main_contract cutoff"
REASON_INVALID = "main_contract_recalc: fill_supervision invalid under actual contract data"


def parse_dt(value: Any) -> datetime | None:
    text = str(value or "").strip()[:19]
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return None


def side_int(value: Any) -> int:
    text = str(value or "").strip().lower()
    if text in {"long", "buy", "1", "多"} or value == 1:
        return 1
    return -1


def futures_csv(data_dir: Path, symbol: str, tf: str) -> Path | None:
    code = str(symbol).upper().replace("USDT", "")
    candidates = [
        data_dir / "futures" / tf / f"{code}.csv",
        data_dir / "futures" / tf / f"{code}USDT.csv",
        data_dir / tf / f"{code}.csv",
        data_dir / tf / f"{code}USDT.csv",
    ]
    for path in candidates:
        if path.is_file():
            return path
    return None


def load_frame(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    if "timestamp" in df.columns and "date" not in df.columns:
        df = df.rename(columns={"timestamp": "date"})
    return df


def supervise_open(pos: dict[str, Any], *, data_dir: Path, gap: int) -> dict[str, Any]:
    symbol = str(pos.get("symbol") or "").upper()
    strategy = str(pos.get("strategy_id") or "").upper()
    tf = "15m" if strategy in {"DS07", "DS08", "DS09"} else "1h" if strategy in {"DS04", "DS06"} else "1d"
    csv_path = futures_csv(data_dir, symbol, tf)
    if csv_path is None:
        return {"verdict": "needs-data", "issues": [f"missing csv tf={tf}"], "order_id": pos.get("order_id")}
    record = {
        "symbol": symbol,
        "strategy_id": strategy,
        "side": side_int(pos.get("direction") or pos.get("side")),
        "entry_date": str(pos.get("entry_time") or "")[:10],
        "entry_time": pos.get("entry_time"),
        "trigger_price": pos.get("trigger_price") or pos.get("entry_price"),
        "stop_price": pos.get("initial_stop") or pos.get("current_stop"),
        "order_id": pos.get("order_id") or pos.get("key"),
        "setup_key": pos.get("setup_key") or "",
        "fill_time": pos.get("entry_time"),
        "bar_time": pos.get("entry_time"),
    }
    raw = load_frame(csv_path)
    raw = apply_radar_ohlcv_tail(raw, tf)
    os_df, engine = build_os_detail_frame(raw, gap=gap)
    result = audit_fill_record(record, os_df, engine)
    out = result.to_dict()
    out["csv"] = str(csv_path)
    return out


def archive_position(position: dict[str, Any], reason: str, audit_time: str) -> dict[str, Any]:
    invalid = dict(position)
    invalid.update(
        {
            "closed": True,
            "audit_invalid": True,
            "audit_invalid_at": audit_time,
            "audit_invalid_reason": reason,
            "audit_invalid_source": "recalc_domestic_main_contract_paper",
        }
    )
    return invalid


def recalc_state(
    state: dict[str, Any],
    *,
    data_dir: Path,
    cutoff: datetime,
    gap: int,
    apply: bool,
) -> dict[str, Any]:
    audit_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    report: dict[str, Any] = {
        "generated_at": audit_time,
        "cutoff": cutoff.isoformat(),
        "apply": apply,
        "archived_before_cutoff": [],
        "archived_invalid_supervision": [],
        "supervision": [],
        "kept_open": [],
    }
    symbols = state.get("symbols") or {}
    if not isinstance(symbols, dict):
        return report

    for sym, bucket in symbols.items():
        if not isinstance(bucket, dict):
            continue
        kept: list[dict[str, Any]] = []
        for pos in bucket.get("open_positions") or []:
            if not isinstance(pos, dict) or pos.get("closed"):
                kept.append(pos)
                continue
            entry_dt = parse_dt(pos.get("entry_time"))
            order_id = str(pos.get("order_id") or pos.get("key") or "")
            row_base = {
                "symbol": str(pos.get("symbol") or sym).upper(),
                "strategy_id": str(pos.get("strategy_id") or ""),
                "entry_time": pos.get("entry_time"),
                "order_id": order_id,
            }
            if entry_dt and entry_dt < cutoff:
                report["archived_before_cutoff"].append({**row_base, "reason": REASON_CUTOFF})
                if apply:
                    bucket.setdefault("audit_invalid_positions", []).append(
                        archive_position(pos, REASON_CUTOFF, audit_time)
                    )
                    if order_id:
                        bucket.setdefault("audit_invalid_entries", []).append(order_id)
                        bucket.setdefault("closed_entries", []).append(order_id)
                continue

            sup = supervise_open(pos, data_dir=data_dir, gap=gap)
            sup_row = {**row_base, **sup}
            report["supervision"].append(sup_row)
            if sup.get("verdict") == "invalid":
                report["archived_invalid_supervision"].append(sup_row)
                if apply:
                    reason = f"{REASON_INVALID}: {'; '.join(sup.get('issues') or [])}"
                    bucket.setdefault("audit_invalid_positions", []).append(
                        archive_position(pos, reason, audit_time)
                    )
                    if order_id:
                        bucket.setdefault("audit_invalid_entries", []).append(order_id)
                        bucket.setdefault("closed_entries", []).append(order_id)
                continue

            kept.append(pos)
            report["kept_open"].append(row_base)

        if apply:
            bucket["open_positions"] = kept
            bucket["last_updated"] = audit_time

    if apply and (report["archived_before_cutoff"] or report["archived_invalid_supervision"]):
        state["last_main_contract_recalc_at"] = audit_time
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--state", default=str(ROOT / "runtime" / "domestic_paper_state.json"))
    parser.add_argument("--data-dir", default=str(ROOT / "data"))
    parser.add_argument("--cutoff", default="2026-06-03")
    parser.add_argument("--gap", type=int, default=3)
    parser.add_argument("--out", default=str(ROOT / "results" / "main_contract_paper_recalc_20260618" / "report.json"))
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    state_path = Path(args.state)
    cutoff = datetime.strptime(args.cutoff, "%Y-%m-%d")
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    lock_cm = file_lock(state_path) if args.apply else nullcontext()
    with lock_cm:
        state = json.loads(state_path.read_text(encoding="utf-8"))
        if args.apply and state_path.is_file():
            backup = state_path.with_suffix(state_path.suffix + ".pre_main_contract_recalc.bak")
            if not backup.exists():
                shutil.copy2(state_path, backup)
        report = recalc_state(
            state,
            data_dir=Path(args.data_dir),
            cutoff=cutoff,
            gap=args.gap,
            apply=args.apply,
        )
        if args.apply:
            tmp = state_path.with_suffix(".tmp")
            tmp.write_text(json.dumps(state, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
            tmp.replace(state_path)

    out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        f"cutoff_archive={len(report['archived_before_cutoff'])} "
        f"invalid_archive={len(report['archived_invalid_supervision'])} "
        f"kept={len(report['kept_open'])} apply={args.apply} report={out_path}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
