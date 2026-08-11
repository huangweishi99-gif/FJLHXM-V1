from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
import time


ROOT = Path(__file__).resolve().parents[1]


def test_overseas_runtime_check_keeps_remote_env_expansion() -> None:
    text = (ROOT / "scripts" / "check_overseas_runtime_status.ps1").read_text(encoding="utf-8")

    assert 'echo "FENGJI_MARKET=${FENGJI_MARKET:-crypto}"' in text
    assert "PYTHON_BIN=.venv/bin/python" in text
    assert "find data -maxdepth 2 -type f -name '*.csv'" in text
    assert '\"$PYTHON_BIN\" scripts/summarize_pending_effective_status.py' in text


def test_overseas_runtime_check_includes_notification_audit() -> None:
    text = (ROOT / "scripts" / "check_overseas_runtime_status.ps1").read_text(encoding="utf-8")

    assert "===== OVERSEAS NOTIFICATION AUDIT =====" in text
    assert "audit_overseas_notification_coverage.py" in text
    assert 'PYTHONPATH=src:packages/fengji_core:. "$PYTHON_BIN" scripts/audit_overseas_notification_coverage.py' in text
    assert "overseas notification audit unavailable" in text


def test_domestic_extra_process_check_uses_text_output() -> None:
    text = (ROOT / "scripts" / "check_domestic_runtime_remote.ps1").read_text(encoding="utf-8")
    remote_extra = text.split("$remoteExtra = @'", 1)[1].split("'@", 1)[0]

    assert "Write-Host" not in remote_extra
    assert "Write-Output" in remote_extra
    assert "-OutputFormat Text -EncodedCommand" in text


def test_domestic_runtime_check_includes_effective_pending_summary() -> None:
    text = (ROOT / "scripts" / "check_domestic_runtime_remote.ps1").read_text(encoding="utf-8")
    remote_effective = text.split("$remoteEffective = @'", 1)[1].split("'@", 1)[0]

    assert "summarize_pending_effective_status.py" in remote_effective
    assert '$py = if (Test-Path ".venv/Scripts/python.exe")' in remote_effective
    assert "& $py scripts/summarize_pending_effective_status.py --include-shadow" in remote_effective
    assert "Write-Host" not in remote_effective
    assert "Write-Output" in remote_effective


def test_domestic_runtime_check_includes_notification_audit() -> None:
    text = (ROOT / "scripts" / "check_domestic_runtime_remote.ps1").read_text(encoding="utf-8")
    remote_notify = text.split("$remoteNotifyAudit = @'", 1)[1].split("'@", 1)[0]

    assert "DOMESTIC NOTIFICATION AUDIT" in text
    assert "audit_domestic_notification_coverage.py" in remote_notify
    assert '$env:PYTHONPATH = "src;packages/fengji_core;."' in remote_notify
    assert '$py = if (Test-Path ".venv/Scripts/python.exe")' in remote_notify
    assert "& $py scripts/audit_domestic_notification_coverage.py" in remote_notify
    assert "Write-Host" not in remote_notify
    assert "Write-Output" in remote_notify
    assert "-OutputFormat Text -EncodedCommand" in text


def test_domestic_status_heartbeat_threshold_matches_poll_contract() -> None:
    status_text = (ROOT / "scripts" / "check_domestic_status.ps1").read_text(encoding="utf-8")
    watchdog_verify_text = (ROOT / "scripts" / "verify_domestic_watchdog.ps1").read_text(encoding="utf-8")

    assert "$HeartbeatMaxAgeSec = 420" in status_text
    assert "expect <$HeartbeatMaxAgeSec" in status_text
    assert "-gt $HeartbeatMaxAgeSec" in status_text
    assert "expect <120" not in status_text
    assert "-gt 120" not in status_text
    assert "$HeartbeatMaxAgeSec = 420" in watchdog_verify_text
    assert "-gt $HeartbeatMaxAgeSec" in watchdog_verify_text


def test_dual_server_runtime_check_wraps_both_existing_checks() -> None:
    text = (ROOT / "scripts" / "check_dual_server_runtime_status.ps1").read_text(encoding="utf-8")

    assert "check_domestic_runtime_remote.ps1" in text
    assert "check_overseas_runtime_status.ps1" in text
    assert "runtime\\logs\\dual_runtime_check" in text
    assert "domestic_runtime.log" in text
    assert "overseas_runtime.log" in text
    assert "SUMMARY.md" in text
    assert "$output | Write-Output" not in text
    assert "$output | ForEach-Object { Write-Host $_ }" in text
    assert "ERROR: No runtime checks selected." in text
    assert "exit 2" in text
    assert "exit 1" in text
    assert "exit 0" in text


def test_dual_server_runtime_check_does_not_log_commands_or_secrets() -> None:
    text = (ROOT / "scripts" / "check_dual_server_runtime_status.ps1").read_text(encoding="utf-8")

    assert "Start-Transcript" not in text
    assert "Set-PSDebug" not in text
    assert "Write-Host $commandArgs" not in text
    forbidden = ("webhook", "token", "password", "secret", "api_key")
    assert all(word not in text.lower() for word in forbidden)


def test_dual_server_runtime_check_rejects_empty_selection_before_log_creation(tmp_path: Path) -> None:
    powershell = shutil.which("powershell")
    assert powershell is not None
    output_dir = tmp_path / "must_not_exist"

    result = subprocess.run(
        [
            powershell,
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(ROOT / "scripts" / "check_dual_server_runtime_status.ps1"),
            "-SkipDomestic",
            "-SkipOverseas",
            "-OutputDir",
            str(output_dir),
        ],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )

    assert result.returncode == 2
    assert "No runtime checks selected" in result.stdout
    assert not output_dir.exists()


def _run_latest_status_script(log_root: Path, max_age_minutes: int = 120) -> subprocess.CompletedProcess[str]:
    powershell = shutil.which("powershell")
    assert powershell is not None
    return subprocess.run(
        [
            powershell,
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(ROOT / "scripts" / "show_latest_dual_runtime_status.ps1"),
            "-LogRoot",
            str(log_root),
            "-MaxAgeMinutes",
            str(max_age_minutes),
        ],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def _write_dual_summary(log_root: Path, status: str) -> Path:
    result_dir = log_root / "20260714_120000"
    result_dir.mkdir(parents=True)
    summary = result_dir / "SUMMARY.md"
    summary.write_text(
        "\n".join(
            [
                "# Dual Server Runtime Check - 20260714_120000",
                "",
                f"- status: {status}",
                "- output_dir: test",
                "",
                "- domestic: exit_code=0, log=domestic_runtime.log",
                "- overseas: exit_code=0, log=overseas_runtime.log",
            ]
        ),
        encoding="utf-8",
    )
    return summary


def test_latest_dual_runtime_status_reports_fresh_pass(tmp_path: Path) -> None:
    _write_dual_summary(tmp_path, "PASS")

    result = _run_latest_status_script(tmp_path)

    assert result.returncode == 0
    assert "status=PASS" in result.stdout
    assert "freshness=FRESH" in result.stdout
    assert "domestic_exit_code=0" in result.stdout
    assert "overseas_exit_code=0" in result.stdout


def test_latest_dual_runtime_status_preserves_fail_exit(tmp_path: Path) -> None:
    _write_dual_summary(tmp_path, "FAIL")

    result = _run_latest_status_script(tmp_path)

    assert result.returncode == 1
    assert "status=FAIL" in result.stdout
    assert "freshness=FRESH" in result.stdout


def test_latest_dual_runtime_status_rejects_stale_summary(tmp_path: Path) -> None:
    summary = _write_dual_summary(tmp_path, "PASS")
    stale_time = time.time() - (180 * 60)
    os.utime(summary, (stale_time, stale_time))

    result = _run_latest_status_script(tmp_path, max_age_minutes=120)

    assert result.returncode == 3
    assert "status=PASS" in result.stdout
    assert "freshness=STALE" in result.stdout


def test_latest_dual_runtime_status_rejects_missing_summary(tmp_path: Path) -> None:
    result = _run_latest_status_script(tmp_path)

    assert result.returncode == 2
    assert "No dual-server runtime summary found" in result.stdout


def test_latest_dual_runtime_status_rejects_malformed_summary(tmp_path: Path) -> None:
    _write_dual_summary(tmp_path, "UNKNOWN")

    result = _run_latest_status_script(tmp_path)

    assert result.returncode == 2
    assert "no valid PASS/FAIL status" in result.stdout


def _run_log_retention_script(
    log_root: Path,
    retention_days: int = 14,
    execute: bool = False,
) -> subprocess.CompletedProcess[str]:
    powershell = shutil.which("powershell")
    assert powershell is not None
    args = [
        powershell,
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(ROOT / "scripts" / "manage_dual_runtime_check_logs.ps1"),
        "-LogRoot",
        str(log_root),
        "-RetentionDays",
        str(retention_days),
    ]
    if execute:
        args.append("-Execute")
    return subprocess.run(
        args,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def _make_old_runtime_log_directory(log_root: Path, name: str, unknown_file: bool = False) -> Path:
    result_dir = log_root / name
    result_dir.mkdir(parents=True)
    file_name = "operator_notes.txt" if unknown_file else "SUMMARY.md"
    (result_dir / file_name).write_text("test\n", encoding="utf-8")
    stale_time = time.time() - (20 * 24 * 60 * 60)
    os.utime(result_dir / file_name, (stale_time, stale_time))
    os.utime(result_dir, (stale_time, stale_time))
    return result_dir


def test_dual_runtime_log_retention_dry_run_does_not_delete(tmp_path: Path) -> None:
    managed = _make_old_runtime_log_directory(tmp_path, "20260601_120000")
    unmanaged = _make_old_runtime_log_directory(tmp_path, "20260601_130000", unknown_file=True)

    result = _run_log_retention_script(tmp_path)

    assert result.returncode == 0
    assert "mode=DRY_RUN" in result.stdout
    assert "candidate_count=1" in result.stdout
    assert "skipped_unmanaged_count=1" in result.stdout
    assert "deleted_count=0" in result.stdout
    assert managed.exists()
    assert unmanaged.exists()


def test_dual_runtime_log_retention_execute_deletes_only_managed_candidate(tmp_path: Path) -> None:
    managed = _make_old_runtime_log_directory(tmp_path, "20260601_120000")
    unmanaged = _make_old_runtime_log_directory(tmp_path, "20260601_130000", unknown_file=True)

    result = _run_log_retention_script(tmp_path, execute=True)

    assert result.returncode == 0
    assert "mode=EXECUTE" in result.stdout
    assert "candidate_count=1" in result.stdout
    assert "deleted_count=1" in result.stdout
    assert not managed.exists()
    assert unmanaged.exists()


def test_domestic_watchdog_deduplicates_unchanged_fill_invalid_set() -> None:
    text = (ROOT / "scripts" / "watchdog_domestic.ps1").read_text(encoding="utf-8")

    assert "invalid_new_fills" in text
    assert "fill_supervision_invalid.fingerprint" in text
    assert "invalid set unchanged; Feishu repeat suppressed" in text
    assert "Send-FillSupervisionAlertOnChange" in text
