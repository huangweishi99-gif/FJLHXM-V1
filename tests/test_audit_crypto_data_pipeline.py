from __future__ import annotations

from pathlib import Path


def test_current_crypto_data_pipeline_contract_passes() -> None:
    from scripts.audit_crypto_data_pipeline import run_checks

    checks = run_checks()

    assert checks
    assert all(check.ok for check in checks), [check.as_dict() for check in checks if not check.ok]


def test_parse_last_timestamp_supports_date_and_datetime(tmp_path: Path) -> None:
    from scripts.audit_crypto_data_pipeline import parse_last_timestamp

    d1 = tmp_path / "d1.csv"
    d1.write_text("timestamp,open,high,low,close,volume\n2026-07-10,1,1,1,1,1\n", encoding="utf-8")
    m15 = tmp_path / "m15.csv"
    m15.write_text("date,open,high,low,close,volume\n2026-07-10 12:15:00,1,1,1,1,1\n", encoding="utf-8")

    assert parse_last_timestamp(d1).strftime("%Y-%m-%d %H:%M:%S") == "2026-07-10 00:00:00"
    assert parse_last_timestamp(m15).strftime("%Y-%m-%d %H:%M:%S") == "2026-07-10 12:15:00"


def test_snapshot_reports_missing_files(tmp_path: Path) -> None:
    from scripts.audit_crypto_data_pipeline import csv_freshness_snapshot

    snapshot = csv_freshness_snapshot(tmp_path)

    assert snapshot["available_total"] == 0
    assert snapshot["missing_sample"]
