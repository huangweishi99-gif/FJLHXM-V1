#!/usr/bin/env python3
"""W15 browser smoke: strategies.html SVG/CSS loop animations + modal pause.

Requires optional dev deps (not in requirements.txt):
  pip install playwright
  python -m playwright install chrome

Usage:
  python scripts/smoke_w15_strategies_browser.py --auto-server
  python scripts/smoke_w15_strategies_browser.py --base-url http://127.0.0.1:8000
  python scripts/smoke_w15_strategies_browser.py --offline-skip-browser
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from smoke_w17_auth_ws import start_uvicorn, wait_for_health  # noqa: E402


def http_strategies_ok(base_url: str) -> dict[str, Any]:
    url = f"{base_url.rstrip('/')}/web/strategies.html"
    try:
        with urlopen(url, timeout=10) as resp:
            html = resp.read().decode("utf-8", errors="replace")
            status = resp.status
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": str(exc), "url": url}

    markers = [
        "strategy_animations.js",
        "strategy-anim-modal",
        "FengJiStrategyAnim",
        "10s 循环",
    ]
    missing = [m for m in markers if m not in html]
    anim_js_url = f"{base_url.rstrip('/')}/web/js/strategy_animations.js"
    try:
        with urlopen(anim_js_url, timeout=10) as resp:
            anim_js = resp.read().decode("utf-8", errors="replace")
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": f"strategy_animations.js fetch failed: {exc}"}

    if "FengJiStrategyAnim" not in anim_js:
        missing.append("FengJiStrategyAnim@js")

    return {
        "ok": status == 200 and not missing,
        "status": status,
        "url": url,
        "missing_markers": missing,
    }


def browser_strategies_smoke(base_url: str, *, headless: bool = True) -> dict[str, Any]:
    try:
        from playwright.sync_api import Error as PlaywrightError
        from playwright.sync_api import sync_playwright
    except ImportError:
        return {
            "ok": False,
            "error": "playwright not installed; run: pip install playwright && python -m playwright install chrome",
        }

    page_errors: list[str] = []
    shot_grid: Path | None = None
    shot_modal: Path | None = None
    svg_count = 0
    lottie_count = 0
    anim_count = 0
    engine_tag = ""
    modal_visible = False
    paused = False
    deep_link_ok = False

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(channel="chrome", headless=headless)
            context = browser.new_context(viewport={"width": 1280, "height": 900})
            page = context.new_page()
            page.on("pageerror", lambda err: page_errors.append(str(err)))

            seed_url = f"{base_url.rstrip('/')}/web/index.html"
            page.goto(seed_url, wait_until="domcontentloaded", timeout=20000)
            page.evaluate(
                """() => {
                  localStorage.setItem('fj-plan', 'standard');
                  localStorage.removeItem('fj-access-token');
                  localStorage.removeItem('fj-auth');
                }"""
            )

            strategies_url = f"{base_url.rstrip('/')}/web/strategies.html"
            page.goto(strategies_url, wait_until="domcontentloaded", timeout=20000)

            page.wait_for_selector(".strategy-anim-lottie, .strategy-anim-svg", timeout=20000)
            svg_count = page.locator(".strategy-anim-svg").count()
            lottie_count = page.locator(".strategy-anim-lottie").count()
            anim_count = svg_count + lottie_count
            engine_tag = page.locator(".strategy-engine-tag").first.inner_text(timeout=5000)

            first_preview = page.locator(
                ".strategy-card-module:not(.strategy-card-locked) .strategy-animate-preview"
            ).first
            first_preview.click(timeout=5000)

            modal = page.locator("#strategyAnimModal")
            page.wait_for_function(
                """() => {
                  const el = document.getElementById('strategyAnimModal');
                  return el && !el.hidden;
                }""",
                timeout=8000,
            )
            modal_visible = modal.is_visible()
            page.wait_for_selector("#strategyAnimModalStage .strategy-anim-lottie, #strategyAnimModalStage .strategy-anim-svg", timeout=12000)

            page.locator("#strategyAnimPauseBtn").click(timeout=3000)
            page.wait_for_selector("#strategyAnimModalStage .is-paused", timeout=8000)
            paused = page.locator("#strategyAnimModalStage .is-paused").count() > 0

            page.locator("#strategyAnimCloseBtn").click(timeout=3000)
            page.wait_for_function(
                """() => {
                  const el = document.getElementById('strategyAnimModal');
                  return el && el.hidden;
                }""",
                timeout=5000,
            )

            page.goto(
                f"{base_url.rstrip('/')}/web/strategies.html?strategy=DS01&open=1",
                wait_until="domcontentloaded",
                timeout=20000,
            )
            page.wait_for_function(
                """() => {
                  const el = document.getElementById('strategyAnimModal');
                  return el && !el.hidden;
                }""",
                timeout=8000,
            )
            deep_link_ok = page.locator("#strategyAnimModalStage .strategy-anim-lottie, #strategyAnimModalStage .strategy-anim-svg").count() > 0

            screenshot_dir = ROOT / "runtime" / "web_validation"
            screenshot_dir.mkdir(parents=True, exist_ok=True)
            shot_grid = screenshot_dir / "w15_strategies_browser_smoke.png"
            shot_modal = screenshot_dir / "w15_strategies_modal_smoke.png"
            page.screenshot(path=str(shot_grid), full_page=True)
            modal.screenshot(path=str(shot_modal))

            browser.close()
    except PlaywrightError as exc:
        return {"ok": False, "error": f"playwright failed: {exc}", "page_errors": page_errors}

    ok = (
        anim_count >= 9
        and "fengji_core" in engine_tag
        and modal_visible
        and paused
        and deep_link_ok
        and not page_errors
    )
    return {
        "ok": ok,
        "svg_count": svg_count,
        "lottie_count": lottie_count,
        "anim_count": anim_count,
        "engine_tag": engine_tag,
        "modal_visible": modal_visible,
        "paused": paused,
        "deep_link_ok": deep_link_ok,
        "page_errors": page_errors,
        "screenshot": str(shot_grid) if shot_grid else None,
        "screenshot_modal": str(shot_modal) if shot_modal else None,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="W15 strategies browser animation smoke")
    parser.add_argument("--base-url", default="")
    parser.add_argument("--port", type=int, default=8033)
    parser.add_argument("--auto-server", action="store_true")
    parser.add_argument("--headed", action="store_true")
    parser.add_argument(
        "--offline-skip-browser",
        action="store_true",
        help="Only HTTP/static marker checks (no Playwright)",
    )
    args = parser.parse_args()

    proc: subprocess.Popen[Any] | None = None
    result: dict[str, Any] = {"ok": False}

    try:
        base_url = args.base_url.rstrip("/")
        if args.auto_server or not base_url:
            proc, base_url = start_uvicorn(args.port)
            wait_for_health(base_url)

        http = http_strategies_ok(base_url)
        if not http.get("ok"):
            result = {"ok": False, "mode": "http", "base_url": base_url, **http}
        elif args.offline_skip_browser:
            result = {"ok": True, "mode": "http-only", "base_url": base_url, **http}
        else:
            browser = browser_strategies_smoke(base_url, headless=not args.headed)
            result = {
                "ok": bool(browser.get("ok")),
                "mode": "browser",
                "base_url": base_url,
                **http,
                **browser,
            }
    except Exception as exc:  # noqa: BLE001
        result = {"ok": False, "error": str(exc)}
    finally:
        if proc is not None:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
