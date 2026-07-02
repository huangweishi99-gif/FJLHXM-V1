"""Static web asset checks (no PG / browser required)."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"

REQUIRED_PAGES = (
    "index.html",
    "login.html",
    "pricing.html",
    "payment.html",
    "community.html",
    "backtest.html",
    "monitor.html",
    "strategies.html",
)


def test_web_required_pages_exist() -> None:
    missing = [name for name in REQUIRED_PAGES if not (WEB / name).is_file()]
    assert not missing, f"missing web pages: {missing}"


def test_login_has_no_pricing_plan_picker() -> None:
    text = (WEB / "login.html").read_text(encoding="utf-8")
    assert "authPassword" in text
    assert 'data-mode="register"' in text
    assert "intent === \"free\"" in text or "intent === 'free'" in text
    assert "订阅档位" not in text


def test_community_separate_from_payment() -> None:
    community = (WEB / "community.html").read_text(encoding="utf-8")
    payment = (WEB / "payment.html").read_text(encoding="utf-8")
    config = (WEB / "js" / "config.js").read_text(encoding="utf-8")
    assert "QQ" in community or "qq-group" in community
    assert "confirmPaidSubscription" in payment
    assert "payment.html" in config and "pay=" in config


def test_app_js_exports_auth_helpers() -> None:
    text = (WEB / "js" / "app.js").read_text(encoding="utf-8")
    for needle in ("authLogin", "authRegister", "getAccessToken", "fj-plan"):
        assert needle in text
