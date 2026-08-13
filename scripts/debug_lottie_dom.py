#!/usr/bin/env python3
"""Debug strategies page Lottie DOM."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from smoke_w17_auth_ws import start_uvicorn, wait_for_health  # noqa: E402


def main() -> int:
    proc, base = start_uvicorn(8034)
    try:
        wait_for_health(base)
        from playwright.sync_api import sync_playwright

        errors: list[str] = []
        with sync_playwright() as p:
            browser = p.chromium.launch(channel="chrome", headless=True)
            page = browser.new_page()
            page.on("pageerror", lambda e: errors.append(str(e)))
            page.on("console", lambda m: errors.append(f"console:{m.type}:{m.text}") if m.type == "error" else None)
            page.goto(f"{base}/web/index.html", wait_until="domcontentloaded")
            page.evaluate("() => localStorage.setItem('fj-plan', 'standard')")
            page.goto(f"{base}/web/strategies.html", wait_until="networkidle", timeout=30000)
            page.wait_for_timeout(3500)
            info = page.evaluate(
                """() => {
                  const h = document.querySelector('.strategy-anim-lottie');
                  if (!h) return { error: 'no lottie holder' };
                  const svg = h.querySelector('svg');
                  return {
                    htmlLen: h.innerHTML.length,
                    svgCount: h.querySelectorAll('svg').length,
                    svgW: svg?.getAttribute('width'),
                    svgH: svg?.getAttribute('height'),
                    paths: h.querySelectorAll('path').length,
                    rects: h.querySelectorAll('rect').length,
                    groups: h.querySelectorAll('g').length,
                    svgHtml: svg?.innerHTML?.slice(0, 500) || '',
                  };
                }"""
            )
            lottie_type = page.evaluate("() => typeof window.lottie")
            print(json.dumps({"lottie": lottie_type, "dom": info, "errors": errors}, ensure_ascii=False, indent=2))
            browser.close()
    finally:
        proc.terminate()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
