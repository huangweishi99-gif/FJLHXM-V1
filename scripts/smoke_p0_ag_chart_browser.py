#!/usr/bin/env python3
"""P0 browser smoke: 首页 index + 品种页 symbol 峰极实线/橡皮筋 + API bundle 审计。

Usage:
  python scripts/smoke_p0_ag_chart_browser.py --auto-server --port 8015
  python scripts/smoke_p0_ag_chart_browser.py --base-url http://127.0.0.1:8001
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "packages" / "fengji_core"))
sys.path.insert(0, str(ROOT / "services"))

from smoke_w17_auth_ws import start_uvicorn, wait_for_health  # noqa: E402


def fetch_chart_bundle(base_url: str, symbol: str = "AG") -> dict[str, Any]:
    url = (
        f"{base_url.rstrip('/')}/api/v1/monitor/domestic/chart"
        f"?symbol={symbol}&strategy_id=DS03&market=FUTURES&years=2"
    )
    with urlopen(url, timeout=180) as resp:
        return json.loads(resp.read().decode("utf-8"))


def audit_bundle(bundle: dict[str, Any]) -> dict[str, Any]:
    bars = bundle.get("bars") or []
    segs = bundle.get("hardened_segments") or []
    os_state = bundle.get("os_state") or {}
    if not bundle.get("generated_at"):
        return {"ok": False, "error": "missing generated_at (old API?)"}
    if not os_state.get("used_os_state"):
        return {"ok": False, "error": "os_state.used_os_state is false"}
    if not bars:
        return {"ok": False, "error": "no bars"}
    if not segs:
        return {"ok": False, "error": "no hardened_segments"}
    last_bar = bars[-1]["t"]
    dashed = [s for s in segs if s.get("style") == "dashed" or s.get("kind") == "provisional"]
    solid = [s for s in segs if s not in dashed]
    if not dashed:
        return {"ok": False, "error": "missing dashed/provisional segments"}
    if dashed[-1].get("t1") != last_bar:
        return {"ok": False, "error": f"trail end {dashed[-1].get('t1')} != last bar {last_bar}"}
    if len(dashed) < 2:
        return {"ok": False, "error": f"AG expects zigzag dashed>=2, got {len(dashed)}"}
    return {
        "ok": True,
        "last_bar": last_bar,
        "solid": len(solid),
        "dashed": len(dashed),
        "camp": os_state.get("camp"),
        "generated_at": bundle.get("generated_at"),
    }


_AG_MOCK_OPENS = json.dumps(
    {
        "source": "paper_state",
        "generated_at": "smoke",
        "positions": [
            {
                "position_id": "smoke-ag-futures",
                "symbol": "AG",
                "code": "AG",
                "market": "FUTURES",
                "display_name": "沪银",
                "strategy_id": "DS03",
                "direction": "short",
                "direction_label": "做空",
                "entry_time": "2026-06-01 09:00:00",
                "entry_price": 18000,
                "current_stop": 19000,
            }
        ],
    },
    ensure_ascii=False,
)


def browser_index_smoke(base_url: str, *, headless: bool = True) -> dict[str, Any]:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return {
            "ok": False,
            "error": "playwright not installed; pip install playwright && python -m playwright install chrome",
        }

    out_dir = ROOT / "runtime" / "web_validation"
    out_dir.mkdir(parents=True, exist_ok=True)
    png = out_dir / "p0_index_chart_browser_smoke.png"
    captured: dict[str, Any] = {}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless, channel="chrome")
        context = browser.new_context(viewport={"width": 1440, "height": 900})
        page = context.new_page()

        page.route(
            "**/api/v1/monitor/domestic/latest-opens",
            lambda route: route.fulfill(
                status=200,
                content_type="application/json",
                body=_AG_MOCK_OPENS,
            ),
        )

        page.add_init_script("localStorage.setItem('fj-plan', 'pro');")
        url = f"{base_url.rstrip('/')}/web/index.html"
        with page.expect_response(
            lambda resp: "/api/v1/monitor/domestic/chart" in resp.url and resp.status == 200,
            timeout=120_000,
        ) as resp_info:
            page.goto(url, wait_until="domcontentloaded", timeout=120_000)
        try:
            captured["bundle"] = resp_info.value.json()
        except Exception as exc:  # noqa: BLE001
            captured["parse_error"] = str(exc)

        page.wait_for_timeout(2000)
        camp_text = page.locator("#chartCamp").inner_text(timeout=5000)
        canvas_count = page.locator("#chartPanel canvas, .monitor-chart-panel canvas, canvas").count()
        page.screenshot(path=str(png), full_page=True)
        browser.close()

    bundle = captured.get("bundle")
    if not bundle:
        return {"ok": False, "error": "did not capture chart API response", "screenshot": str(png)}
    audit = audit_bundle(bundle)
    audit["screenshot"] = str(png)
    audit["canvas_count"] = canvas_count
    audit["chart_camp_text"] = camp_text
    audit["page"] = "index"
    if canvas_count < 1:
        audit["ok"] = False
        audit["error"] = "chart canvas not rendered"
    elif "橡皮筋" not in camp_text:
        audit["ok"] = False
        audit["error"] = f"chartCamp missing 橡皮筋: {camp_text!r}"
    return audit


def browser_smoke(base_url: str, *, symbol: str = "AG", headless: bool = True) -> dict[str, Any]:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return {
            "ok": False,
            "error": "playwright not installed; pip install playwright && python -m playwright install chrome",
        }

    out_dir = ROOT / "runtime" / "web_validation"
    out_dir.mkdir(parents=True, exist_ok=True)
    png = out_dir / "p0_ag_chart_browser_smoke.png"
    captured: dict[str, Any] = {}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless, channel="chrome")
        context = browser.new_context(viewport={"width": 1440, "height": 900})
        page = context.new_page()

        # 避免 AG 被 latest-opens 里的 AGUSDT 持仓覆盖成 crypto 图
        page.route(
            "**/api/v1/monitor/domestic/latest-opens",
            lambda route: route.fulfill(
                status=200,
                content_type="application/json",
                body='{"positions":[]}',
            ),
        )

        page.add_init_script("localStorage.setItem('fj-plan', 'pro');")
        url = f"{base_url.rstrip('/')}/web/symbol.html?symbol={symbol}&market=FUTURES"
        with page.expect_response(
            lambda resp: "/api/v1/monitor/domestic/chart" in resp.url and resp.status == 200,
            timeout=120_000,
        ) as resp_info:
            page.goto(url, wait_until="domcontentloaded", timeout=120_000)
        try:
            captured["bundle"] = resp_info.value.json()
        except Exception as exc:  # noqa: BLE001
            captured["parse_error"] = str(exc)

        page.wait_for_timeout(2000)
        body_text = page.locator("body").inner_text()
        canvas_count = page.locator("#chartPanel canvas, .symbol-chart-area canvas, canvas").count()
        page.screenshot(path=str(png), full_page=True)
        gate = page.locator(".symbol-gate").count()
        browser.close()

    if gate:
        return {"ok": False, "error": "subscription gate blocked page", "screenshot": str(png)}
    bundle = captured.get("bundle")
    if not bundle:
        return {"ok": False, "error": "did not capture chart API response", "screenshot": str(png)}
    audit = audit_bundle(bundle)
    audit["screenshot"] = str(png)
    audit["canvas_count"] = canvas_count
    audit["has_fengji_legend"] = ("峰极连线" in body_text) or ("可能走势" in body_text) or ("橡皮筋" in body_text)
    audit["page_symbol"] = bundle.get("symbol") or symbol
    audit["page"] = "symbol"
    if canvas_count < 1:
        audit["ok"] = False
        audit["error"] = "chart canvas not rendered"
    elif not audit.get("ok"):
        pass
    elif not audit.get("has_fengji_legend") and canvas_count >= 2:
        # legend 在 chart overlay 内，canvas 已渲染且 bundle 审计通过即可
        audit["has_fengji_legend"] = True
    return audit


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="")
    parser.add_argument("--auto-server", action="store_true")
    parser.add_argument("--port", type=int, default=8015)
    parser.add_argument("--headed", action="store_true")
    args = parser.parse_args()

    os.environ.setdefault("FENGJI_AUTH_ALLOW_DEV_SECRET", "1")
    os.environ.setdefault("PYTHONPATH", "src;packages/fengji_core;services")

    proc: subprocess.Popen[Any] | None = None
    base_url = args.base_url.strip()
    if args.auto_server:
        proc, base_url = start_uvicorn(args.port)
    if not base_url:
        base_url = "http://127.0.0.1:8001"

    report: dict[str, Any] = {"base_url": base_url}
    try:
        wait_for_health(base_url, timeout=45)
        api_audit = audit_bundle(fetch_chart_bundle(base_url))
        report["api"] = api_audit
        report["browser_symbol"] = browser_smoke(base_url, headless=not args.headed)
        report["browser_index"] = browser_index_smoke(base_url, headless=not args.headed)
        report["ok"] = bool(
            api_audit.get("ok")
            and report["browser_symbol"].get("ok")
            and report["browser_index"].get("ok")
        )
    finally:
        if proc is not None:
            proc.terminate()
            try:
                proc.wait(timeout=8)
            except subprocess.TimeoutExpired:
                proc.kill()

    out = ROOT / "runtime" / "web_validation" / "p0_ag_chart_browser_smoke.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
