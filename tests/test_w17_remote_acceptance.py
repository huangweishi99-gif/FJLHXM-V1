"""W17-prod remote acceptance checklist."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
ACCEPTANCE = ROOT / "scripts" / "w17_remote_acceptance.py"
RUNNER = ROOT / "scripts" / "run_w17_remote_acceptance.ps1"


def test_w17_acceptance_script_exists() -> None:
    text = ACCEPTANCE.read_text(encoding="utf-8")
    assert "run_acceptance" in text
    assert "preflight_checks" in text
    assert "admin_unauth" in text
    assert "feature_gate_total" in text


def test_w17_remote_runner_ps1_exists() -> None:
    assert RUNNER.is_file()
    text = RUNNER.read_text(encoding="utf-8")
    assert "w17_remote_acceptance.py" in text
    assert "PreflightOnly" in text


def test_w17_preflight_only_ok() -> None:
    proc = subprocess.run(
        [sys.executable, str(ACCEPTANCE), "--preflight-only", "--preflight-ssh", "domestic-quant-nonexistent"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    payload = json.loads(proc.stdout)
    assert payload.get("mode") == "preflight"
    assert any(c["id"] == "manifest" and c["ok"] for c in payload.get("checks", []))


@pytest.mark.skipif(
    not (ROOT / "runtime" / "secrets" / "fengji_local.env").is_file(),
    reason="needs local env; run start_fengji_local.ps1 once",
)
def test_w17_acceptance_auto_server() -> None:
    proc = subprocess.run(
        [sys.executable, str(ACCEPTANCE), "--auto-server", "--port", "8043"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    if proc.returncode != 0 and "auth storage unavailable" in proc.stdout:
        pytest.skip("local PG auth storage is unavailable for W17 auto-server acceptance")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    payload = json.loads(proc.stdout)
    assert payload.get("ok") is True
    assert payload["summary"]["required_passed"] == payload["summary"]["required_total"]
