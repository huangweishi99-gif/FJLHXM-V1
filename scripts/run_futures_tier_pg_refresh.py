"""Import FUTURES context snapshots into PG, rebuild bucket stats, re-run tier audit."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "services"))
sys.path.insert(0, str(ROOT / "packages" / "fengji_core"))

from db.context_queries import import_snapshots_csv, rebuild_global_bucket_stats  # noqa: E402
from discover_backtest_results import discover  # noqa: E402


def futures_context_dirs(results_root: Path) -> list[Path]:
    dirs: list[Path] = []
    seen: set[str] = set()
    for item in discover(results_root):
        if item.get("market") != "FUTURES":
            continue
        d = Path(item["result_dir"])
        csv_path = d / "trade_context_snapshots.csv"
        if not csv_path.exists():
            continue
        key = str(d.resolve())
        if key in seen:
            continue
        seen.add(key)
        dirs.append(d)
    dirs.sort(key=lambda p: str(p))
    return dirs


def main() -> int:
    parser = argparse.ArgumentParser(description="Refresh FUTURES context in PG and audit tier eligibility.")
    parser.add_argument("--results-root", default=str(ROOT / "results"))
    parser.add_argument("--out-dir", default=str(ROOT / "results" / "futures_tier_pg_refresh"))
    parser.add_argument("--skip-audit", action="store_true")
    parser.add_argument("--dry-run", action="store_true", help="List dirs only; no PG writes")
    args = parser.parse_args()

    dirs = futures_context_dirs(Path(args.results_root))
    summary: dict = {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "futures_dirs": len(dirs),
        "imported": [],
        "errors": [],
    }

    if args.dry_run:
        for d in dirs:
            print(f"WOULD_IMPORT {d}")
        print(f"DRY_RUN futures_dirs={len(dirs)}")
        return 0

    imported = 0
    snapshots = 0
    for result_dir in dirs:
        try:
            n = import_snapshots_csv(result_dir, replace=True)
            summary["imported"].append({"result_dir": str(result_dir), "snapshots": n})
            imported += 1
            snapshots += n
            print(f"OK {n} <- {result_dir.name}")
        except Exception as exc:
            summary["errors"].append({"result_dir": str(result_dir), "error": str(exc)})
            print(f"FAIL {result_dir}: {exc}")

    if imported and not summary["errors"]:
        print("Rebuilding global bucket stats ...")
        rebuild = rebuild_global_bucket_stats()
        summary["rebuild"] = rebuild

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    log_path = out_dir / "futures_pg_refresh_log.json"
    summary["import_ok"] = imported
    summary["snapshots_imported"] = snapshots
    log_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Saved {log_path}")

    if summary["errors"]:
        return 1

    if not args.skip_audit:
        audit_dir = out_dir / "audit"
        cmd = [
            sys.executable,
            str(ROOT / "scripts" / "report_futures_tier_eligibility.py"),
            "--out-dir",
            str(audit_dir),
        ]
        print("Running tier audit ...")
        proc = subprocess.run(cmd, cwd=str(ROOT))
        return proc.returncode

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
