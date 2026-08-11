from __future__ import annotations


def test_pending_refresh_policy_audit_passes() -> None:
    from scripts.audit_pending_refresh_policy import run_checks

    checks = run_checks()

    assert checks
    assert all(check.ok for check in checks), [check.as_dict() for check in checks if not check.ok]


def test_valid_until_anchor_contract_is_checked() -> None:
    from scripts.audit_pending_refresh_policy import ROOT, check_pending_order_valid_until_contract

    result = check_pending_order_valid_until_contract(ROOT)

    assert result.ok


def test_check_contains_reports_missing_tokens() -> None:
    from scripts.audit_pending_refresh_policy import check_contains

    result = check_contains("sample", "alpha beta", ["alpha", "gamma"])

    assert not result.ok
    assert "gamma" in result.detail


def test_runtime_snapshot_handles_empty_root(tmp_path) -> None:
    from scripts.audit_pending_refresh_policy import runtime_snapshot

    snapshot = runtime_snapshot(tmp_path)

    assert snapshot["orders_exists"] is False
    assert snapshot["order_count"] is None
    assert snapshot["crypto_state_exists"] is False
    assert snapshot["futures_state_exists"] is False
