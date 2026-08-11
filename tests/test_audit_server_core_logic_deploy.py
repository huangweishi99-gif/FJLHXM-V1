from __future__ import annotations

from pathlib import Path


def test_current_local_core_feature_tokens_pass() -> None:
    from scripts.audit_server_core_logic_deploy import run_checks

    checks = run_checks()

    assert checks
    assert all(check.ok for check in checks), [check.as_dict() for check in checks if not check.ok]


def test_compare_snapshots_detects_hash_mismatch() -> None:
    from scripts.audit_server_core_logic_deploy import CORE_FEATURES, compare_snapshots

    rel = next(iter(CORE_FEATURES))
    local = {name: {"exists": True, "hash": "aaa", "missing_tokens": []} for name in CORE_FEATURES}
    remote = {name: {"exists": True, "hash": "aaa", "missing_tokens": []} for name in CORE_FEATURES}
    remote[rel] = {"exists": True, "hash": "bbb", "missing_tokens": []}

    result = compare_snapshots(local, remote)

    assert result["mismatches"] == 1
    assert result["rows"][0]["match"] is False


def test_local_file_snapshot_reports_missing_tokens(tmp_path: Path) -> None:
    from scripts.audit_server_core_logic_deploy import CORE_FEATURES, local_file_snapshot

    rel = next(iter(CORE_FEATURES))
    path = tmp_path / rel
    path.parent.mkdir(parents=True)
    path.write_text("print('old logic')\n", encoding="utf-8")

    result = local_file_snapshot(tmp_path, rel)

    assert result["exists"] is True
    assert result["missing_tokens"]


def test_remote_command_contains_profile_root() -> None:
    from scripts.audit_server_core_logic_deploy import remote_command

    cmd = remote_command({"root": "C:/x/y", "python": "python"}, "payload", "program")

    assert "C:/x/y" in cmd
    assert "payload" in cmd
    assert "program" in cmd
