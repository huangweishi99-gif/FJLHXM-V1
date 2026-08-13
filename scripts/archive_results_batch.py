#!/usr/bin/env python3
"""Zip results/ subdirs by inventory category and remove originals after verify."""
from __future__ import annotations

import argparse
import json
import shutil
import zipfile
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INVENTORY = ROOT / "results" / "RESULTS_ARCHIVE_INVENTORY_20260618.json"
ARCHIVE_DIR = ROOT / "results" / "_archive"


def archive_batch(
    *,
    inventory: Path,
    categories: list[str],
    stamp: str,
    approved_by: str,
    exclude: set[str] | None = None,
) -> int:
    rows = json.loads(inventory.read_text(encoding="utf-8"))["rows"]
    skip = {x.strip() for x in (exclude or set()) if x.strip()}
    names = sorted(
        r["name"]
        for r in rows
        if r["category"] in categories and r["name"] not in skip
    )
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    zip_path = ARCHIVE_DIR / f"results_archive_{stamp}.zip"
    manifest_path = ARCHIVE_DIR / f"results_archive_{stamp}_manifest.json"

    if zip_path.exists():
        print(f"already exists: {zip_path}")
        return 1

    missing = [n for n in names if not (ROOT / "results" / n).is_dir()]
    if missing:
        print("missing dirs:", missing)
        return 1

    total_bytes = 0
    file_count = 0
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for name in names:
            base = ROOT / "results" / name
            for path in base.rglob("*"):
                if path.is_file():
                    arc = Path("results") / name / path.relative_to(base)
                    zf.write(path, arc.as_posix())
                    total_bytes += path.stat().st_size
                    file_count += 1

    with zipfile.ZipFile(zip_path, "r") as zf:
        if zf.testzip() is not None:
            zip_path.unlink(missing_ok=True)
            print("zip verify failed")
            return 1
        zip_entries = len(zf.namelist())

    manifest = {
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "zip": str(zip_path.relative_to(ROOT)),
        "categories": categories,
        "dirs": names,
        "dir_count": len(names),
        "file_count": file_count,
        "source_bytes": total_bytes,
        "zip_bytes": zip_path.stat().st_size,
        "zip_entries": zip_entries,
        "approved_by": approved_by,
        "excluded": sorted(skip),
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    for name in names:
        shutil.rmtree(ROOT / "results" / name)

    print(
        f"ok zip={zip_path.name} dirs={len(names)} files={file_count} "
        f"src_mb={total_bytes/1024/1024:.1f} zip_mb={zip_path.stat().st_size/1024/1024:.1f}"
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--inventory", default=str(DEFAULT_INVENTORY))
    parser.add_argument("--categories", nargs="+", required=True)
    parser.add_argument("--stamp", required=True)
    parser.add_argument("--exclude", nargs="*", default=[], help="Directory names to skip")
    parser.add_argument("--approved-by", default="user approved")
    args = parser.parse_args()
    return archive_batch(
        inventory=Path(args.inventory),
        categories=args.categories,
        stamp=args.stamp,
        approved_by=args.approved_by,
        exclude=set(args.exclude),
    )


if __name__ == "__main__":
    raise SystemExit(main())
