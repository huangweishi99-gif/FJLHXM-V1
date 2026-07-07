#!/usr/bin/env python3
"""Phase 2 D7 收口验收：closeout manifest · stash 边界 · D5/D6 烟测。"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CLOSEOUT_MANIFEST = ROOT / "scripts" / "fengji_phase2_closeout_manifest.txt"
RESIDUAL_MANIFEST = ROOT / "scripts" / "fengji_stash_residual_manifest.txt"


def fail(msg: str) -> None:
    print(f"PHASE2_CLOSEOUT_FAIL: {msg}")
    sys.exit(1)


def read_manifest(path: Path) -> list[str]:
    lines = path.read_text(encoding="utf-8").splitlines()
    return [ln.strip() for ln in lines if ln.strip() and not ln.strip().startswith("#")]


def check_closeout_files() -> None:
    if not CLOSEOUT_MANIFEST.is_file():
        fail("缺少 fengji_phase2_closeout_manifest.txt")
    missing = [rel for rel in read_manifest(CLOSEOUT_MANIFEST) if not (ROOT / rel).is_file()]
    if missing:
        fail(f"closeout manifest 缺文件: {missing[:8]}{'...' if len(missing) > 8 else ''}")


def check_residual_manifest() -> None:
    if not RESIDUAL_MANIFEST.is_file():
        fail("缺少 fengji_stash_residual_manifest.txt")
    prefixes = read_manifest(RESIDUAL_MANIFEST)
    if "data/" not in prefixes:
        fail("residual manifest 应包含 data/")


def check_stash_still_present() -> None:
    proc = subprocess.run(
        ["git", "stash", "list"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        fail(f"git stash list 失败: {proc.stderr.strip()}")
    if "stash@{0}:" not in proc.stdout:
        fail("stash@{0} 不存在（若已 pop 请人工确认残留物已处理）")
    if "b04-wip-all" not in proc.stdout:
        fail("stash@{0} 消息非 b04-wip-all，需人工复查")


def audit_stash_categories() -> dict[str, int]:
    proc = subprocess.run(
        ["git", "stash", "show", "stash@{0}", "--name-only"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        fail(f"git stash show 失败: {proc.stderr.strip()}")
    files = [ln.strip() for ln in proc.stdout.splitlines() if ln.strip()]
    counts = {"total": len(files), "data": 0, "fjlh": 0}
    for rel in files:
        if rel.startswith("data/"):
            counts["data"] += 1
        elif rel.startswith("FJLHXM") or rel.startswith("designs/"):
            counts["fjlh"] += 1
    if counts["total"] < 300:
        fail(f"stash 文件数异常偏少: {counts['total']}")
    if counts["data"] < 200:
        fail(f"stash data/ 文件数异常偏少: {counts['data']}")
    return counts


def run_child(script: str) -> None:
    proc = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / script)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        tail = (proc.stdout + proc.stderr).strip().splitlines()[-3:]
        fail(f"{script} 失败: {' | '.join(tail)}")


def main() -> None:
    check_closeout_files()
    check_residual_manifest()
    check_stash_still_present()
    counts = audit_stash_categories()
    run_child("verify_d5_data_pending_policy.py")
    run_child("verify_d6_market_coverage_boundaries.py")
    print(
        f"PHASE2_CLOSEOUT_OK stash_files={counts['total']} "
        f"data_csv={counts['data']} fjlh={counts['fjlh']}"
    )


if __name__ == "__main__":
    main()
