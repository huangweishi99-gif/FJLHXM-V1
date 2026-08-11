from __future__ import annotations


def test_pending_order_contract_audit_passes() -> None:
    from scripts.audit_pending_order_contract import run_checks

    checks = run_checks()

    assert checks
    assert all(check.ok for check in checks), [check.as_dict() for check in checks if not check.ok]


def test_conflict_cancel_contract_keeps_ds01_same_direction_add() -> None:
    from scripts.audit_pending_order_contract import check_conflict_cancel_ds01_add_kept

    result = check_conflict_cancel_ds01_add_kept()

    assert result.ok


def test_conflict_cancel_contract_cancels_non_ds01_same_symbol_orders() -> None:
    from scripts.audit_pending_order_contract import check_conflict_cancel_non_ds01

    result = check_conflict_cancel_non_ds01()

    assert result.ok
