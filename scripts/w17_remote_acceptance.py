#!/usr/bin/env python3
"""W17-prod remote acceptance checklist (health / auth / WS / web / admin).

Usage:
  python scripts/w17_remote_acceptance.py --auto-server
  python scripts/w17_remote_acceptance.py --base-url http://127.0.0.1:8000
  python scripts/w17_remote_acceptance.py --ssh-tunnel domestic-quant --local-port 8040
  python scripts/w17_remote_acceptance.py --preflight-only
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any
from urllib.error import HTTPError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from smoke_w17_auth_ws import (  # noqa: E402
    auth_flow_http,
    http_smoke,
    start_uvicorn,
    wait_for_health,
)


@dataclass
class AcceptanceCheck:
    id: str
    name: str
    ok: bool
    required: bool = True
    detail: dict[str, Any] = field(default_factory=dict)
    error: str = ""


def _get_status(url: str, *, headers: dict[str, str] | None = None, timeout: float = 12.0) -> tuple[int, str]:
    req = Request(url, headers=headers or {}, method="GET")
    try:
        with urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read().decode("utf-8", errors="replace")
    except HTTPError as exc:
        return exc.code, exc.read().decode("utf-8", errors="replace")


def preflight_checks(*, ssh_host: str = "") -> list[AcceptanceCheck]:
    checks: list[AcceptanceCheck] = []

    manifest = ROOT / "scripts" / "fengji_api_deploy_manifest.txt"
    checks.append(
        AcceptanceCheck(
            id="manifest",
            name="部署清单存在",
            ok=manifest.is_file(),
            detail={"path": str(manifest)},
            error="" if manifest.is_file() else "missing fengji_api_deploy_manifest.txt",
        )
    )

    deploy_ps1 = ROOT / "scripts" / "sync_deploy_fengji_api.ps1"
    checks.append(
        AcceptanceCheck(
            id="deploy_script",
            name="sync_deploy_fengji_api.ps1 存在",
            ok=deploy_ps1.is_file(),
            detail={"path": str(deploy_ps1)},
        )
    )

    if ssh_host:
        try:
            proc = subprocess.run(
                ["ssh", "-o", "BatchMode=yes", ssh_host, "echo", "FENGJI_SSH_OK"],
                capture_output=True,
                text=True,
                timeout=15,
                check=False,
            )
            ok = proc.returncode == 0 and "FENGJI_SSH_OK" in (proc.stdout or "")
            checks.append(
                AcceptanceCheck(
                    id="ssh_batch",
                    name=f"SSH BatchMode 连通 ({ssh_host})",
                    ok=ok,
                    required=False,
                    detail={"returncode": proc.returncode},
                    error="" if ok else (proc.stderr or proc.stdout or "ssh failed").strip()[:200],
                )
            )
        except Exception as exc:  # noqa: BLE001
            checks.append(
                AcceptanceCheck(
                    id="ssh_batch",
                    name=f"SSH BatchMode 连通 ({ssh_host})",
                    ok=False,
                    required=False,
                    error=str(exc),
                )
            )

    return checks


def run_acceptance(
    base_url: str,
    *,
    admin_token: str = "",
    check_web: bool = True,
    with_ws: bool = True,
) -> dict[str, Any]:
    base = base_url.rstrip("/")
    checks: list[AcceptanceCheck] = []

    # 1) Health
    try:
        status, body = _get_status(f"{base}/api/v1/health")
        payload = json.loads(body) if body.strip().startswith("{") else {}
        ok = status == 200 and payload.get("status") == "ok"
        checks.append(
            AcceptanceCheck(
                id="health",
                name="GET /api/v1/health",
                ok=ok,
                detail={"status": status, "version": payload.get("version")},
                error="" if ok else f"status={status} body={body[:120]}",
            )
        )
    except Exception as exc:  # noqa: BLE001
        checks.append(AcceptanceCheck(id="health", name="GET /api/v1/health", ok=False, error=str(exc)))

    # 2) Auth register/login/me/refresh
    auth = auth_flow_http(base)
    checks.append(
        AcceptanceCheck(
            id="auth_flow",
            name="Auth 注册/登录/me/refresh",
            ok=bool(auth.get("ok")),
            detail={
                "me_plan": auth.get("me_plan"),
                "refresh_ok": auth.get("refresh_ok"),
            },
            error=str(auth.get("error") or ""),
        )
    )

    access_token = str(auth.get("access_token") or "")

    # 3) WS monitor (JWT pro)
    if with_ws and auth.get("ok"):
        ws_result = http_smoke(base, with_ws=True)
        ws_ok = bool(ws_result.get("ok")) and bool(ws_result.get("ws_first_message"))
        checks.append(
            AcceptanceCheck(
                id="ws_monitor",
                name="监测 WS 首帧 (JWT pro)",
                ok=ws_ok,
                detail={"first_message": ws_result.get("ws_first_message")},
                error=str(ws_result.get("error") or ""),
            )
        )
    elif with_ws:
        checks.append(
            AcceptanceCheck(
                id="ws_monitor",
                name="监测 WS 首帧 (JWT pro)",
                ok=False,
                error="skipped: auth failed",
            )
        )

    # 4) WS stats (optional telemetry)
    try:
        status, body = _get_status(f"{base}/api/v1/monitor/ws/stats")
        payload = json.loads(body) if body.strip().startswith("{") else {}
        ok = status == 200
        checks.append(
            AcceptanceCheck(
                id="ws_stats",
                name="GET /api/v1/monitor/ws/stats",
                ok=ok,
                required=False,
                detail={"active_total": payload.get("active_total")},
                error="" if ok else f"status={status}",
            )
        )
    except Exception as exc:  # noqa: BLE001
        checks.append(
            AcceptanceCheck(
                id="ws_stats",
                name="GET /api/v1/monitor/ws/stats",
                ok=False,
                required=False,
                error=str(exc),
            )
        )

    # 5) Domestic monitor read-only
    try:
        status, body = _get_status(f"{base}/api/v1/monitor/domestic/latest-opens")
        payload = json.loads(body) if body.strip().startswith("{") else {}
        ok = status == 200 and "positions" in payload
        checks.append(
            AcceptanceCheck(
                id="monitor_domestic",
                name="GET /api/v1/monitor/domestic/latest-opens",
                ok=ok,
                required=False,
                detail={"source": payload.get("source"), "count": len(payload.get("positions") or [])},
                error="" if ok else f"status={status}",
            )
        )
    except Exception as exc:  # noqa: BLE001
        checks.append(
            AcceptanceCheck(
                id="monitor_domestic",
                name="GET /api/v1/monitor/domestic/latest-opens",
                ok=False,
                required=False,
                error=str(exc),
            )
        )

    # 6) Admin unauthenticated -> 401
    try:
        status, _ = _get_status(f"{base}/api/v1/admin/overview")
        ok = status == 401
        checks.append(
            AcceptanceCheck(
                id="admin_unauth",
                name="Admin 未鉴权返回 401",
                ok=ok,
                detail={"status": status},
                error="" if ok else f"expected 401 got {status}",
            )
        )
    except Exception as exc:  # noqa: BLE001
        checks.append(AcceptanceCheck(id="admin_unauth", name="Admin 未鉴权返回 401", ok=False, error=str(exc)))

    # 7) Admin with token (optional)
    token = (admin_token or os.environ.get("FENGJI_ADMIN_TOKEN") or "").strip()
    if token:
        try:
            status, body = _get_status(
                f"{base}/api/v1/admin/overview",
                headers={"Authorization": f"Bearer {token}"},
            )
            payload = json.loads(body) if body.strip().startswith("{") else {}
            ok = status == 200 and "auth_users" in payload
            checks.append(
                AcceptanceCheck(
                    id="admin_overview",
                    name="Admin overview 只读概览",
                    ok=ok,
                    required=False,
                    detail={"auth_users": payload.get("auth_users")},
                    error="" if ok else f"status={status}",
                )
            )
        except Exception as exc:  # noqa: BLE001
            checks.append(
                AcceptanceCheck(
                    id="admin_overview",
                    name="Admin overview 只读概览",
                    ok=False,
                    required=False,
                    error=str(exc),
                )
            )

    # 8) Feature gate (free user cannot use TOTAL)
    if auth.get("ok") and access_token:
        status, body = _post_json_with_token(
            base,
            "/api/v1/backtests",
            {
                "market": "A_STOCK",
                "symbol": "000021",
                "strategy_id": "TOTAL",
                "years": 1,
            },
            access_token,
        )
        ok = status in {403, 422}
        checks.append(
            AcceptanceCheck(
                id="feature_gate_total",
                name="Feature Gate：免费档拒绝 TOTAL 回测",
                ok=ok,
                required=False,
                detail={"status": status, "detail": body.get("detail") if isinstance(body, dict) else body},
                error="" if ok else f"expected 403/422 got {status}",
            )
        )

    # 9) Manual subscription confirm (only when server allows)
    if auth.get("ok") and access_token and os.environ.get("FENGJI_ALLOW_MANUAL_SUBSCRIPTION_CONFIRM") == "1":
        req = Request(
            f"{base}/api/v1/subscriptions/manual-confirm",
            data=json.dumps({"plan": "standard"}).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {access_token}",
            },
            method="POST",
        )
        try:
            with urlopen(req, timeout=15) as resp:
                status = resp.status
                sub = json.loads(resp.read().decode("utf-8"))
        except HTTPError as exc:
            status = exc.code
            sub = json.loads(exc.read().decode("utf-8", errors="replace") or "{}")
        ok = status == 200 and sub.get("user", {}).get("plan") == "standard"
        checks.append(
            AcceptanceCheck(
                id="subscription_manual_confirm",
                name="订阅 manual-confirm (dev/local)",
                ok=ok,
                required=False,
                detail={"status": status, "plan": sub.get("user", {}).get("plan")},
                error="" if ok else f"status={status}",
            )
        )

    # 10) Static web (when -SyncWeb deployed)
    if check_web:
        web_pages = [
            ("web_index", "GET /web/index.html", "/web/index.html", ["navMount", "FengJiApp"]),
            ("web_strategies", "GET /web/strategies.html", "/web/strategies.html", ["strategy_animations.js"]),
            ("web_login", "GET /web/login.html", "/web/login.html", ["authForm", "authAccount"]),
        ]
        for cid, cname, path, markers in web_pages:
            try:
                status, html = _get_status(f"{base}{path}")
                missing = [m for m in markers if m not in html]
                ok = status == 200 and not missing
                checks.append(
                    AcceptanceCheck(
                        id=cid,
                        name=cname,
                        ok=ok,
                        detail={"status": status, "missing": missing},
                        error="" if ok else f"status={status} missing={missing}",
                    )
                )
            except Exception as exc:  # noqa: BLE001
                checks.append(AcceptanceCheck(id=cid, name=cname, ok=False, error=str(exc)))

    required_ok = all(c.ok for c in checks if c.required)
    optional_total = sum(1 for c in checks if not c.required)
    optional_ok = sum(1 for c in checks if not c.required and c.ok)

    return {
        "ok": required_ok,
        "base_url": base,
        "summary": {
            "required_passed": sum(1 for c in checks if c.required and c.ok),
            "required_total": sum(1 for c in checks if c.required),
            "optional_passed": optional_ok,
            "optional_total": optional_total,
        },
        "checks": [asdict(c) for c in checks],
    }


def _post_json_with_token(base_url: str, path: str, payload: dict, token: str) -> tuple[int, dict]:
    req = Request(
        f"{base_url.rstrip('/')}{path}",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
        },
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


def _load_env_file(path: Path) -> None:
    if not path.is_file():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


def main() -> int:
    parser = argparse.ArgumentParser(description="W17 remote acceptance checklist")
    parser.add_argument("--base-url", default="")
    parser.add_argument("--port", type=int, default=8041)
    parser.add_argument("--auto-server", action="store_true")
    parser.add_argument("--ssh-tunnel", default="", help="SSH alias, e.g. domestic-quant")
    parser.add_argument("--local-port", type=int, default=8040)
    parser.add_argument("--wait-seconds", type=float, default=5.0)
    parser.add_argument("--admin-token", default="")
    parser.add_argument("--no-web", action="store_true", help="Skip static /web/* checks")
    parser.add_argument("--no-ws", action="store_true")
    parser.add_argument("--preflight-only", action="store_true")
    parser.add_argument("--preflight-ssh", default="domestic-quant")
    args = parser.parse_args()

    os.environ.setdefault("FENGJI_AUTH_ALLOW_DEV_SECRET", "1")
    _load_env_file(ROOT / "runtime" / "secrets" / "fengji_local.env")

    if args.preflight_only:
        checks = preflight_checks(ssh_host=args.preflight_ssh)
        out = {
            "ok": all(c.ok for c in checks if c.required),
            "mode": "preflight",
            "checks": [asdict(c) for c in checks],
        }
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return 0 if out["ok"] else 1

    tunnel_proc: subprocess.Popen[Any] | None = None
    api_proc: subprocess.Popen[Any] | None = None
    result: dict[str, Any] = {"ok": False}

    try:
        base_url = args.base_url.rstrip("/")
        if args.ssh_tunnel:
            base_url = f"http://127.0.0.1:{args.local_port}"
            tunnel_proc = subprocess.Popen(
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
            time.sleep(args.wait_seconds)
            pre = preflight_checks(ssh_host=args.ssh_tunnel)
            wait_for_health(base_url, timeout=25.0)
        elif args.auto_server or not base_url:
            api_proc, base_url = start_uvicorn(args.port)
            wait_for_health(base_url)
            pre = preflight_checks()
        else:
            wait_for_health(base_url, timeout=15.0)
            pre = preflight_checks(ssh_host=args.preflight_ssh if args.ssh_tunnel else "")

        acceptance = run_acceptance(
            base_url,
            admin_token=args.admin_token,
            check_web=not args.no_web,
            with_ws=not args.no_ws,
        )
        result = {
            "ok": acceptance["ok"] and all(c.ok for c in pre if c.required),
            "mode": "acceptance",
            "preflight": [asdict(c) for c in pre],
            **acceptance,
        }
    except Exception as exc:  # noqa: BLE001
        result = {"ok": False, "error": str(exc)}
    finally:
        if tunnel_proc is not None:
            tunnel_proc.terminate()
            try:
                tunnel_proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                tunnel_proc.kill()
        if api_proc is not None:
            api_proc.terminate()
            try:
                api_proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                api_proc.kill()

    out_path = ROOT / "runtime" / "web_validation" / "w17_remote_acceptance.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    result["report_path"] = str(out_path)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
