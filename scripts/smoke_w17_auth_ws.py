#!/usr/bin/env python3
"""W17-prod smoke: auth register/login/refresh/me + monitor WS with JWT.

Usage:
  docker compose up -d && alembic upgrade head
  python scripts/smoke_w17_auth_ws.py --offline
  python scripts/smoke_w17_auth_ws.py --auto-server
  python scripts/smoke_w17_auth_ws.py --base-url http://127.0.0.1:8000
"""
from __future__ import annotations

import argparse
import asyncio
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
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "packages" / "fengji_core"))
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "services"))


def _ensure_dev_jwt() -> None:
    os.environ.setdefault("FENGJI_AUTH_ALLOW_DEV_SECRET", "1")


def wait_for_health(base_url: str, timeout: float = 30.0) -> None:
    deadline = time.time() + timeout
    last_error: Exception | None = None
    while time.time() < deadline:
        try:
            with urlopen(f"{base_url.rstrip('/')}/api/v1/health", timeout=3) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            if data.get("status") == "ok":
                return
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            time.sleep(0.5)
    raise RuntimeError(f"API not ready at {base_url}; last_error={last_error}")


def start_uvicorn(port: int) -> tuple[subprocess.Popen[Any], str]:
    logs = ROOT / "runtime" / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    stdout = logs / "api_smoke_w17_stdout.log"
    stderr = logs / "api_smoke_w17_stderr.log"
    env = os.environ.copy()
    env.setdefault("FENGJI_AUTH_ALLOW_DEV_SECRET", "1")
    env["PYTHONPATH"] = "src;packages/fengji_core;services"
    proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "services.api.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
        ],
        cwd=str(ROOT),
        env=env,
        stdout=stdout.open("w", encoding="utf-8"),
        stderr=stderr.open("w", encoding="utf-8"),
        text=True,
    )
    return proc, f"http://127.0.0.1:{port}"


def _post_json(base_url: str, path: str, payload: dict, token: str = "") -> tuple[int, dict]:
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = Request(
        f"{base_url.rstrip('/')}{path}",
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    try:
        with urlopen(req, timeout=15) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        try:
            return exc.code, json.loads(body)
        except json.JSONDecodeError:
            return exc.code, {"detail": body}


def _get_json(base_url: str, path: str, token: str) -> dict:
    req = Request(
        f"{base_url.rstrip('/')}{path}",
        headers={"Authorization": f"Bearer {token}"},
        method="GET",
    )
    with urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode("utf-8"))


def auth_flow_http(base_url: str) -> dict[str, Any]:
    account = f"w17-smoke-{uuid.uuid4().hex[:8]}@test.local"
    password = "smoke-pass-12"

    status, body = _post_json(base_url, "/api/v1/auth/register", {"account": account, "password": password})
    if status == 503:
        return {"ok": False, "error": "auth storage unavailable (PG down? run alembic upgrade head)"}
    if status == 400 and "already exists" in str(body.get("detail", "")):
        status, body = _post_json(base_url, "/api/v1/auth/login", {"account": account, "password": password})
    if status != 200:
        return {"ok": False, "error": f"register/login failed: {status} {body}"}

    access = body["access_token"]
    me = _get_json(base_url, "/api/v1/auth/me", access)
    ref_status, ref = _post_json(base_url, "/api/v1/auth/refresh", {"refresh_token": body["refresh_token"]})
    if ref_status != 200:
        return {"ok": False, "error": f"/refresh failed: {ref_status}"}

    return {
        "ok": True,
        "account": account,
        "user": body["user"],
        "me_plan": me.get("plan"),
        "refresh_ok": bool(ref.get("access_token")),
        "access_token": ref.get("access_token") or access,
        "refresh_token": body["refresh_token"],
    }


async def ws_probe_http(base_url: str, access_token: str) -> str:
    import websockets

    ws_base = base_url.rstrip("/").replace("http://", "ws://").replace("https://", "wss://")
    url = f"{ws_base}/api/v1/ws/monitor?access_token={access_token}&interval_seconds=0.05"
    async with websockets.connect(url, open_timeout=10) as ws:
        raw = await asyncio.wait_for(ws.recv(), timeout=15)
        payload = json.loads(raw)
        return str(payload.get("type", ""))


def http_smoke(base_url: str, *, with_ws: bool = True) -> dict:
    _ensure_dev_jwt()
    auth = auth_flow_http(base_url)
    if not auth.get("ok"):
        return {"ok": False, "mode": "http", "base_url": base_url, **auth}

    result: dict[str, Any] = {
        "ok": True,
        "mode": "http",
        "base_url": base_url,
        "account": auth["account"],
        "me_plan": auth["me_plan"],
        "refresh_ok": auth["refresh_ok"],
    }

    if with_ws:
        token = str(auth.get("access_token") or "")
        mc_status, _mc = _post_json(
            base_url,
            "/api/v1/subscriptions/manual-confirm",
            {"plan": "pro"},
            token,
        )
        if mc_status == 200 and auth.get("refresh_token"):
            ref_status, ref = _post_json(
                base_url,
                "/api/v1/auth/refresh",
                {"refresh_token": auth["refresh_token"]},
            )
            if ref_status == 200:
                token = str(ref.get("access_token") or token)
        try:
            msg_type = asyncio.run(ws_probe_http(base_url, token))
        except Exception as exc:  # noqa: BLE001
            return {**result, "ok": False, "error": f"ws failed: {exc}"}
        if msg_type not in {"monitor.snapshot.v1", "monitor.heartbeat.v1", "monitor.delta.v1", "monitor.auth_error.v1"}:
            return {**result, "ok": False, "error": f"ws unexpected: {msg_type}"}
        if msg_type == "monitor.auth_error.v1":
            return {**result, "ok": False, "error": "ws auth rejected"}
        result["ws_first_message"] = msg_type

    return result


def offline_smoke() -> dict:
    _ensure_dev_jwt()
    from fastapi.testclient import TestClient
    from services.api import main

    account = f"w17-smoke-{uuid.uuid4().hex[:8]}@test.local"
    password = "smoke-pass-12"
    client = TestClient(main.app)

    reg = client.post("/api/v1/auth/register", json={"account": account, "password": password})
    if reg.status_code == 503:
        return {"ok": False, "mode": "offline", "error": "auth storage unavailable (PG down?)"}
    if reg.status_code == 400 and "already exists" in str(reg.json().get("detail", "")):
        reg = client.post("/api/v1/auth/login", json={"account": account, "password": password})
    if reg.status_code != 200:
        return {"ok": False, "mode": "offline", "error": f"register/login failed: {reg.status_code} {reg.text}"}

    body = reg.json()
    me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {body['access_token']}"})
    ref = client.post("/api/v1/auth/refresh", json={"refresh_token": body["refresh_token"]})
    if me.status_code != 200 or ref.status_code != 200:
        return {"ok": False, "mode": "offline", "error": "me or refresh failed"}

    from auth_service import create_access_token
    from services.api import main as api_main
    import tests.test_monitor_websocket as ws_test

    class _Monkey:
        def setattr(self, target, name, value):
            setattr(target, name, value)

    ws_test._patch_monitor_sources(_Monkey())

    async def ws_probe() -> str:
        user = body["user"]
        token = create_access_token(user_id=user["id"], account=user["account"], plan="pro")
        ws = ws_test.FakeWebSocket(disconnect_after_messages=1)
        await api_main.monitor_websocket(
            ws, user_id="", plan="free", access_token=token, interval_seconds=0.01,
        )
        return str(ws.messages[0].get("type", "")) if ws.messages else "ws_no_messages"

    msg_type = asyncio.run(ws_probe())
    if msg_type not in {"monitor.snapshot.v1", "monitor.heartbeat.v1", "monitor.delta.v1"}:
        return {"ok": False, "mode": "offline", "error": f"ws unexpected: {msg_type}"}

    return {
        "ok": True,
        "mode": "offline",
        "account": account,
        "me_plan": me.json().get("plan"),
        "ws_first_message": msg_type,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="W17 auth + WS smoke")
    parser.add_argument("--base-url", default="")
    parser.add_argument("--port", type=int, default=8031)
    parser.add_argument("--offline", action="store_true")
    parser.add_argument("--auto-server", action="store_true", help="Start temporary uvicorn then run HTTP+WS smoke")
    args = parser.parse_args()

    proc: subprocess.Popen[Any] | None = None
    try:
        if args.offline:
            result = offline_smoke()
        else:
            base_url = args.base_url.rstrip("/")
            if args.auto_server or not base_url:
                proc, base_url = start_uvicorn(args.port)
                wait_for_health(base_url)
            result = http_smoke(base_url)
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
