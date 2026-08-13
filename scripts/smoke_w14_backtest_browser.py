#!/usr/bin/env python3
"""Wave 2 D4b: backtest.html browser smoke — four markets search + load.

Requires: pip install playwright && python -m playwright install chrome

Usage:
  python scripts/smoke_w14_backtest_browser.py --base-url http://127.0.0.1:8000
  python scripts/smoke_w14_backtest_browser.py --auto-server
  python scripts/smoke_w14_backtest_browser.py --offline-skip-browser
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

MARKET_SAMPLES = [
    {"market": "A_STOCK", "query": "000021", "pick": "000021", "strategy": "DS01"},
    {"market": "FUTURES", "query": "RB", "pick": "RB", "strategy": "DS01"},
    {"market": "CRYPTO", "query": "SOL", "pick": "SOLUSDT", "strategy": "DS03"},
    {"market": "US_STOCK", "query": "NVDA", "pick": "NVDA", "strategy": "DS01"},
]


def http_backtest_ok(base_url: str) -> dict[str, Any]:
    url = f"{base_url.rstrip('/')}/web/backtest.html"
    try:
        with urlopen(url, timeout=10) as resp:
            html = resp.read().decode("utf-8", errors="replace")
            status = resp.status
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": str(exc), "url": url}

    markers = ["symbolSearch", "loadBtn", "chartPanel", "backtest-toolbar"]
    missing = [m for m in markers if m not in html]
    return {"ok": status == 200 and not missing, "status": status, "url": url, "missing_markers": missing}


def browser_backtest_smoke(base_url: str, *, headless: bool = True) -> dict[str, Any]:
    try:
        from playwright.sync_api import Error as PlaywrightError
        from playwright.sync_api import sync_playwright
    except ImportError:
        return {
            "ok": False,
            "error": "playwright not installed; pip install playwright && python -m playwright install chrome",
        }

    page_errors: list[str] = []
    results: list[dict[str, Any]] = []
    shot_dir = ROOT / "runtime" / "web_validation"
    shot_dir.mkdir(parents=True, exist_ok=True)

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(channel="chrome", headless=headless)

            for sample in MARKET_SAMPLES:
                market = sample["market"]
                sym = sample["pick"]
                strat = sample.get("strategy") or "DS01"
                url = (
                    f"{base_url.rstrip('/')}/web/backtest.html"
                    f"?market={market}&symbol={sym}&strategy={strat}&years=3"
                )
                context = browser.new_context(viewport={"width": 1400, "height": 900})
                context.add_init_script(
                    """() => {
                      localStorage.setItem('fj-plan', 'pro');
                      localStorage.removeItem('fj-watchlist-v1');
                    }"""
                )
                page = context.new_page()
                page.on("pageerror", lambda err: page_errors.append(str(err)))

                page.goto(url, wait_until="domcontentloaded", timeout=30000)
                page.wait_for_function(
                    f"""() => {{
                      const sel = document.getElementById('strategy');
                      return sel && sel.value === '{strat}';
                    }}""",
                    timeout=30000,
                )
                page.wait_for_function(
                    """() => {
                      const t = document.getElementById('chartMeta')?.textContent || '';
                      const s = document.getElementById('statusBar')?.textContent || '';
                      const err = s.includes('失败') || s.includes('不可用') || s.includes('超时');
                      return (t.includes('根K线') || s.includes('已加载')) && !err;
                    }""",
                    timeout=180000,
                )
                meta = page.locator("#chartMeta").inner_text(timeout=5000)
                status = page.locator("#statusBar").inner_text(timeout=5000)
                shot = shot_dir / f"w14_backtest_{market.lower()}.png"
                page.locator("#chartPanel").screenshot(path=str(shot))
                ok = "根K线" in meta and "失败" not in status and "超时" not in status
                results.append(
                    {
                        "market": market,
                        "symbol": sample["pick"],
                        "ok": ok,
                        "chart_meta": meta[:120],
                        "status": status[:80],
                        "screenshot": str(shot),
                    }
                )
                context.close()

            browser.close()
    except PlaywrightError as exc:
        return {"ok": False, "error": f"playwright failed: {exc}", "page_errors": page_errors, "markets": results}

    ok = all(r.get("ok") for r in results) and not page_errors
    return {"ok": ok, "markets": results, "page_errors": page_errors}


def main() -> int:
    parser = argparse.ArgumentParser(description="W14 backtest browser smoke (4 markets)")
    parser.add_argument("--base-url", default="")
    parser.add_argument("--port", type=int, default=8034)
    parser.add_argument("--auto-server", action="store_true")
    parser.add_argument("--headed", action="store_true")
    parser.add_argument("--offline-skip-browser", action="store_true")
    args = parser.parse_args()

    proc: subprocess.Popen[Any] | None = None
    result: dict[str, Any] = {"ok": False}

    try:
        base_url = args.base_url.rstrip("/")
        if args.auto_server or not base_url:
            proc, base_url = start_uvicorn(args.port)
            wait_for_health(base_url)

        http = http_backtest_ok(base_url)
        if not http.get("ok"):
            result = {"ok": False, "mode": "http", "base_url": base_url, **http}
        elif args.offline_skip_browser:
            result = {"ok": True, "mode": "http-only", "base_url": base_url, **http}
        else:
            browser = browser_backtest_smoke(base_url, headless=not args.headed)
            result = {"ok": bool(browser.get("ok")), "mode": "browser", "base_url": base_url, **http, **browser}
    except Exception as exc:  # noqa: BLE001
        result = {"ok": False, "error": str(exc)}
    finally:
        if proc is not None:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()

    out = ROOT / "runtime" / "web_validation" / "w14_backtest_browser_smoke.json"
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
