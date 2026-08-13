#!/usr/bin/env python3
"""Zip ARCHIVE_SAFE results dirs and remove originals after verify."""
from __future__ import annotations

import json
import shutil
import zipfile
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INVENTORY = ROOT / "results" / "RESULTS_ARCHIVE_INVENTORY_20260618.json"
ARCHIVE_DIR = ROOT / "results" / "_archive"
STAMP = "20260618_batch1"


def main() -> int:
    rows = json.loads(INVENTORY.read_text(encoding="utf-8"))["rows"]
    names = sorted(r["name"] for r in rows if r["category"] == "ARCHIVE_SAFE")
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    zip_path = ARCHIVE_DIR / f"results_archive_safe_{STAMP}.zip"
    manifest_path = ARCHIVE_DIR / f"results_archive_safe_{STAMP}_manifest.json"

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
        "dirs": names,
        "dir_count": len(names),
        "file_count": file_count,
        "source_bytes": total_bytes,
        "zip_bytes": zip_path.stat().st_size,
        "zip_entries": zip_entries,
        "approved_by": "user 2026-06-18 ARCHIVE_SAFE batch1",
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    removed = []
    for name in names:
        shutil.rmtree(ROOT / "results" / name)
        removed.append(name)

    print(
        f"ok zip={zip_path.name} dirs={len(removed)} files={file_count} "
        f"src_mb={total_bytes/1024/1024:.1f} zip_mb={zip_path.stat().st_size/1024/1024:.1f}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
