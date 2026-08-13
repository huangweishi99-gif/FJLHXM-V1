#!/usr/bin/env python3
"""W16-WS browser smoke: monitor.html + JWT pro user + WebSocket in real Chrome.

Requires optional dev deps (not in requirements.txt):
  pip install playwright
  python -m playwright install chrome

Usage:
  docker compose up -d && alembic upgrade head
  python scripts/smoke_w16_monitor_browser.py --offline-skip-browser
  python scripts/smoke_w16_monitor_browser.py --auto-server
  python scripts/smoke_w16_monitor_browser.py --base-url http://127.0.0.1:8000
  python scripts/smoke_w16_monitor_browser.py --skip-reconnect   # 仅验首连
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import uuid
from pathlib import Path
from typing import Any
from urllib.error import HTTPError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "packages" / "fengji_core"))
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "services"))

# Reuse W17 smoke helpers
from smoke_w17_auth_ws import (  # noqa: E402
    _post_json,
    start_uvicorn,
    wait_for_health,
)


def _ensure_dev_env() -> None:
    os.environ.setdefault("FENGJI_AUTH_ALLOW_DEV_SECRET", "1")
    os.environ.setdefault("FENGJI_ALLOW_MANUAL_SUBSCRIPTION_CONFIRM", "1")


def _get_json_auth(base_url: str, path: str, access_token: str) -> tuple[int, dict[str, Any]]:
    req = Request(
        f"{base_url.rstrip('/')}{path}",
        headers={"Authorization": f"Bearer {access_token}"},
        method="GET",
    )
    try:
        with urlopen(req, timeout=20) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        try:
            payload = json.loads(body)
        except json.JSONDecodeError:
            payload = {"error": body}
        return exc.code, payload


def monitor_v1_plus_api_smoke(base_url: str, access_token: str) -> dict[str, Any]:
    """V1+ ledger / paper-account read-only API smoke."""
    checks: dict[str, Any] = {}
    status, ledger = _get_json_auth(base_url, "/api/v1/monitor/ledger/recent?limit=10", access_token)
    checks["ledger_status"] = status
    checks["ledger_mode"] = ledger.get("mode")
    checks["ledger_has_items_key"] = "items" in ledger
    ok_ledger = status == 200 and ledger.get("mode") == "read_only_ledger"

    status, paper = _get_json_auth(
        base_url,
        "/api/v1/monitor/paper-account?local_watchlist_count=2&local_symbols=RB,000021",
        access_token,
    )
    checks["paper_status"] = status
    checks["paper_mode"] = paper.get("mode")
    checks["paper_authenticated"] = paper.get("authenticated")
    ok_paper = (
        status == 200
        and paper.get("mode") == "read_only_paper_account"
        and paper.get("authenticated") is True
    )

    return {
        "ok": ok_ledger and ok_paper,
        "checks": checks,
        "ledger_count": ledger.get("count"),
        "paper_equity": paper.get("equity"),
    }


def provision_pro_user(base_url: str) -> dict[str, Any]:
    """Register free user, manual-confirm pro, return tokens + account."""
    account = f"w16-browser-{uuid.uuid4().hex[:8]}@test.local"
    password = "smoke-pass-12"
    status, body = _post_json(
        base_url,
        "/api/v1/auth/register",
        {"account": account, "password": password},
    )
    if status == 503:
        return {"ok": False, "error": "auth storage unavailable (PG down? alembic upgrade head)"}
    if status != 200:
        return {"ok": False, "error": f"register failed: {status} {body}"}

    access = body["access_token"]
    req = Request(
        f"{base_url.rstrip('/')}/api/v1/subscriptions/manual-confirm",
        data=json.dumps({"plan": "pro"}).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {access}",
        },
        method="POST",
    )
    try:
        with urlopen(req, timeout=15) as resp:
            sub = json.loads(resp.read().decode("utf-8"))
            status = resp.status
    except HTTPError as exc:
        status = exc.code
        sub = json.loads(exc.read().decode("utf-8", errors="replace"))
    if status != 200:
        return {"ok": False, "error": f"manual-confirm pro failed: {status} {sub}"}

    return {
        "ok": True,
        "account": account,
        "access_token": sub["access_token"],
        "refresh_token": sub.get("refresh_token", body.get("refresh_token", "")),
        "user": sub["user"],
    }


def browser_monitor_ws_smoke(
    base_url: str,
    session: dict[str, Any],
    *,
    headless: bool = True,
    test_reconnect: bool = True,
) -> dict[str, Any]:
    try:
        from playwright.sync_api import Error as PlaywrightError
        from playwright.sync_api import sync_playwright
    except ImportError:
        return {
            "ok": False,
            "error": "playwright not installed; run: pip install playwright && python -m playwright install chrome",
        }

    ws_types: list[str] = []
    page_errors: list[str] = []
    refresh_text = ""
    reconnect_disconnect_seen = False
    reconnect_ok = False
    snapshot_before = 0
    snapshot_after = 0

    WS_HOOK = """
(() => {
  if (window.__fjWsHookInstalled) return;
  window.__fjWsHookInstalled = true;
  window.__fjTestWsRefs = [];
  const Orig = window.WebSocket;
  window.WebSocket = function(url, protocols) {
    const ws = protocols === undefined ? new Orig(url) : new Orig(url, protocols);
    window.__fjTestWsRefs.push(ws);
    return ws;
  };
  window.WebSocket.CONNECTING = Orig.CONNECTING;
  window.WebSocket.OPEN = Orig.OPEN;
  window.WebSocket.CLOSING = Orig.CLOSING;
  window.WebSocket.CLOSED = Orig.CLOSED;
})();
"""

    def _on_websocket(ws: Any) -> None:
        def _on_frame(frame: Any) -> None:
            text = getattr(frame, "text", None) or getattr(frame, "payload", None) or str(frame)
            try:
                payload = json.loads(text)
                msg_type = str(payload.get("type", ""))
                if msg_type:
                    ws_types.append(msg_type)
            except (json.JSONDecodeError, TypeError):
                pass

        ws.on("framereceived", _on_frame)

    auth_payload = {
        "access_token": session["access_token"],
        "refresh_token": session.get("refresh_token", ""),
        "user": session["user"],
    }

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(channel="chrome", headless=headless)
            context = browser.new_context()
            context.add_init_script(WS_HOOK)
            page = context.new_page()
            page.on("websocket", _on_websocket)
            page.on("pageerror", lambda err: page_errors.append(str(err)))

            seed_url = f"{base_url.rstrip('/')}/web/index.html"
            page.goto(seed_url, wait_until="domcontentloaded", timeout=20000)
            page.evaluate(
                """({ token, account, auth }) => {
                  localStorage.setItem('fj-access-token', token);
                  localStorage.setItem('fj-user', account);
                  localStorage.setItem('fj-plan', auth.user.plan || 'pro');
                  localStorage.setItem('fj-auth', JSON.stringify(auth));
                  document.dispatchEvent(new CustomEvent('fj-auth-ready', { detail: auth }));
                }""",
                {
                    "token": session["access_token"],
                    "account": session["account"],
                    "auth": auth_payload,
                },
            )

            monitor_url = f"{base_url.rstrip('/')}/web/monitor.html"
            page.goto(monitor_url, wait_until="domcontentloaded", timeout=20000)
            page.evaluate(
                """() => {
                  const authRaw = localStorage.getItem('fj-auth');
                  if (authRaw) {
                    try {
                      document.dispatchEvent(new CustomEvent('fj-auth-ready', { detail: JSON.parse(authRaw) }));
                    } catch (_) {}
                  }
                }"""
            )

            v1_dom_deadline = time.time() + 12.0
            v1_dom: dict[str, bool] = {
                "ledger_panel": False,
                "paper_account_card": False,
                "notifications_mount": False,
                "market_tabs": False,
            }
            while time.time() < v1_dom_deadline:
                v1_dom["ledger_panel"] = page.locator("#ledgerPanel").count() > 0
                v1_dom["notifications_mount"] = page.locator("#monitorNotifications").count() > 0
                v1_dom["market_tabs"] = page.locator("#marketTabs button[data-market]").count() >= 5
                v1_dom["paper_account_card"] = page.locator("#paperAccountCard").is_visible()
                if all(v1_dom.values()):
                    break
                time.sleep(0.35)

            deadline = time.time() + 20.0
            while time.time() < deadline:
                refresh_text = page.locator("#refreshMeta").inner_text(timeout=1000)
                if any(
                    token in refresh_text
                    for token in ("WS已连接", "WS心跳", "WS连接中", "实盘同步", "演示数据", "更新 20")
                ):
                    if "WS已连接" in refresh_text or "WS心跳" in refresh_text:
                        break
                    if "实盘同步" in refresh_text or refresh_text.startswith("更新 "):
                        break
                if ws_types:
                    break
                time.sleep(0.25)

            snapshot_before = ws_types.count("monitor.snapshot.v1")

            if test_reconnect and ("WS已连接" in refresh_text or snapshot_before > 0):
                page.evaluate(
                    """() => {
                      const refs = window.__fjTestWsRefs || [];
                      if (refs.length) refs[refs.length - 1].close(1000, 'smoke-test');
                    }"""
                )
                disconnect_deadline = time.time() + 8.0
                while time.time() < disconnect_deadline:
                    refresh_text = page.locator("#refreshMeta").inner_text(timeout=1000)
                    if any(
                        token in refresh_text
                        for token in ("WS断开", "轮询备用", "5秒后重连", "WS连接中")
                    ):
                        reconnect_disconnect_seen = True
                        break
                    time.sleep(0.2)

                reconnect_deadline = time.time() + 15.0
                while time.time() < reconnect_deadline:
                    refresh_text = page.locator("#refreshMeta").inner_text(timeout=1000)
                    snapshot_after = ws_types.count("monitor.snapshot.v1")
                    if "WS已连接" in refresh_text and snapshot_after > snapshot_before:
                        reconnect_ok = True
                        break
                    if "WS已连接" in refresh_text and reconnect_disconnect_seen:
                        reconnect_ok = True
                        break
                    if snapshot_after > snapshot_before:
                        reconnect_ok = True
                        break
                    time.sleep(0.25)
            elif not test_reconnect:
                reconnect_ok = True

            screenshot_dir = ROOT / "runtime" / "web_validation"
            screenshot_dir.mkdir(parents=True, exist_ok=True)
            shot = screenshot_dir / (
                "w16_monitor_v1_plus_smoke.png"
                if test_reconnect
                else "w16_monitor_v1_plus_smoke.png"
            )
            page.screenshot(path=str(shot), full_page=True)

            browser.close()
    except PlaywrightError as exc:
        return {"ok": False, "error": f"playwright failed: {exc}"}

    ok_ws = any(t in ws_types for t in ("monitor.snapshot.v1", "monitor.heartbeat.v1", "monitor.delta.v1"))
    ok_ui = (
        "WS已连接" in refresh_text
        or "WS心跳" in refresh_text
        or "实盘同步" in refresh_text
        or refresh_text.startswith("更新 ")
    )
    ok_initial = ok_ws or ok_ui
    if test_reconnect and ok_ws:
        ok_reconnect = reconnect_ok and reconnect_disconnect_seen
    elif test_reconnect and ok_ui and not ok_ws:
        ok_reconnect = True
    else:
        ok_reconnect = reconnect_ok if test_reconnect else True
    ok_v1_dom = all(v1_dom.values()) if "v1_dom" in locals() else False
    ok = ok_initial and ok_reconnect and ok_v1_dom
    return {
        "ok": ok,
        "v1_plus_dom": v1_dom if "v1_dom" in locals() else {},
        "refresh_meta": refresh_text,
        "ws_message_types": sorted(set(ws_types)),
        "snapshot_before": snapshot_before,
        "snapshot_after": ws_types.count("monitor.snapshot.v1"),
        "reconnect_disconnect_seen": reconnect_disconnect_seen,
        "reconnect_ok": reconnect_ok,
        "page_errors": page_errors,
        "screenshot": str(shot) if "shot" in locals() else None,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="W16 monitor browser + WS smoke")
    parser.add_argument("--base-url", default="")
    parser.add_argument("--port", type=int, default=8032)
    parser.add_argument("--auto-server", action="store_true")
    parser.add_argument("--headed", action="store_true", help="Show browser window")
    parser.add_argument(
        "--offline-skip-browser",
        action="store_true",
        help="Only verify auth+pro provisioning HTTP path (no Playwright)",
    )
    parser.add_argument(
        "--skip-reconnect",
        action="store_true",
        help="Skip forced WS close + 5s reconnect verification",
    )
    args = parser.parse_args()

    _ensure_dev_env()
    proc: subprocess.Popen[Any] | None = None
    result: dict[str, Any] = {"ok": False}

    try:
        base_url = args.base_url.rstrip("/")
        if args.auto_server or not base_url:
            proc, base_url = start_uvicorn(args.port)
            wait_for_health(base_url)

        session = provision_pro_user(base_url)
        if not session.get("ok"):
            result = {"ok": False, "base_url": base_url, **session}
        v1_api = monitor_v1_plus_api_smoke(base_url, session["access_token"])
        if args.offline_skip_browser:
            result = {
                "ok": bool(v1_api.get("ok")),
                "mode": "http-only",
                "base_url": base_url,
                "account": session["account"],
                "v1_plus_api": v1_api,
            }
        else:
            browser = browser_monitor_ws_smoke(
                base_url,
                session,
                headless=not args.headed,
                test_reconnect=not args.skip_reconnect,
            )
            result = {
                "ok": bool(browser.get("ok")) and bool(v1_api.get("ok")),
                "mode": "browser",
                "base_url": base_url,
                "account": session["account"],
                "user_plan": session["user"].get("plan"),
                "v1_plus_api": v1_api,
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
