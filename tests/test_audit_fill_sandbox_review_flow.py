from __future__ import annotations

from pathlib import Path


def test_current_fill_sandbox_review_flow_contract_passes() -> None:
    from scripts.audit_fill_sandbox_review_flow import run_checks

    checks = run_checks()

    assert checks
    assert all(check.ok for check in checks), [check.as_dict() for check in checks if not check.ok]


def test_check_contains_reports_missing_token() -> None:
    from scripts.audit_fill_sandbox_review_flow import check_contains

    result = check_contains("sample", "alpha beta", ["alpha", "gamma"])

    assert not result.ok
    assert "gamma" in result.detail


def test_runtime_snapshot_reports_empty_tmp_dir(tmp_path: Path) -> None:
    from scripts.audit_fill_sandbox_review_flow import runtime_snapshot

    snapshot = runtime_snapshot(tmp_path)

    assert snapshot["out_dir_exists"] is False
    assert snapshot["review_json_exists"] is False
    assert snapshot["png_count"] == 0
