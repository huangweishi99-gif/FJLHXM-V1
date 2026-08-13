#!/usr/bin/env python3
"""Stress-test personal WeChat manual_confirm: N runs per plan via API.

Usage:
  python scripts/stress_subscription_manual_confirm.py --auto-server
  python scripts/stress_subscription_manual_confirm.py --base-url http://127.0.0.1:8000 --standard 20 --pro 20
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

from smoke_w17_auth_ws import start_uvicorn, wait_for_health  # noqa: E402


def _ensure_env() -> None:
    os.environ.setdefault("FENGJI_AUTH_ALLOW_DEV_SECRET", "1")
    os.environ.setdefault("FENGJI_ALLOW_MANUAL_SUBSCRIPTION_CONFIRM", "1")


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
        with urlopen(req, timeout=20) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        try:
            return exc.code, json.loads(body)
        except json.JSONDecodeError:
            return exc.code, {"detail": body}


def _get_json(base_url: str, path: str, token: str = "") -> tuple[int, dict]:
    headers: dict[str, str] = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = Request(f"{base_url.rstrip('/')}{path}", headers=headers, method="GET")
    try:
        with urlopen(req, timeout=20) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        try:
            return exc.code, json.loads(body)
        except json.JSONDecodeError:
            return exc.code, {"detail": body}


def _run_one(base_url: str, plan: str, run_idx: int) -> dict[str, Any]:
    account = f"stress-{plan}-{run_idx}-{uuid.uuid4().hex[:8]}@test.local"
    password = "stress-pass-12"
    errors: list[str] = []

    st, reg = _post_json(base_url, "/api/v1/auth/register", {"account": account, "password": password})
    if st != 200 or not reg.get("access_token"):
        return {"ok": False, "plan": plan, "run": run_idx, "account": account, "errors": [f"register {st}: {reg}"]}

    token = str(reg["access_token"])
    if reg.get("user", {}).get("plan") != "free":
        errors.append(f"register plan expected free got {reg.get('user', {}).get('plan')}")

    st, cfg = _get_json(base_url, "/api/v1/subscriptions/payment-config")
    if st != 200:
        errors.append(f"payment-config {st}")
    else:
        if cfg.get("confirm_button_mode") != "manual_confirm":
            errors.append(f"confirm_button_mode={cfg.get('confirm_button_mode')}")
        price = (cfg.get("pricing") or {}).get(plan, {})
        expected_yuan = 99 if plan == "standard" else 299
        if price.get("amount_yuan") != expected_yuan:
            errors.append(f"pricing.{plan}.amount_yuan={price.get('amount_yuan')}")

    st, paid = _post_json(base_url, "/api/v1/subscriptions/manual-confirm", {"plan": plan}, token=token)
    if st != 200:
        errors.append(f"manual-confirm {st}: {paid.get('detail', paid)}")
    else:
        user_plan = paid.get("user", {}).get("plan")
        if user_plan != plan:
            errors.append(f"paid user.plan={user_plan}")
        order = paid.get("subscription_order") or {}
        if order.get("channel") != "personal_wechat_qr":
            errors.append(f"order.channel={order.get('channel')}")
        meta = order.get("metadata") or {}
        if meta.get("amount_yuan") != (99 if plan == "standard" else 299):
            errors.append(f"order.metadata.amount_yuan={meta.get('amount_yuan')}")
        if not paid.get("access_token"):
            errors.append("missing refreshed access_token")

    st, me = _get_json(base_url, "/api/v1/auth/me", token=str(paid.get("access_token") or token))
    if st != 200 or me.get("plan") != plan:
        errors.append(f"auth/me plan={me.get('plan')} status={st}")

    st2, dup = _post_json(
        base_url,
        "/api/v1/subscriptions/manual-confirm",
        {"plan": plan},
        token=str(paid.get("access_token") or token),
    )
    if st2 != 400:
        errors.append(f"duplicate confirm expected 400 got {st2}: {dup.get('detail', dup)}")

    if plan == "pro":
        st3, down = _post_json(
            base_url,
            "/api/v1/subscriptions/manual-confirm",
            {"plan": "standard"},
            token=str(paid.get("access_token") or token),
        )
        if st3 != 400 or "downgrade" not in str(down.get("detail", "")).lower():
            errors.append(f"pro->standard downgrade expected 400 got {st3}: {down.get('detail', down)}")

    return {
        "ok": not errors,
        "plan": plan,
        "run": run_idx,
        "account": account,
        "order_id": (paid.get("subscription_order") or {}).get("id") if st == 200 else None,
        "errors": errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Stress manual_confirm subscription flow")
    parser.add_argument("--base-url", default="")
    parser.add_argument("--port", type=int, default=8035)
    parser.add_argument("--auto-server", action="store_true")
    parser.add_argument("--standard", type=int, default=20)
    parser.add_argument("--pro", type=int, default=20)
    args = parser.parse_args()

    _ensure_env()
    proc: subprocess.Popen[Any] | None = None
    base_url = args.base_url.rstrip("/")
    results: list[dict[str, Any]] = []

    try:
        if args.auto_server or not base_url:
            proc, base_url = start_uvicorn(args.port)
            env_copy = os.environ.copy()
            env_copy["FENGJI_ALLOW_MANUAL_SUBSCRIPTION_CONFIRM"] = "1"
            wait_for_health(base_url)

        for i in range(1, args.standard + 1):
            results.append(_run_one(base_url, "standard", i))
        for i in range(1, args.pro + 1):
            results.append(_run_one(base_url, "pro", i))

        failed = [r for r in results if not r.get("ok")]
        payload = {
            "ok": len(failed) == 0,
            "base_url": base_url,
            "total": len(results),
            "passed": len(results) - len(failed),
            "failed": len(failed),
            "failures": failed[:10],
        }
        out = ROOT / "runtime" / "web_validation" / "stress_subscription_manual_confirm.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps({"results": results, "summary": payload}, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0 if payload["ok"] else 1
    finally:
        if proc is not None:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()


if __name__ == "__main__":
    raise SystemExit(main())
