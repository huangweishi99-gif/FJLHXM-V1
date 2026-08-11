from __future__ import annotations

from pathlib import Path


def test_current_domestic_paper_coordination_contract_passes() -> None:
    from scripts.audit_domestic_paper_coordination import run_checks

    checks = run_checks()

    assert checks
    assert all(check.ok for check in checks), [check.as_dict() for check in checks if not check.ok]


def test_manifest_source_accepts_staged_domestic_paper(tmp_path: Path) -> None:
    from scripts.audit_domestic_paper_coordination import check_paper_manifest_source

    (tmp_path / "scripts").mkdir()
    (tmp_path / "remote_domestic_optimize").mkdir()
    (tmp_path / "scripts" / "domestic_paper_manifest.txt").write_text("paper.py\n", encoding="utf-8")
    (tmp_path / "remote_domestic_optimize" / "paper.py").write_text("print('paper')\n", encoding="utf-8")

    result = check_paper_manifest_source(tmp_path)

    assert result.ok
    assert "paper.py" in result.detail


def test_check_contains_reports_missing_tokens() -> None:
    from scripts.audit_domestic_paper_coordination import check_contains

    result = check_contains("sample", "alpha beta", ["alpha", "gamma"])

    assert not result.ok
    assert "gamma" in result.detail
