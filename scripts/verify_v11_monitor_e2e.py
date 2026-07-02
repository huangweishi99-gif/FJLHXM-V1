#!/usr/bin/env python3
"""V1.1 monitor E2E: domestic + overseas paper_state + payment-config + monitor.html markers."""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any
from urllib.error import HTTPError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]


@dataclass
class Check:
    id: str
    ok: bool
    detail: dict[str, Any] = field(default_factory=dict)
    error: str = ""


def _get(
    url: str,
    *,
    timeout: float = 20.0,
    token: str | None = None,
) -> tuple[int, dict[str, Any] | str]:
    headers: dict[str, str] = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = Request(url, method="GET", headers=headers)
    try:
        with urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            if body.strip().startswith("{"):
                return resp.status, json.loads(body)
            return resp.status, body
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        try:
            return exc.code, json.loads(body)
        except json.JSONDecodeError:
            return exc.code, {"detail": body[:500]}


def _post_json(base_url: str, path: str, payload: dict, *, token: str = "") -> tuple[int, dict[str, Any]]:
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


def mint_pro_access_token(base_url: str) -> tuple[str | None, str]:
    """Register ephemeral user and manual-confirm pro; returns (token, auth_mode detail)."""
    account = f"v11-e2e-{uuid.uuid4().hex[:10]}@test.local"
    password = "v11-e2e-pass-12"
    status, reg = _post_json(base_url, "/api/v1/auth/register", {"account": account, "password": password})
    if status != 200 or not reg.get("access_token"):
        return None, f"register_failed status={status}"

    token = str(reg["access_token"])
    status, paid = _post_json(base_url, "/api/v1/subscriptions/manual-confirm", {"plan": "pro"}, token=token)
    if status != 200:
        return None, f"manual_confirm_failed status={status} detail={paid.get('detail', paid)}"

    refreshed = str(paid.get("access_token") or token)
    plan = (paid.get("user") or {}).get("plan")
    if plan != "pro":
        return None, f"unexpected_plan={plan}"
    return refreshed, f"mint_pro account={account}"


def resolve_pro_token(base_url: str, *, pro_token: str, mint_pro_token: bool) -> tuple[str | None, str]:
    explicit = str(pro_token or os.getenv("FENGJI_V11_E2E_PRO_TOKEN", "")).strip()
    if explicit:
        return explicit, "pro_token_arg"
    if mint_pro_token:
        return mint_pro_access_token(base_url)
    return None, "anonymous"


def run_checks(base: str, *, pause_sec: float = 2.0, pro_token: str | None = None) -> list[Check]:
    base = base.rstrip("/")
    checks: list[Check] = []

    status, data = _get(f"{base}/api/v1/health")
    checks.append(
        Check(
            id="health",
            ok=status == 200 and isinstance(data, dict) and data.get("status") == "ok",
            detail={"status": status, "version": data.get("version") if isinstance(data, dict) else None},
        )
    )
    time.sleep(pause_sec)

    status, data = _get(f"{base}/api/v1/monitor/domestic/latest-opens", token=pro_token)
    ok = status == 200 and isinstance(data, dict) and data.get("source") == "paper_state"
    checks.append(
        Check(
            id="domestic_opens",
            ok=ok,
            detail={
                "status": status,
                "count": len((data or {}).get("positions") or []) if isinstance(data, dict) else 0,
                "source": (data or {}).get("source") if isinstance(data, dict) else None,
                "authenticated": bool(pro_token),
            },
            error="" if ok else f"status={status}",
        )
    )
    time.sleep(pause_sec)

    status, data = _get(f"{base}/api/v1/monitor/overseas/latest-opens", token=pro_token)
    ok = status == 200 and isinstance(data, dict) and data.get("source") == "paper_state"
    checks.append(
        Check(
            id="overseas_opens",
            ok=ok,
            detail={
                "status": status,
                "count": len((data or {}).get("positions") or []) if isinstance(data, dict) else 0,
                "source": (data or {}).get("source") if isinstance(data, dict) else None,
                "authenticated": bool(pro_token),
            },
            error="" if ok else f"status={status}",
        )
    )
    time.sleep(pause_sec)

    status, data = _get(f"{base}/api/v1/subscriptions/payment-config")
    ok = status == 200 and isinstance(data, dict) and "confirm_button_mode" in data
    checks.append(
        Check(
            id="payment_config",
            ok=ok,
            detail={"status": status, "mode": (data or {}).get("confirm_button_mode") if isinstance(data, dict) else None},
            error="" if ok else f"status={status}",
        )
    )
    time.sleep(pause_sec)

    status, html = _get(f"{base}/web/monitor.html")
    markers = ["monitor/overseas/latest-opens", "虚拟币", "monitorPollFetch"]
    missing = [m for m in markers if m not in str(html)]
    checks.append(
        Check(
            id="monitor_html",
            ok=status == 200 and not missing,
            detail={"status": status, "missing": missing},
            error="" if not missing else f"missing={missing}",
        )
    )

    return checks


def main() -> int:
    parser = argparse.ArgumentParser(description="V1.1 monitor E2E verification")
    parser.add_argument("--base-url", default="")
    parser.add_argument("--ssh-tunnel", default="", help="e.g. domestic-quant")
    parser.add_argument("--local-port", type=int, default=8043)
    parser.add_argument("--pause-sec", type=float, default=2.5, help="Delay between API calls (avoid 429)")
    parser.add_argument(
        "--pro-token",
        default="",
        help="Bearer access token with pro plan for monitor opens (or env FENGJI_V11_E2E_PRO_TOKEN)",
    )
    parser.add_argument(
        "--mint-pro-token",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Register ephemeral user + manual-confirm pro when --pro-token unset (default: on)",
    )
    args = parser.parse_args()

    tunnel: subprocess.Popen[Any] | None = None
    base = args.base_url.rstrip("/")
    try:
        if args.ssh_tunnel:
            base = f"http://127.0.0.1:{args.local_port}"
            tunnel = subprocess.Popen(
                [
                    "ssh",
                    "-o",
                    "BatchMode=yes",
                    "-N",
                    "-L",
                    f"{args.local_port}:127.0.0.1:8000",
                    args.ssh_tunnel,
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            time.sleep(4.0)
        if not base:
            raise SystemExit("provide --base-url or --ssh-tunnel")

        pro_token, auth_mode = resolve_pro_token(base, pro_token=args.pro_token, mint_pro_token=args.mint_pro_token)
        if args.mint_pro_token and not args.pro_token and pro_token is None:
            raise SystemExit(f"failed to mint pro token: {auth_mode}")

        checks = run_checks(base, pause_sec=args.pause_sec, pro_token=pro_token)
        ok = all(c.ok for c in checks)
        report = {
            "ok": ok,
            "base_url": base,
            "auth_mode": auth_mode,
            "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "checks": [asdict(c) for c in checks],
        }
        out = ROOT / "runtime" / "web_validation" / "v11_monitor_e2e.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(report, ensure_ascii=False, indent=2))
        print(f"saved {out}")
        return 0 if ok else 1
    finally:
        if tunnel is not None:
            tunnel.terminate()
            try:
                tunnel.wait(timeout=3)
            except subprocess.TimeoutExpired:
                tunnel.kill()


if __name__ == "__main__":
    raise SystemExit(main())
