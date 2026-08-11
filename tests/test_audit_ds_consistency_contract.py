from __future__ import annotations

from pathlib import Path


def test_current_ds_consistency_contract_passes() -> None:
    from scripts.audit_ds_consistency_contract import run_checks

    checks = run_checks()

    assert checks
    assert all(check.ok for check in checks), [check.as_dict() for check in checks if not check.ok]


def test_check_contract_reports_missing_tokens(tmp_path: Path) -> None:
    from scripts.audit_ds_consistency_contract import Contract, check_contract

    rel = "packages/fengji_core/fengji_core/ds01.py"
    path = tmp_path / rel
    path.parent.mkdir(parents=True)
    path.write_text("def ds01_left_filter_pass():\n    return True\n", encoding="utf-8")
    contract = Contract(
        name="tmp_contract",
        path=rel,
        required_tokens=("def ds01_left_filter_pass(", "max_lines: int = 2"),
    )

    result = check_contract(tmp_path, contract)

    assert not result.ok
    assert "max_lines: int = 2" in result.detail


def test_check_contract_reports_missing_file(tmp_path: Path) -> None:
    from scripts.audit_ds_consistency_contract import Contract, check_contract

    contract = Contract(name="missing_contract", path="missing.py", required_tokens=("x",))

    result = check_contract(tmp_path, contract)

    assert not result.ok
    assert "missing_file=missing.py" == result.detail


def test_check_contract_reports_forbidden_token(tmp_path: Path) -> None:
    from scripts.audit_ds_consistency_contract import Contract, check_contract

    rel = "src/fengji_total_radar.py"
    path = tmp_path / rel
    path.parent.mkdir(parents=True)
    path.write_text("current_contract\nold_contract\n", encoding="utf-8")
    contract = Contract(
        name="forbidden_contract",
        path=rel,
        required_tokens=("current_contract",),
        forbidden_tokens=("old_contract",),
    )

    result = check_contract(tmp_path, contract)

    assert not result.ok
    assert "old_contract" in result.detail
