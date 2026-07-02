#!/usr/bin/env python
"""批量将 results/ 下 trade_context_snapshots.csv 导入 PostgreSQL，并重算全局 bucket stats。"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services"))
sys.path.insert(0, str(ROOT / "packages" / "fengji_core"))

from db.context_queries import import_snapshots_csv, rebuild_global_bucket_stats  # noqa: E402
from db.models import ContextBucketStat, TradeContextSnapshot  # noqa: E402
from db.session import get_engine  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402


def truncate_snapshot_tables() -> None:
    engine = get_engine()
    with Session(engine) as session:
        session.query(ContextBucketStat).delete(synchronize_session=False)
        session.query(TradeContextSnapshot).delete(synchronize_session=False)
        session.commit()


def discover_snapshot_dirs(root: Path) -> list[Path]:
    dirs: list[Path] = []
    seen: set[str] = set()
    for path in root.rglob("trade_context_snapshots.csv"):
        d = path.parent.resolve()
        key = str(d)
        if key in seen:
            continue
        seen.add(key)
        dirs.append(d)
    dirs.sort(key=lambda p: str(p))
    return dirs


def main() -> int:
    parser = argparse.ArgumentParser(description="Batch import context snapshots into PostgreSQL.")
    parser.add_argument("--root", default=str(ROOT / "results"))
    parser.add_argument("--limit", type=int, default=0, help="Max dirs (0=all)")
    parser.add_argument("--skip-rebuild", action="store_true", help="Skip global bucket rebuild")
    parser.add_argument(
        "--fresh",
        action="store_true",
        help="Truncate trade_context_snapshots + context_bucket_stats before import",
    )
    parser.add_argument("--log", default=str(ROOT / "results" / "context_import_pg_log.json"))
    args = parser.parse_args()

    if args.fresh:
        print("Truncating PG snapshot tables ...")
        truncate_snapshot_tables()

    dirs = discover_snapshot_dirs(Path(args.root))
    if args.limit > 0:
        dirs = dirs[: args.limit]

    ok, fail = 0, 0
    imported_snaps = 0
    log: list[dict] = []
    for result_dir in dirs:
        try:
            n = import_snapshots_csv(result_dir, replace=True)
            print(f"OK {n} snapshots <- {result_dir}")
            log.append({"result_dir": str(result_dir), "status": "ok", "snapshots": n})
            ok += 1
            imported_snaps += n
        except Exception as exc:
            print(f"FAIL {result_dir}: {exc}")
            log.append({"result_dir": str(result_dir), "status": "error", "error": str(exc)})
            fail += 1

    rebuild_counts = {"snapshots": 0, "buckets": 0}
    if not args.skip_rebuild and ok > 0:
        print("Rebuilding global bucket stats ...")
        rebuild_counts = rebuild_global_bucket_stats()
        print(f"rebuilt buckets={rebuild_counts['buckets']} from snapshots={rebuild_counts['snapshots']}")

    summary = {
        "dirs_ok": ok,
        "dirs_fail": fail,
        "imported_snapshots": imported_snaps,
        "rebuild": rebuild_counts,
        "items": log,
    }
    Path(args.log).write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"done dirs_ok={ok} dirs_fail={fail} snapshots={imported_snaps} log={args.log}")
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
