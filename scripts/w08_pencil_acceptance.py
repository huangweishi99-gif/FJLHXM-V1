#!/usr/bin/env python3
"""W08 / Wave5 P4: FJLHXM 9-screen file-level + HTTP acceptance (+ Pencil canvas optional).

File-level: regenerate/validate FJLHXM-UI.pen via finalize_fjlhxm_ui_pen.py.
HTTP: all 9 Web screens via API static mount or --base-url.
Canvas: Pencil MCP requires .pen open in editor; use --web-screenshots for Playwright Web baseline.

Usage:
  python scripts/w08_pencil_acceptance.py --preflight-only
  python scripts/w08_pencil_acceptance.py --auto-server --port 8036
  python scripts/w08_pencil_acceptance.py --auto-server --web-screenshots
  python scripts/w08_pencil_acceptance.py --base-url http://127.0.0.1:8000
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
PEN = ROOT / "FJLHXM-UI.pen"
FINALIZE = ROOT / "scripts" / "finalize_fjlhxm_ui_pen.py"
REPORT = ROOT / "runtime" / "web_validation" / "w08_pencil_acceptance.json"

PEN_EXPECTED = [
    "01 · Dashboard",
    "02 · Backtest",
    "03 · Monitor",
    "04 · Strategies",
    "05 · Pricing",
    "06 · Symbol Chart",
    "07 · Auth",
    "08 · Community",
    "09 · Payment",
]

# 各定稿帧须含的关键文案（与 Web / build_fjlhxm_ui_pen.py 一致）
PEN_FRAME_MARKERS: list[tuple[str, list[str]]] = [
    ("01 · Dashboard", ["加载持仓", "选择左侧品种", "净盈亏", "刷新"]),
    ("02 · Backtest", ["读取样本概览", "搜索品种并加载回测", "同桶样本", "就绪"]),
    ("03 · Monitor", ["暂无模拟持仓", "0 / 50 自选", "WS 连接中"]),
    ("04 · Strategies", ["Lottie/SVG", "10s 循环", "峰极总定式"]),
    ("05 · Pricing", ["注册后自动开启 7 天试用", "Phase 4"]),
    ("06 · Symbol Chart", ["返回模拟监测", "守护止损"]),
    ("07 · Auth", ["登录后使用回测", "JWT 登录"]),
    ("08 · Community", ["加入峰极量化交流群", "官方 QQ 交流群"]),
    ("09 · Payment", ["请确认订阅档位后", "微信订阅收款"]),
]

WEB_SCREENS: list[tuple[str, str, str, list[str]]] = [
    ("web_01_dashboard", "01 Dashboard", "/web/index.html", ["navMount", "FengJiApp"]),
    ("web_02_backtest", "02 Backtest", "/web/backtest.html", ["loadBtn", "chartPanel"]),
    ("web_03_monitor", "03 Monitor", "/web/monitor.html", ["watchTable", "symbolPick", "symbolSearch", "refreshMeta"]),
    ("web_04_strategies", "04 Strategies", "/web/strategies.html", ["strategy_animations.js"]),
    ("web_05_pricing", "05 Pricing", "/web/pricing.html", ["pricingGrid", "PRICING_TIERS"]),
    ("web_06_symbol", "06 Symbol Chart", "/web/symbol.html", ["chartPanel", "pageSymbol"]),
    ("web_07_auth", "07 Auth", "/web/login.html", ["authForm", "authAccount"]),
    ("web_08_community", "08 Community", "/web/community.html", ["qq-group", "community"]),
    ("web_09_payment_std", "09 Payment standard", "/web/payment.html?pay=standard", ["payConfirmBtn", "wechat-pay"]),
    ("web_09_payment_pro", "09 Payment pro", "/web/payment.html?pay=pro", ["payConfirmBtn", "wechat-pay"]),
]

JS_CHECKS = [
    ROOT / "web" / "js" / "app.js",
    ROOT / "web" / "js" / "config.js",
    ROOT / "web" / "js" / "chart.js",
    ROOT / "web" / "js" / "monitor-chart.js",
]

WEB_SCREENSHOTS: list[tuple[str, str]] = [
    ("01_dashboard", "/web/index.html"),
    ("02_backtest", "/web/backtest.html"),
    ("03_monitor", "/web/monitor.html"),
    ("04_strategies", "/web/strategies.html"),
    ("05_pricing", "/web/pricing.html"),
    ("06_symbol", "/web/symbol.html?symbol=RB&market=FUTURES"),
    ("07_auth", "/web/login.html"),
    ("08_community", "/web/community.html"),
    ("09_payment", "/web/payment.html?pay=standard"),
]

SCREENSHOT_DIR = ROOT / "runtime" / "web_validation" / "p4_web_screenshots"
PEN_SCREENSHOT_DIR = ROOT / "runtime" / "web_validation" / "p4_pen_screenshots"
PEN_CANVAS_REPORT = ROOT / "runtime" / "web_validation" / "p4_canvas_acceptance.json"
PEN_CANVAS_MIN_FILES = 9
PEN_CANVAS_MIN_BYTES = 5000

PY_CHECKS = [
    ROOT / "scripts" / "build_fjlhxm_ui_pen.py",
    ROOT / "scripts" / "finalize_fjlhxm_ui_pen.py",
]


@dataclass
class Check:
    id: str
    name: str
    ok: bool
    required: bool = True
    detail: dict[str, Any] | None = None
    error: str = ""


def _get_html(base: str, path: str) -> tuple[int, str]:
    req = Request(f"{base.rstrip('/')}{path}", method="GET")
    with urlopen(req, timeout=15) as resp:
        return resp.status, resp.read().decode("utf-8", errors="replace")


def check_pen_finalize(regenerate: bool) -> Check:
    cmd = [sys.executable, str(FINALIZE)]
    if not regenerate:
        if not PEN.exists():
            return Check("pen_file", "FJLHXM-UI.pen exists", False, error="missing pen file")
        try:
            data = json.loads(PEN.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            return Check("pen_file", "FJLHXM-UI.pen JSON", False, error=str(exc))
        names = [str(c.get("name", "")) for c in data.get("children", [])]
        glass = [n for n in names if "Glass Gold" in n or "定稿" in n]
        missing = [k for k in PEN_EXPECTED if not any(k in n for n in glass)]
        ok = not missing
        return Check(
            "pen_frames",
            "FJLHXM-UI.pen 9-screen frames",
            ok,
            detail={"frames": len(glass), "missing": missing},
            error="" if ok else f"missing frames: {missing}",
        )
    proc = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True, check=False)
    ok = proc.returncode == 0 and "OK · FJLHXM-UI.pen finalized" in proc.stdout
    return Check(
        "pen_finalize",
        "finalize_fjlhxm_ui_pen.py rebuild",
        ok,
        detail={"returncode": proc.returncode},
        error="" if ok else (proc.stderr or proc.stdout)[-500:],
    )


def check_static_separation() -> list[Check]:
    checks: list[Check] = []
    community = (ROOT / "web" / "community.html").read_text(encoding="utf-8")
    payment = (ROOT / "web" / "payment.html").read_text(encoding="utf-8")
    login = (ROOT / "web" / "login.html").read_text(encoding="utf-8")
    config = (ROOT / "web" / "js" / "config.js").read_text(encoding="utf-8")

    checks.append(
        Check(
            "community_no_pay",
            "community.html 无 ?pay= / 微信收款",
            "wechat-pay" not in community and "community.html?pay" not in community,
            error="" if "wechat-pay" not in community and "community.html?pay" not in community else "community must not host payment QR",
        )
    )
    checks.append(
        Check(
            "payment_wechat",
            "payment.html 含微信收款码",
            "wechat-pay.png" in payment and "confirmPaidSubscription" in payment,
        )
    )
    checks.append(
        Check(
            "login_no_tier_select",
            "login.html 无订阅档位选择",
            "PRICING_TIERS" not in login and "payment.html?pay=" not in login,
        )
    )
    checks.append(
        Check(
            "config_pay_routes",
            "config.js 三档入口",
            "payment.html?pay=standard" in config
            and "payment.html?pay=pro" in config
            and "intent=free" in config,
        )
    )
    return checks


def check_js_syntax() -> Check:
    missing = [str(p) for p in JS_CHECKS if not p.exists()]
    if missing:
        return Check("js_syntax", "Web JS syntax", False, error=f"missing: {missing}")
    for path in JS_CHECKS:
        proc = subprocess.run(
            ["node", "--check", str(path)],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            check=False,
        )
        if proc.returncode != 0:
            return Check(
                "js_syntax",
                "Web JS syntax",
                False,
                error=f"{path.name}: {proc.stderr or proc.stdout}",
            )
    return Check("js_syntax", "Web JS syntax", True, detail={"files": len(JS_CHECKS)})


def check_py_build_scripts() -> Check:
    for path in PY_CHECKS:
        proc = subprocess.run(
            [sys.executable, "-m", "py_compile", str(path)],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            check=False,
        )
        if proc.returncode != 0:
            return Check("py_build", "Pencil build scripts compile", False, error=proc.stderr)
    return Check("py_build", "Pencil build scripts compile", True)


def check_pen_json_layout() -> Check:
    if not PEN.exists():
        return Check("pen_json_layout", "Pencil JSON 9 屏布局", False, error="missing pen")
    data = json.loads(PEN.read_text(encoding="utf-8"))
    frames = [
        c
        for c in data.get("children", [])
        if "Glass Gold" in str(c.get("name", "")) and "定稿" in str(c.get("name", "")) and "审阅" not in str(c.get("name", ""))
    ]
    missing = [k for k in PEN_EXPECTED if not any(k in str(f.get("name", "")) for f in frames)]
    sizes = [
        {"name": f.get("name"), "width": f.get("width"), "height": f.get("height")}
        for f in frames
    ]
    ok = len(frames) >= 9 and not missing
    return Check(
        "pen_json_layout",
        "Pencil JSON 9 屏布局",
        ok,
        required=False,
        detail={"frame_count": len(frames), "frames": sizes, "missing": missing},
        error="" if ok else f"missing={missing}",
    )


def _iter_text_content(node: Any) -> list[str]:
    out: list[str] = []
    if isinstance(node, dict):
        if node.get("type") == "text" and isinstance(node.get("content"), str):
            out.append(node["content"])
        for val in node.values():
            out.extend(_iter_text_content(val))
    elif isinstance(node, list):
        for item in node:
            out.extend(_iter_text_content(item))
    return out


def _find_glass_frame(data: dict[str, Any], key: str) -> dict[str, Any] | None:
    for child in data.get("children", []):
        name = str(child.get("name", ""))
        if key in name and "Glass Gold" in name and "定稿" in name and "审阅" not in name:
            return child
    return None


def check_pen_web_text_alignment() -> Check:
    """文件级：定稿帧 JSON 文案与当前 Web 生成源一致（MCP 不可用时的代理验收）。"""
    if not PEN.exists():
        return Check("pen_web_text", "Pencil 9 屏文案对齐 Web", False, required=False, error="missing pen")
    data = json.loads(PEN.read_text(encoding="utf-8"))
    per_frame: list[dict[str, Any]] = []
    all_ok = True
    for key, markers in PEN_FRAME_MARKERS:
        frame = _find_glass_frame(data, key)
        if frame is None:
            per_frame.append({"frame": key, "ok": False, "missing": markers, "error": "frame not found"})
            all_ok = False
            continue
        blob = "\n".join(_iter_text_content(frame))
        missing = [m for m in markers if m not in blob]
        ok = not missing
        if not ok:
            all_ok = False
        per_frame.append({"frame": key, "ok": ok, "missing": missing})
    return Check(
        "pen_web_text",
        "Pencil 9 屏文案对齐 Web",
        all_ok,
        required=False,
        detail={"frames": per_frame},
        error="" if all_ok else "missing markers in one or more frames",
    )


def capture_web_screenshots(base_url: str) -> Check:
    try:
        from playwright.sync_api import Error as PlaywrightError
        from playwright.sync_api import sync_playwright
    except ImportError:
        return Check(
            "web_screenshot_proxy",
            "Web 9 屏 Playwright 截图基线",
            False,
            required=False,
            error="playwright not installed",
        )

    SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
    shots: list[str] = []
    page_errors: list[str] = []

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(channel="chrome", headless=True)
            context = browser.new_context(viewport={"width": 1280, "height": 900})
            page = context.new_page()
            page.on("pageerror", lambda err: page_errors.append(str(err)))

            seed = f"{base_url.rstrip('/')}/web/index.html"
            page.goto(seed, wait_until="domcontentloaded", timeout=20000)
            page.evaluate(
                """() => {
                  localStorage.setItem('fj-plan', 'pro');
                  localStorage.setItem('fj-user', 'w08-screenshot@test.local');
                }"""
            )

            for slug, path in WEB_SCREENSHOTS:
                url = f"{base_url.rstrip('/')}{path}"
                page.goto(url, wait_until="domcontentloaded", timeout=20000)
                page.wait_for_timeout(800)
                out = SCREENSHOT_DIR / f"p4_{slug}.png"
                page.screenshot(path=str(out), full_page=True)
                shots.append(str(out))

            browser.close()
    except PlaywrightError as exc:
        return Check(
            "web_screenshot_proxy",
            "Web 9 屏 Playwright 截图基线",
            False,
            required=False,
            error=str(exc),
        )

    ok = len(shots) == len(WEB_SCREENSHOTS) and not page_errors
    return Check(
        "web_screenshot_proxy",
        "Web 9 屏 Playwright 截图基线",
        ok,
        required=False,
        detail={"count": len(shots), "dir": str(SCREENSHOT_DIR), "shots": shots},
        error="" if ok else f"errors={page_errors}",
    )


def check_pen_canvas_exports() -> Check:
    """画布级代理：Pencil MCP export_nodes 导出 PNG 存在且非空。"""
    if not PEN_SCREENSHOT_DIR.is_dir():
        return Check(
            "pen_canvas_exports",
            "Pencil MCP 画布 PNG 导出",
            False,
            required=False,
            error=f"missing dir {PEN_SCREENSHOT_DIR}",
        )
    files = sorted(PEN_SCREENSHOT_DIR.glob("*.png"))
    good = [f for f in files if f.stat().st_size >= PEN_CANVAS_MIN_BYTES]
    ok = len(good) >= PEN_CANVAS_MIN_FILES
    report_ok = False
    if PEN_CANVAS_REPORT.exists():
        try:
            report_ok = bool(json.loads(PEN_CANVAS_REPORT.read_text(encoding="utf-8")).get("ok"))
        except json.JSONDecodeError:
            report_ok = False
    return Check(
        "pen_canvas_exports",
        "Pencil MCP 画布 PNG 导出",
        ok,
        required=False,
        detail={
            "dir": str(PEN_SCREENSHOT_DIR),
            "png_count": len(good),
            "files": [f.name for f in good[:12]],
            "canvas_report_ok": report_ok,
            "canvas_report": str(PEN_CANVAS_REPORT) if PEN_CANVAS_REPORT.exists() else None,
        },
        error="" if ok else f"need>={PEN_CANVAS_MIN_FILES} png>={PEN_CANVAS_MIN_BYTES}b, got {len(good)}",
    )


def check_web_pages(base_url: str) -> list[Check]:
    checks: list[Check] = []
    for cid, cname, path, markers in WEB_SCREENS:
        try:
            status, html = _get_html(base_url, path)
            missing = [m for m in markers if m not in html]
            ok = status == 200 and not missing
            checks.append(
                Check(
                    cid,
                    cname,
                    ok,
                    detail={"status": status, "path": path, "missing": missing},
                    error="" if ok else f"status={status} missing={missing}",
                )
            )
        except (HTTPError, URLError, TimeoutError) as exc:
            checks.append(Check(cid, cname, False, error=str(exc)))
    return checks


def run_acceptance(
    *,
    base_url: str = "",
    preflight_only: bool = False,
    regenerate_pen: bool = True,
    web_screenshots: bool = False,
) -> dict[str, Any]:
    checks: list[Check] = []
    checks.append(check_pen_finalize(regenerate=regenerate_pen and not preflight_only))
    if not preflight_only:
        checks.append(check_pen_json_layout())
        checks.append(check_pen_web_text_alignment())
        checks.extend(check_static_separation())
        checks.append(check_js_syntax())
        checks.append(check_py_build_scripts())
    if base_url and not preflight_only:
        checks.extend(check_web_pages(base_url))
        if web_screenshots:
            checks.append(capture_web_screenshots(base_url))

    web_proxy_ok = any(c.id == "web_screenshot_proxy" and c.ok for c in checks)
    pen_text_ok = any(c.id == "pen_web_text" and c.ok for c in checks)
    if not preflight_only:
        checks.append(check_pen_canvas_exports())
    pen_canvas_ok = any(c.id == "pen_canvas_exports" and c.ok for c in checks)
    canvas_ok = pen_canvas_ok and pen_text_ok
    checks.append(
        Check(
            "pencil_canvas_mcp",
            "Pencil MCP 画布截图",
            canvas_ok,
            required=False,
            detail={
                "status": "ok" if canvas_ok else "pending",
                "web_screenshot_proxy": web_proxy_ok,
                "pen_web_text_proxy": pen_text_ok,
                "pen_canvas_exports": pen_canvas_ok,
                "hint": "export_nodes → p4_pen_screenshots; see p4_canvas_acceptance.json",
            },
            error="" if canvas_ok else "need pen_web_text + pen_canvas_exports",
        )
    )

    required = [c for c in checks if c.required]
    optional = [c for c in checks if not c.required]
    ok = all(c.ok for c in required)
    return {
        "ok": ok,
        "mode": "preflight" if preflight_only else "acceptance",
        "base_url": base_url or None,
        "summary": {
            "required_passed": sum(1 for c in required if c.ok),
            "required_total": len(required),
            "optional_passed": sum(1 for c in optional if c.ok),
            "optional_total": len(optional),
            "canvas_pending": not canvas_ok,
            "pen_canvas_exports": pen_canvas_ok,
            "pen_web_text_proxy": pen_text_ok,
            "web_screenshot_proxy": web_proxy_ok,
        },
        "checks": [asdict(c) for c in checks],
        "report_path": str(REPORT),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="W08/P4 FJLHXM 9-screen acceptance")
    parser.add_argument("--base-url", default="")
    parser.add_argument("--port", type=int, default=8036)
    parser.add_argument("--auto-server", action="store_true")
    parser.add_argument("--preflight-only", action="store_true")
    parser.add_argument("--skip-pen-regenerate", action="store_true")
    parser.add_argument("--web-screenshots", action="store_true", help="Capture Playwright baseline for 9 Web screens")
    args = parser.parse_args()

    sys.path.insert(0, str(ROOT / "scripts"))
    proc = None
    try:
        base_url = args.base_url.rstrip("/")
        if args.auto_server or (not base_url and not args.preflight_only):
            from smoke_w17_auth_ws import start_uvicorn, wait_for_health  # noqa: WPS433

            proc, base_url = start_uvicorn(args.port)
            wait_for_health(base_url)

        result = run_acceptance(
            base_url=base_url,
            preflight_only=args.preflight_only,
            regenerate_pen=not args.skip_pen_regenerate,
            web_screenshots=args.web_screenshots,
        )
    except Exception as exc:  # noqa: BLE001
        result = {"ok": False, "error": str(exc)}
    finally:
        if proc is not None:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()

    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
