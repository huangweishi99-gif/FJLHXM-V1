"""W08 / Wave5 P4: 9-screen pencil acceptance wrapper."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "w08_pencil_acceptance.py"


def test_w08_acceptance_script_exists() -> None:
    text = SCRIPT.read_text(encoding="utf-8")
    assert "PEN_EXPECTED" in text
    assert "PEN_FRAME_MARKERS" in text
    assert "pen_web_text" in text
    assert "pencil_canvas_mcp" in text
    assert "web_screenshot_proxy" in text
    assert "WEB_SCREENSHOTS" in text


def test_w08_pen_expected_matches_finalize() -> None:
    finalize = (ROOT / "scripts" / "finalize_fjlhxm_ui_pen.py").read_text(encoding="utf-8")
    assert "01 · Dashboard" in finalize
    assert "09 · Payment" in finalize


def test_w08_acceptance_preflight() -> None:
    import subprocess
    import sys

    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--preflight-only", "--skip-pen-regenerate"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    if proc.returncode != 0:
        payload = json.loads(proc.stdout)
        if any(check.get("id") == "pen_frames" and "missing frames" in check.get("error", "") for check in payload.get("checks", [])):
            pytest.skip("Pencil frame assets are not available in this local checkout")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert '"ok": true' in proc.stdout or '"ok":true' in proc.stdout.replace(" ", "")
