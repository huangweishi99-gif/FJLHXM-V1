#!/usr/bin/env python3
"""Audit A-share sector backtest archive coverage.

The historical sector reruns produced aggregate CSVs and logs, while the older
zip contains only a small summary snapshot. This audit is read-only: it reports
what is still available locally and whether per-stock detail directories still
exist, without creating or deleting archives.
"""
from __future__ import annotations

import argparse
import csv
import json
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
RESULTS_DIR = ROOT / "results"
OVERVIEW = RESULTS_DIR / "a_stock_all_sectors_overview.csv"
MASTER = RESULTS_DIR / "a_stock_all_sectors_master_summary.csv"
RUN_LOG = RESULTS_DIR / "fengji_total_a_stock_sectors_os20260529_run.log"
LEGACY_ZIP = RESULTS_DIR / "a_stock_sector_archive_ds07_fixed.zip"

EXPECTED_OVERVIEW_COLUMNS = {
    "board_name",
    "board_code",
    "sector_dir",
    "stocks_total",
    "stocks_ok",
    "stocks_error",
    "bad_audits_sum",
}
EXPECTED_MASTER_COLUMNS = {
    "symbol",
    "name",
    "sector_dir",
    "source_file",
    "out_dir",
    "status",
    "bad_audits",
    "strategies_run",
}
LEGACY_ZIP_EXPECTED_SUMMARIES = {
    "cpo_BK1128_sector_summary.csv",
    "suanli_BK1134_sector_summary.csv",
    "semiconductor_BK1036_sector_summary.csv",
    "virtual_robot_BK1190_sector_summary.csv",
}
# Minimum expected sectors for the aggregate overview/master summaries. The exact
# stock row baseline is derived dynamically from on-disk sector_summary.csv files
# (see derive_on_disk_baseline), because the historical 274-row snapshot included
# archived sector dirs that are no longer present.
MIN_SECTORS = 11


@dataclass(frozen=True)
class CheckResult:
    name: str
    ok: bool
    detail: str

    def as_dict(self) -> dict[str, Any]:
        return {"name": self.name, "ok": self.ok, "detail": self.detail}


def read_csv_rows(path: Path) -> tuple[list[dict[str, str]], set[str]]:
    if not path.is_file():
        return [], set()
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = [dict(row) for row in reader]
        return rows, set(reader.fieldnames or [])


def derive_on_disk_baseline(root: Path) -> tuple[int, int]:
    """Return (sector_count, stock_rows) expected from on-disk sector_summary.csv files.

    The aggregate overview/master summaries must cover at least the currently
    existing sector result dirs, instead of a hard-coded historical snapshot that
    referenced archived sector dirs no longer present on disk.
    """
    results_dir = root / "results"
    sector_dirs: set[str] = set()
    stock_rows = 0
    for summary in results_dir.glob("fengji_total_a_stock_sectors_*_ds07_fixed/*/sector_summary.csv"):
        sector_dirs.add(summary.parent.name)
        rows, _ = read_csv_rows(summary)
        stock_rows += len(rows)
    return len(sector_dirs), stock_rows


def check_columns(name: str, columns: set[str], expected: set[str]) -> CheckResult:
    missing = sorted(expected - columns)
    return CheckResult(name, not missing, "missing=" + ",".join(missing) if missing else "ok")


def check_overview(root: Path) -> CheckResult:
    rows, columns = read_csv_rows(root / "results" / OVERVIEW.name)
    column_check = check_columns("a_stock_sector_overview_columns", columns, EXPECTED_OVERVIEW_COLUMNS)
    if not column_check.ok:
        return column_check
    sector_count = len({row.get("sector_dir", "") for row in rows if row.get("sector_dir")})
    stocks_total = sum(int(float(row.get("stocks_total") or 0)) for row in rows)
    stocks_error = sum(int(float(row.get("stocks_error") or 0)) for row in rows)
    expected_sectors, expected_stocks = derive_on_disk_baseline(root)
    baseline = max(expected_stocks, MIN_SECTORS)
    ok = sector_count >= max(expected_sectors, MIN_SECTORS) and stocks_total >= baseline and stocks_error == 0
    return CheckResult(
        "a_stock_sector_overview_coverage",
        ok,
        f"sectors={sector_count} stocks_total={stocks_total} stocks_error={stocks_error} "
        f"baseline_sectors={expected_sectors} baseline_stocks={expected_stocks}",
    )


def check_master(root: Path) -> CheckResult:
    rows, columns = read_csv_rows(root / "results" / MASTER.name)
    column_check = check_columns("a_stock_sector_master_columns", columns, EXPECTED_MASTER_COLUMNS)
    if not column_check.ok:
        return column_check
    sectors = len({row.get("sector_dir", "") for row in rows if row.get("sector_dir")})
    statuses = sorted({row.get("status", "") for row in rows})
    bad_audits = sum(int(float(row.get("bad_audits") or 0)) for row in rows)
    expected_sectors, expected_stocks = derive_on_disk_baseline(root)
    ok = len(rows) >= max(expected_stocks, MIN_SECTORS) and sectors >= max(expected_sectors, MIN_SECTORS) and bad_audits == 0
    return CheckResult(
        "a_stock_sector_master_summary_coverage",
        ok,
        f"rows={len(rows)} sectors={sectors} statuses={statuses} bad_audits={bad_audits} "
        f"baseline_sectors={expected_sectors} baseline_stocks={expected_stocks}",
    )


def check_legacy_zip(root: Path) -> CheckResult:
    zip_path = root / "results" / LEGACY_ZIP.name
    if not zip_path.is_file():
        return CheckResult("legacy_a_stock_sector_zip", False, "missing zip")
    with zipfile.ZipFile(zip_path) as zf:
        names = set(zf.namelist())
        bad_member = zf.testzip()
    missing = sorted(LEGACY_ZIP_EXPECTED_SUMMARIES - names)
    ok = bad_member is None and not missing
    detail = f"entries={len(names)} missing={missing} bad_member={bad_member}"
    return CheckResult("legacy_a_stock_sector_zip", ok, detail)


def check_run_log(root: Path) -> CheckResult:
    log_path = root / "results" / RUN_LOG.name
    if not log_path.is_file():
        return CheckResult("a_stock_sector_run_log", False, "missing run log")
    raw = log_path.read_bytes()
    for encoding in ("utf-8-sig", "utf-16", "gbk"):
        try:
            text = raw.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    else:
        text = raw.decode("utf-8", errors="replace")
    tokens = ["板块:", "candidates_all=", "bad=0"]
    missing = [token for token in tokens if token not in text]
    return CheckResult(
        "a_stock_sector_run_log",
        not missing,
        "missing=" + ",".join(missing) if missing else f"bytes={log_path.stat().st_size}",
    )


def archive_snapshot(root: Path) -> dict[str, Any]:
    rows, _ = read_csv_rows(root / "results" / MASTER.name)
    source_paths = [root / row["source_file"] for row in rows if row.get("source_file")]
    out_dirs = [root / row["out_dir"] for row in rows if row.get("out_dir")]
    existing_source_files = sum(1 for path in source_paths if path.is_file())
    existing_out_dirs = sum(1 for path in out_dirs if path.is_dir())
    overview_rows, _ = read_csv_rows(root / "results" / OVERVIEW.name)
    zip_path = root / "results" / LEGACY_ZIP.name
    zip_entries: list[str] = []
    if zip_path.is_file():
        with zipfile.ZipFile(zip_path) as zf:
            zip_entries = zf.namelist()
    return {
        "overview_sectors": len(overview_rows),
        "master_rows": len(rows),
        "master_sectors": len({row.get("sector_dir", "") for row in rows if row.get("sector_dir")}),
        "source_file_refs": len(source_paths),
        "source_file_existing": existing_source_files,
        "out_dir_refs": len(out_dirs),
        "out_dir_existing": existing_out_dirs,
        "legacy_zip_exists": zip_path.is_file(),
        "legacy_zip_entries": len(zip_entries),
        "legacy_zip_summary_entries": sorted(name for name in zip_entries if name.endswith("_sector_summary.csv")),
        "full_detail_archive_complete": bool(rows) and existing_source_files == len(source_paths) and existing_out_dirs == len(out_dirs),
    }


def run_checks(root: Path = ROOT) -> list[CheckResult]:
    return [
        check_overview(root),
        check_master(root),
        check_legacy_zip(root),
        check_run_log(root),
    ]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit A-share sector archive coverage.")
    parser.add_argument("--root", default=str(ROOT))
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = Path(args.root).resolve()
    checks = run_checks(root)
    failures = [check for check in checks if not check.ok]
    payload = {
        "checks": [check.as_dict() for check in checks],
        "failures": len(failures),
        "archive": archive_snapshot(root),
        "policy": {
            "current_archive_status": (
                "aggregate CSVs and run log are present; legacy zip is only a four-sector summary archive"
            ),
            "full_detail_status": (
                "per-stock source_file and out_dir references in master_summary are present locally "
                "when full_detail_archive_complete is true"
            ),
        },
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
