from __future__ import annotations


def test_unified_ledger_regression_audit_passes() -> None:
    from scripts.audit_unified_ledger_regression import run_checks

    checks = run_checks()

    assert checks
    assert all(check.ok for check in checks), [check.as_dict() for check in checks if not check.ok]


def test_merge_candidates_contract_check_passes() -> None:
    from scripts.audit_unified_ledger_regression import check_merge_candidates_contract

    result = check_merge_candidates_contract()

    assert result.ok
    assert "accepted=3" in result.detail


def test_futures_scoring_contract_check_passes() -> None:
    from scripts.audit_unified_ledger_regression import check_futures_scoring_contract

    result = check_futures_scoring_contract()

    assert result.ok


def test_crypto_scoring_contract_check_passes() -> None:
    from scripts.audit_unified_ledger_regression import check_crypto_scoring_contract

    result = check_crypto_scoring_contract()

    assert result.ok
