"""W17 P3: subscription Playwright smoke wrapper."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "smoke_w17_subscription_browser.py"


def test_w17_subscription_smoke_script_exists() -> None:
    text = SCRIPT.read_text(encoding="utf-8")
    assert "login_gate_redirect" in text
    assert "payment_confirm_landing" in text
    assert "--plan" in text
    assert "pricing.html" in text
    assert "payment.html" in text


def test_payment_pages_use_independent_pay_url() -> None:
    pricing = (ROOT / "web" / "pricing.html").read_text(encoding="utf-8")
    payment = (ROOT / "web" / "payment.html").read_text(encoding="utf-8")
    login = (ROOT / "web" / "login.html").read_text(encoding="utf-8")
    assert "payment.html?pay=standard" in pricing or "ctaHref" in pricing
    assert "confirmPaidSubscription" in payment
    assert "intent=free" not in login or "register" in login


@pytest.mark.skipif(
    os.getenv("RUN_W17_SUBSCRIPTION_BROWSER_SMOKE", "").lower() not in {"1", "true", "yes"},
    reason="set RUN_W17_SUBSCRIPTION_BROWSER_SMOKE=1 to run live browser smoke (needs PG + playwright)",
)
def test_w17_subscription_browser_smoke_auto_server() -> None:
    env = os.environ.copy()
    env.setdefault("FENGJI_AUTH_ALLOW_DEV_SECRET", "1")
    env.setdefault("FENGJI_ALLOW_MANUAL_SUBSCRIPTION_CONFIRM", "1")
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--auto-server", "--port", "8035", "--plan", "standard"],
        cwd=str(ROOT),
        env=env,
        capture_output=True,
        text=True,
        timeout=180,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert '"ok": true' in proc.stdout.replace(" ", "")
