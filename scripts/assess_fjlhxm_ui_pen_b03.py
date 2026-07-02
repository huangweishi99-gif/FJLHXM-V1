#!/usr/bin/env python3
"""Plan B B0-3: file-level acceptance for FJLHXM-UI.pen (9 screens + review note)."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PEN = ROOT / "FJLHXM-UI.pen"
DESIGN_FREEZE = ROOT / "docs" / "FJLHXM_UI_DESIGN_FREEZE.md"

EXPECTED_SCREENS = [
    ("01 · Dashboard", (3200, 0), "index.html"),
    ("02 · Backtest", (3200, 920), "backtest.html"),
    ("03 · Monitor", (4720, 0), "monitor.html"),
    ("04 · Strategies", (4720, 920), "strategies.html"),
    ("05 · Pricing", (6240, 920), "pricing.html"),
    ("06 · Symbol Chart", (7760, 920), "symbol.html"),
    ("07 · Auth", (7760, 0), "login.html"),
    ("08 · Community", (9280, 0), "community.html"),
    ("09 · Payment", (9280, 920), "payment.html"),
]
REVIEW_POS = (3200, -260)
FRAME_SIZE = (1280, 832)


def load_pen() -> dict:
    if not PEN.is_file():
        raise FileNotFoundError(PEN)
    return json.loads(PEN.read_text(encoding="utf-8"))


def find_screen(frames: list[dict], key: str) -> dict | None:
    for frame in frames:
        name = str(frame.get("name", ""))
        if key in name and "Glass Gold" in name:
            return frame
    return None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default=str(ROOT / "results" / "plan_b_b03_pencil_acceptance"))
    args = parser.parse_args()

    data = load_pen()
    frames = [c for c in data.get("children", []) if "Glass Gold" in str(c.get("name", ""))]
    screens = [f for f in frames if "审阅说明" not in str(f.get("name", ""))]

    checks: list[dict] = []
    for key, (ex, ey), web_page in EXPECTED_SCREENS:
        frame = find_screen(screens, key)
        web_path = ROOT / "web" / web_page
        ok = frame is not None
        pos_ok = size_ok = web_ok = False
        node_id = None
        if frame:
            node_id = frame.get("id")
            pos_ok = frame.get("x") == ex and frame.get("y") == ey
            size_ok = frame.get("width") == FRAME_SIZE[0] and frame.get("height") == FRAME_SIZE[1]
        web_ok = web_path.is_file()
        checks.append(
            {
                "screen": key,
                "node_id": node_id,
                "position": [frame.get("x"), frame.get("y")] if frame else None,
                "expected_position": [ex, ey],
                "size": [frame.get("width"), frame.get("height")] if frame else None,
                "web": web_page,
                "web_exists": web_ok,
                "pass": ok and pos_ok and size_ok and web_ok,
            }
        )

    review = next((f for f in frames if "审阅说明" in str(f.get("name", ""))), None)
    review_ok = review is not None and review.get("x") == REVIEW_POS[0] and review.get("y") == REVIEW_POS[1]

    report = {
        "pen_file": str(PEN),
        "design_freeze": str(DESIGN_FREEZE),
        "screen_count": len(screens),
        "expected_screens": len(EXPECTED_SCREENS),
        "review_note": review_ok,
        "canvas_mcp": "pending (open FJLHXM-UI.pen in Pencil editor for get_screenshot)",
        "checks": checks,
        "pass": len(screens) == 9 and all(c["pass"] for c in checks) and review_ok,
    }

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "B03_FILE_LEVEL.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "# Plan B B0-3 · Pencil 9 屏验收",
        "",
        f"**文件级**：{'✅ PASS' if report['pass'] else '❌ FAIL'}",
        f"**画布级**：⏳ **待 Pencil MCP**（须在编辑器打开 `FJLHXM-UI.pen`）",
        "",
        "## 屏位对账（1280×832）",
        "",
        "| # | 帧 | nodeId | 坐标 | Web |",
        "|---|-----|--------|------|-----|",
    ]
    for c in checks:
        flag = "✅" if c["pass"] else "❌"
        pos = c["position"] or ["—", "—"]
        lines.append(
            f"| {flag} | {c['screen']} | `{c['node_id'] or '—'}` | ({pos[0]}, {pos[1]}) | `{c['web']}` |"
        )
    lines.extend(
        [
            "",
            f"审阅说明帧 @ (3200, -260)：`{'✅' if review_ok else '❌'}`",
            "",
            "## 画布验收步骤（待人工/下次 MCP 连上）",
            "",
            "1. 在 Cursor 中打开 `FJLHXM-UI.pen`（Pencil 扩展）",
            "2. 对每屏 `nodeId` 调用 `get_screenshot`",
            "3. 核对：顶栏导航 · 三档订阅入口 · Community 无收款码 · Payment 独立微信页",
            "",
            "引用：`docs/FJLHXM_UI_DESIGN_FREEZE.md`",
            "",
        ]
    )
    (out / "B03_ACCEPTANCE.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(json.dumps({"pass": report["pass"], "screens": len(screens), "canvas": "pending"}, ensure_ascii=False))
    return 0 if report["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
