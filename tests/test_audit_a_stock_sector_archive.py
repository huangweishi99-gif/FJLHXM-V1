from __future__ import annotations

import csv
import zipfile
from pathlib import Path


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def test_a_stock_sector_archive_audit_passes() -> None:
    from scripts.audit_a_stock_sector_archive import run_checks

    checks = run_checks()

    assert checks
    assert all(check.ok for check in checks), [check.as_dict() for check in checks if not check.ok]


def test_archive_snapshot_records_missing_detail_dirs() -> None:
    from scripts.audit_a_stock_sector_archive import ROOT, archive_snapshot

    snapshot = archive_snapshot(ROOT)

    assert snapshot["overview_sectors"] >= 11
    assert snapshot["master_rows"] >= 274
    assert snapshot["legacy_zip_exists"] is True
    assert snapshot["full_detail_archive_complete"] is False


def test_legacy_zip_check_detects_missing_summary(tmp_path) -> None:
    from scripts.audit_a_stock_sector_archive import check_legacy_zip

    results = tmp_path / "results"
    results.mkdir()
    with zipfile.ZipFile(results / "a_stock_sector_archive_ds07_fixed.zip", "w") as zf:
        zf.writestr("README.md", "partial")

    result = check_legacy_zip(tmp_path)

    assert not result.ok
    assert "missing=" in result.detail


def test_overview_check_accepts_minimum_fixture(tmp_path) -> None:
    from scripts.audit_a_stock_sector_archive import check_overview

    fields = [
        "board_name",
        "board_code",
        "sector_dir",
        "stocks_total",
        "stocks_ok",
        "stocks_error",
        "bad_audits_sum",
    ]
    rows = [
        {
            "board_name": f"sector{i}",
            "board_code": f"BK{i:04d}",
            "sector_dir": f"sector{i}_BK{i:04d}",
            "stocks_total": 25,
            "stocks_ok": 25,
            "stocks_error": 0,
            "bad_audits_sum": 0,
        }
        for i in range(11)
    ]
    write_csv(tmp_path / "results" / "a_stock_all_sectors_overview.csv", fields, rows)

    result = check_overview(tmp_path)

    assert result.ok
