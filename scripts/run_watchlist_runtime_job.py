from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
for item in (ROOT / "services", ROOT / "src"):
    if str(item) not in sys.path:
        sys.path.insert(0, str(item))

from db.paper_watchlist import (  # noqa: E402
    WATCHLIST_STATUS_PENDING_RUNTIME,
    list_distinct_watchlist_user_ids,
    list_paper_watchlist,
)
from watchlist_runtime import build_watchlist_runtime_snapshots  # noqa: E402
from watchlist_runtime_file_cache import save_watchlist_runtime_cache  # noqa: E402


def build_watchlist_runtime_cache_payload(
    *,
    user_id: str,
    status: str = WATCHLIST_STATUS_PENDING_RUNTIME,
    limit: int = 100,
    include_signal_preview: bool = True,
    rows: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    watchlist_rows = rows if rows is not None else list_paper_watchlist(user_id=user_id, status=status, limit=limit)
    snapshots = build_watchlist_runtime_snapshots(watchlist_rows, include_signal_preview=include_signal_preview)
    return {
        "user_id": user_id,
        "mode": "read_only_observation",
        "runtime_binding": "file_cache_signal_preview" if include_signal_preview else "file_cache_snapshot_only",
        "status_filter": status,
        "limit": limit,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "count": len(snapshots),
        "items": snapshots,
    }


def run_watchlist_runtime_job_for_user(
    *,
    user_id: str,
    status: str,
    limit: int,
    cache_dir: Path | None,
    include_signal_preview: bool,
    dry_run: bool = False,
) -> Path | None:
    payload = build_watchlist_runtime_cache_payload(
        user_id=user_id,
        status=status,
        limit=limit,
        include_signal_preview=include_signal_preview,
    )
    if dry_run:
        return None
    return save_watchlist_runtime_cache(user_id, payload, cache_dir)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build read-only watchlist runtime cache for one or all users.")
    parser.add_argument("--user-id", default="", help="User id whose paper_watchlist entries will be cached.")
    parser.add_argument(
        "--all-users",
        action="store_true",
        help="Cache pending_runtime watchlist for every distinct user id.",
    )
    parser.add_argument("--status", default=WATCHLIST_STATUS_PENDING_RUNTIME, help="paper_watchlist status filter.")
    parser.add_argument("--limit", type=int, default=100, help="Maximum watchlist rows per user.")
    parser.add_argument("--limit-users", type=int, default=200, help="Maximum users when --all-users is set.")
    parser.add_argument("--cache-dir", type=Path, default=None, help="Optional output cache directory.")
    parser.add_argument("--no-signal-preview", action="store_true", help="Skip chart-bundle signal preview.")
    parser.add_argument("--dry-run", action="store_true", help="Build payloads but do not write cache files.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    user_id = args.user_id.strip()
    if not user_id and not args.all_users:
        print("ERROR: provide --user-id or --all-users", file=sys.stderr)
        return 2
    if user_id and args.all_users:
        print("ERROR: --user-id and --all-users are mutually exclusive", file=sys.stderr)
        return 2

    include_signal_preview = not args.no_signal_preview
    user_ids = [user_id] if user_id else list_distinct_watchlist_user_ids(status=args.status, limit_users=args.limit_users)
    if not user_ids:
        print(
            "WATCHLIST_RUNTIME_JOB_OK",
            "users=0",
            f"status={args.status}",
            "count=0",
            f"dry_run={args.dry_run}",
        )
        return 0

    total_items = 0
    written = 0
    for uid in user_ids:
        payload = build_watchlist_runtime_cache_payload(
            user_id=uid,
            status=args.status,
            limit=args.limit,
            include_signal_preview=include_signal_preview,
        )
        item_count = int(payload.get("count") or 0)
        total_items += item_count
        if args.dry_run:
            print(
                "WATCHLIST_RUNTIME_USER_DRY",
                f"user_id={uid}",
                f"count={item_count}",
            )
            continue
        path = save_watchlist_runtime_cache(uid, payload, args.cache_dir)
        written += 1
        print(
            "WATCHLIST_RUNTIME_USER_OK",
            f"user_id={uid}",
            f"count={item_count}",
            f"path={path}",
        )

    print(
        "WATCHLIST_RUNTIME_JOB_OK",
        f"users={len(user_ids)}",
        f"written={written}",
        f"status={args.status}",
        f"items={total_items}",
        f"include_signal_preview={include_signal_preview}",
        f"dry_run={args.dry_run}",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
