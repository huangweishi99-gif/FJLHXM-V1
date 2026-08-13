#!/usr/bin/env python3
"""Batch DS01 audit sandboxes for all M5 B-zone fills (S2 continuation)."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DRAFT = ROOT / "runtime" / "m5_b_zone_disposition_draft.json"
SCRIPT = ROOT / "scripts" / "plot_ds01_audit_sandbox.py"
OUT = ROOT / "results" / "m5_samples"

SKIP_ORDER_IDS = {
    "BNBUSDT-DS01-D1-long-ebfd3882424f3fc6",  # dedicated plot_bnb_ds01_audit_sandbox
    "AGUSDT-DS01-D1-short-756e2840d226d53c",  # S2 representative already plotted
}


def csv_path(symbol: str, profile: str) -> tuple[Path, str]:
    sym = symbol.strip().upper()
    if profile == "domestic":
        short = sym.replace("USDT", "")
        return ROOT / "data" / "1d" / f"{short}.csv", "futures"
    candidates = [
        ROOT / "data" / "1d" / f"{sym}.csv",
        ROOT / "data" / "overseas_1d" / f"{sym}.csv",
    ]
    for p in candidates:
        if p.exists():
            return p, "crypto"
    return candidates[0], "crypto"


def out_path(symbol: str, entry_date: str, order_id: str) -> Path:
    tag = order_id.split("-")[-1][:8]
    return OUT / f"{symbol}_ds01_audit_{entry_date.replace('-', '')}_{tag}.png"


def window(entry_date: str) -> tuple[str, str]:
    ts = __import__("pandas").Timestamp(entry_date)
    return str((ts - timedelta(days=35)).date()), str((ts + timedelta(days=14)).date())


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", choices=("domestic", "overseas", "all"), default="all")
    parser.add_argument("--skip-existing", action="store_true")
    args = parser.parse_args()

    if not DRAFT.exists():
        print(f"missing {DRAFT}", file=sys.stderr)
        return 1
    draft = json.loads(DRAFT.read_text(encoding="utf-8"))
    rows = draft.get("rows") or []
    ok, skip, fail = 0, 0, 0
    summary: list[dict] = []

    for row in rows:
        oid = str(row.get("order_id") or "")
        prof = str(row.get("profile") or "")
        if prof not in ("domestic", "overseas"):
            continue
        if args.profile != "all" and prof != args.profile:
            continue
        if oid in SKIP_ORDER_IDS:
            skip += 1
            continue
        symbol = str(row["symbol"])
        side = str(row["side"])
        entry_date = str(row["entry_date"])
        checks = row.get("checks") or {}
        fill_price = checks.get("fill_price") or checks.get("trigger_calc")
        if fill_price is None:
            skip += 1
            summary.append({"order_id": oid, "status": "skip_no_price"})
            continue
        csv, market = csv_path(symbol, prof)
        if not csv.exists():
            skip += 1
            summary.append({"order_id": oid, "status": "skip_no_csv", "csv": str(csv)})
            continue
        out = out_path(symbol, entry_date, oid)
        if args.skip_existing and out.exists():
            skip += 1
            continue
        start, end = window(entry_date)
        tag = oid.split("-")[-1][:8]
        verdict = str(row.get("issues_summary") or "")[:120]
        cmd = [
            sys.executable,
            str(SCRIPT),
            "--csv", str(csv),
            "--market", market,
            "--symbol", symbol,
            "--side", side,
            "--entry-date", entry_date,
            "--fill-price", str(float(fill_price)),
            "--start", start,
            "--end", end,
            "--order-tag", tag,
            "--verdict", verdict,
            "--out", str(out),
        ]
        proc = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True, encoding="utf-8", errors="replace")
        if proc.returncode == 0:
            ok += 1
            summary.append({"order_id": oid, "status": "ok", "png": out.name})
            print(proc.stdout.strip() or f"OK {oid} -> {out.name}")
        else:
            fail += 1
            summary.append({"order_id": oid, "status": "fail", "err": (proc.stderr or proc.stdout)[-200:]})
            print(f"FAIL {oid}: {(proc.stderr or proc.stdout)[-120:]}", file=sys.stderr)

    manifest = OUT / "m5_b_zone_ds01_batch_manifest.json"
    manifest.write_text(json.dumps({"ok": ok, "skip": skip, "fail": fail, "rows": summary}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"batch done ok={ok} skip={skip} fail={fail} manifest={manifest}")
    return 1 if fail else 0


if __name__ == "__main__":
    raise SystemExit(main())
