#!/usr/bin/env python3
"""O1 · Lottie 占位验收（工程链路 + 10 占位 JSON + pytest + browser smoke）。

Usage:
  python scripts/run_o1_lottie_placeholder_acceptance.py
  python scripts/run_o1_lottie_placeholder_acceptance.py --skip-browser
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
LOTTIE_DIR = ROOT / "web" / "assets" / "lottie"
EXPECTED = ["DS01", "DS02", "DS03", "DS04", "DS05", "DS06", "DS07", "DS08", "DS09", "TOTAL"]
OUT_JSON = ROOT / "runtime" / "web_validation" / "o1_lottie_placeholder_acceptance.json"
OUT_MD = ROOT / "runtime" / "web_validation" / "o1_lottie_placeholder_acceptance.md"


def check_lottie_assets() -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    manifest_path = LOTTIE_DIR / "manifest.json"
    if not manifest_path.exists():
        return {"ok": False, "error": "manifest.json missing", "checks": checks}

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    listed = list(manifest.get("strategies") or [])
    missing_manifest = [s for s in EXPECTED if s not in listed]
    if missing_manifest:
        checks.append({"id": "manifest_list", "ok": False, "detail": f"missing in manifest: {missing_manifest}"})
    else:
        checks.append({"id": "manifest_list", "ok": True, "detail": f"strategies={len(listed)}"})

    for sid in EXPECTED:
        path = LOTTIE_DIR / f"{sid}.json"
        if not path.exists():
            checks.append({"id": f"file_{sid}", "ok": False, "detail": "missing"})
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            checks.append({"id": f"file_{sid}", "ok": False, "detail": f"invalid json: {exc}"})
            continue
        w, h, fr, op = data.get("w"), data.get("h"), data.get("fr"), data.get("op")
        ok = w == 160 and h == 88 and fr == 30 and op == 300 and bool(data.get("layers"))
        checks.append(
            {
                "id": f"file_{sid}",
                "ok": ok,
                "detail": f"w={w} h={h} fr={fr} op={op} layers={len(data.get('layers') or [])}",
            }
        )

    ok = all(c["ok"] for c in checks)
    refinement = manifest.get("refinement") or "placeholder"
    return {"ok": ok, "checks": checks, "manifest_version": manifest.get("version"), "refinement": refinement}


def run_pytest() -> dict[str, Any]:
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/test_w15_strategy_animations.py", "-q"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    passed = proc.returncode == 0 and "passed" in proc.stdout
    return {
        "ok": passed,
        "exit_code": proc.returncode,
        "stdout_tail": proc.stdout.strip().splitlines()[-3:],
        "stderr_tail": proc.stderr.strip().splitlines()[-3:] if proc.stderr.strip() else [],
    }


def run_node_check() -> dict[str, Any]:
    files = [ROOT / "web" / "js" / "strategy_animations.js", ROOT / "web" / "js" / "app.js"]
    results = []
    for path in files:
        proc = subprocess.run(
            ["node", "--check", str(path)],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
        )
        results.append({"file": str(path.relative_to(ROOT)), "ok": proc.returncode == 0})
    return {"ok": all(r["ok"] for r in results), "files": results}


def run_browser_smoke() -> dict[str, Any]:
    proc = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "smoke_w15_strategies_browser.py"), "--auto-server"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    try:
        # smoke prints JSON as last block
        text = proc.stdout.strip()
        start = text.rfind("{")
        payload = json.loads(text[start:]) if start >= 0 else {"ok": False, "error": "no json output"}
    except json.JSONDecodeError as exc:
        payload = {"ok": False, "error": f"parse failed: {exc}", "raw_tail": proc.stdout[-500:]}
    payload["exit_code"] = proc.returncode
    return payload


def markdown_report(report: dict[str, Any]) -> str:
    lines = [
        "# O1 Lottie 占位验收报告",
        "",
        f"生成时间：{report.get('generated_at', '')}",
        f"**总体**：{'✅ PASS' if report.get('ok') else '❌ FAIL'}（{report.get('phase_label', 'O1')}）",
        "",
        "## 检查项",
        "",
        "| ID | 结果 | 说明 |",
        "|----|------|------|",
    ]
    for block_id, block in report.get("sections", {}).items():
        status = "✅" if block.get("ok") else "❌"
        if block_id == "assets":
            detail = f"{sum(1 for c in block.get('checks', []) if c['ok'])}/{len(block.get('checks', []))} asset checks"
        elif block_id == "pytest":
            detail = " ".join(block.get("stdout_tail") or [])
        elif block_id == "browser":
            detail = (
                f"lottie={block.get('lottie_count')} svg={block.get('svg_count')} "
                f"deep_link={block.get('deep_link_ok')} engine_tag={block.get('engine_tag', '')[:40]}"
            )
        else:
            detail = str(block.get("detail") or block.get("files") or "")[:120]
        lines.append(f"| {block_id} | {status} | {detail} |")

    lines.extend(
        [
            "",
            "## 说明",
            "",
            "- 本报告验收 **Lottie 工程链路**（加载器、manifest、10 JSON、弹层、暂停、深链）。",
            "- **N字突破分镜 v3**（manifest version≥4）：折线逐段绘制 → 前峰水平线 → 红/蓝启动棍 → 止损；对齐 N字突破03/04。",
            "- **工程精修 v2**（manifest version≥3）：峰极节点、光晕、暗角、apple.css 色板对齐。",
            "- **正式分镜** 仍可由设计方 drop-in 同名 JSON；drop-in 后重跑本脚本即可。",
            "",
            "## 复现",
            "",
            "```powershell",
            "python scripts/run_o1_lottie_placeholder_acceptance.py",
            "```",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="O1 Lottie placeholder acceptance")
    parser.add_argument("--skip-browser", action="store_true")
    args = parser.parse_args()

    sections: dict[str, Any] = {
        "assets": check_lottie_assets(),
        "node_check": run_node_check(),
        "pytest": run_pytest(),
    }
    if args.skip_browser:
        sections["browser"] = {"ok": True, "skipped": True, "detail": "browser smoke skipped by flag"}
    else:
        sections["browser"] = run_browser_smoke()

    ok = all(bool(s.get("ok")) for s in sections.values())
    assets = sections.get("assets") or {}
    refinement = assets.get("refinement") or "placeholder"
    phase = "O1_n_breakthrough" if "n_breakthrough" in refinement else ("O1_refined" if refinement != "placeholder" else "O1_placeholder")
    phase_labels = {
        "O1_n_breakthrough": "N字突破分镜 v4" if "v4" in refinement else "N字突破分镜 v3",
        "O1_refined": "工程精修 v2",
        "O1_placeholder": "占位工程验收",
    }
    report = {
        "ok": ok,
        "phase": phase,
        "phase_label": phase_labels.get(phase, "O1"),
        "refinement": refinement,
        "manifest_version": assets.get("manifest_version"),
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "sections": sections,
    }

    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    OUT_MD.write_text(markdown_report(report), encoding="utf-8")

    print(f"O1 placeholder acceptance ok={ok}")
    print(f"report_json={OUT_JSON}")
    print(f"report_md={OUT_MD}")
    for name, block in sections.items():
        print(f"  {name}: {'PASS' if block.get('ok') else 'FAIL'}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
