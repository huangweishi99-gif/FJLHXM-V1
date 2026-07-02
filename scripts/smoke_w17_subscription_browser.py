#!/usr/bin/env python3
"""W17 P3 browser smoke: login/register → pricing → payment → landing page.

Requires optional dev deps:
  pip install playwright
  python -m playwright install chrome

Usage:
  docker compose up -d && alembic upgrade head
  python scripts/smoke_w17_subscription_browser.py --auto-server
  python scripts/smoke_w17_subscription_browser.py --base-url http://127.0.0.1:8000 --plan standard
  python scripts/smoke_w17_subscription_browser.py --auto-server --plan pro --skip-login-gate
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import uuid
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT))

from smoke_w17_auth_ws import start_uvicorn, wait_for_health  # noqa: E402


def _ensure_dev_env() -> None:
    os.environ.setdefault("FENGJI_AUTH_ALLOW_DEV_SECRET", "1")
    os.environ.setdefault("FENGJI_ALLOW_MANUAL_SUBSCRIPTION_CONFIRM", "1")


def _landing_for_plan(plan: str) -> str:
    return "monitor.html" if plan == "standard" else "backtest.html"


def _cta_selector(plan: str) -> str:
    return f'a.pricing-cta[href*="pay={plan}"]'


def browser_subscription_flow(
    base_url: str,
    *,
    plan: str = "standard",
    headless: bool = True,
    test_login_gate: bool = True,
) -> dict[str, Any]:
    try:
        from playwright.sync_api import Error as PlaywrightError
        from playwright.sync_api import sync_playwright
    except ImportError:
        return {
            "ok": False,
            "error": "playwright not installed; run: pip install playwright && python -m playwright install chrome",
        }

    if plan not in {"standard", "pro"}:
        return {"ok": False, "error": f"unsupported plan: {plan}"}

    account = f"w17-sub-{plan}-{uuid.uuid4().hex[:8]}@test.local"
    password = "smoke-pass-12"
    landing = _landing_for_plan(plan)
    page_errors: list[str] = []
    login_gate_ok = False
    steps: list[dict[str, Any]] = []

    def record(step: str, ok: bool, detail: dict[str, Any] | None = None) -> None:
        steps.append({"step": step, "ok": ok, **(detail or {})})

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(channel="chrome", headless=headless)
            context = browser.new_context()
            page = context.new_page()
            page.on("pageerror", lambda err: page_errors.append(str(err)))
            root = base_url.rstrip("/")

            if test_login_gate:
                page.goto(f"{root}/web/payment.html?pay={plan}", wait_until="domcontentloaded", timeout=20000)
                page.wait_for_url("**/login.html**", timeout=10000)
                login_gate_ok = "login.html" in page.url and "return=" in page.url
                record("login_gate_redirect", login_gate_ok, {"url": page.url})
                if not login_gate_ok:
                    browser.close()
                    return {
                        "ok": False,
                        "plan": plan,
                        "account": account,
                        "login_gate_ok": login_gate_ok,
                        "steps": steps,
                        "page_errors": page_errors,
                    }
                context.clear_cookies()

            page.goto(f"{root}/web/login.html?mode=register&intent=free", wait_until="domcontentloaded", timeout=20000)
            page.fill("#authAccount", account)
            page.fill("#authPassword", password)
            page.fill("#authConfirm", password)
            page.click("#authSubmit")
            page.wait_for_url("**/backtest.html**", timeout=15000)
            record("register_free", "backtest.html" in page.url, {"url": page.url})

            plan_after_register = page.evaluate("() => localStorage.getItem('fj-plan')")
            record("register_plan_free", plan_after_register == "free", {"plan": plan_after_register})

            page.goto(f"{root}/web/pricing.html", wait_until="domcontentloaded", timeout=20000)
            page.wait_for_selector(_cta_selector(plan), timeout=10000)
            record("pricing_rendered", True, {"tiers": page.locator(".pricing-card").count()})

            page.locator(_cta_selector(plan)).first.click()
            page.wait_for_url(f"**/payment.html?pay={plan}**", timeout=15000)
            page.wait_for_selector("#payPanel:not([hidden])", timeout=10000)
            qr_visible = page.locator(".community-wechat-qr img").is_visible()
            record("payment_panel", qr_visible, {"url": page.url})

            page.click("#payConfirmBtn")
            page.wait_for_url(f"**/{landing}**", timeout=15000)
            final_plan = page.evaluate("() => localStorage.getItem('fj-plan')")
            has_token = page.evaluate("() => Boolean(localStorage.getItem('fj-access-token'))")
            record(
                "payment_confirm_landing",
                landing in page.url and final_plan == plan,
                {"url": page.url, "plan": final_plan, "has_token": has_token},
            )

            screenshot_dir = ROOT / "runtime" / "web_validation"
            screenshot_dir.mkdir(parents=True, exist_ok=True)
            shot = screenshot_dir / f"w17_subscription_{plan}_smoke.png"
            page.screenshot(path=str(shot), full_page=True)

            browser.close()
    except PlaywrightError as exc:
        return {"ok": False, "plan": plan, "error": f"playwright failed: {exc}", "steps": steps}

    ok = all(s.get("ok") for s in steps) and not page_errors
    return {
        "ok": ok,
        "plan": plan,
        "account": account,
        "landing": landing,
        "login_gate_ok": login_gate_ok if test_login_gate else None,
        "steps": steps,
        "page_errors": page_errors,
        "screenshot": str(shot) if "shot" in locals() else None,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="W17 subscription browser smoke (P3)")
    parser.add_argument("--base-url", default="")
    parser.add_argument("--port", type=int, default=8034)
    parser.add_argument("--auto-server", action="store_true")
    parser.add_argument("--headed", action="store_true")
    parser.add_argument("--plan", choices=["standard", "pro", "both"], default="both")
    parser.add_argument("--skip-login-gate", action="store_true", help="Skip unauthenticated payment redirect check")
    args = parser.parse_args()

    _ensure_dev_env()
    proc: subprocess.Popen[Any] | None = None
    results: list[dict[str, Any]] = []

    try:
        base_url = args.base_url.rstrip("/")
        if args.auto_server or not base_url:
            proc, base_url = start_uvicorn(args.port)
            wait_for_health(base_url)

        plans = ["standard", "pro"] if args.plan == "both" else [args.plan]
        for plan in plans:
            result = browser_subscription_flow(
                base_url,
                plan=plan,
                headless=not args.headed,
                test_login_gate=not args.skip_login_gate and plan == plans[0],
            )
            results.append(result)

        ok = all(r.get("ok") for r in results)
        payload = {"ok": ok, "base_url": base_url, "flows": results}
    except Exception as exc:  # noqa: BLE001
        payload = {"ok": False, "error": str(exc), "flows": results}
        ok = False
    finally:
        if proc is not None:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()

    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
