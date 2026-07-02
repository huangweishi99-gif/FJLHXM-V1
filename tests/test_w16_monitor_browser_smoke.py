"""W16-WS: optional browser smoke wrapper (skips without Playwright/PG)."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "smoke_w16_monitor_browser.py"


def test_w16_smoke_script_includes_reconnect_flow() -> None:
    text = SCRIPT.read_text(encoding="utf-8")
    assert "__fjTestWsRefs" in text
    assert "reconnect_disconnect_seen" in text
    assert "reconnect_ok" in text
    assert "--skip-reconnect" in text
    assert "ok_reconnect" in text


def test_monitor_html_ws_reconnect_meta() -> None:
    html = (ROOT / "web" / "monitor.html").read_text(encoding="utf-8")
    assert "WS断开，轮询备用，5秒后重连" in html
    assert "keepReconnectMeta" in html
    assert "startPolling(false)" in html


def test_w16_smoke_script_includes_v1_plus_api_checks() -> None:
    text = SCRIPT.read_text(encoding="utf-8")
    assert "monitor_v1_plus_api_smoke" in text
    assert "/api/v1/monitor/ledger/recent" in text
    assert "/api/v1/monitor/paper-account" in text
    assert "v1_plus_dom" in text


@pytest.mark.skipif(
    os.getenv("RUN_W16_BROWSER_SMOKE", "").lower() not in {"1", "true", "yes"},
    reason="set RUN_W16_BROWSER_SMOKE=1 to run live browser smoke (needs PG + playwright)",
)
def test_w16_monitor_browser_smoke_auto_server() -> None:
    env = os.environ.copy()
    env.setdefault("FENGJI_AUTH_ALLOW_DEV_SECRET", "1")
    env.setdefault("FENGJI_ALLOW_MANUAL_SUBSCRIPTION_CONFIRM", "1")
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--auto-server", "--port", "8033"],
        cwd=str(ROOT),
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert '"ok": true' in proc.stdout or '"ok": true' in proc.stdout.replace(" ", "")
