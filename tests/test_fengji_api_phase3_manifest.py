"""Ensure Phase 3 deploy manifest paths exist (PR #9)."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _manifest_paths(name: str) -> list[str]:
    manifest = ROOT / "scripts" / name
    lines = manifest.read_text(encoding="utf-8").splitlines()
    return [ln.strip() for ln in lines if ln.strip() and not ln.strip().startswith("#")]


def test_fengji_api_phase3_manifest_files_exist() -> None:
    rel_paths = (
        _manifest_paths("fengji_api_phase1_manifest.txt")
        + _manifest_paths("fengji_api_phase2_manifest.txt")
        + _manifest_paths("fengji_api_phase3_manifest.txt")
    )
    assert rel_paths, "manifest empty"
    missing = [rel for rel in rel_paths if not (ROOT / rel.replace("/", "\\")).is_file()]
    assert not missing, f"missing phase3 manifest files: {missing}"


def test_fengji_api_full_deploy_manifest_files_exist() -> None:
    rel_paths = _manifest_paths("fengji_api_deploy_manifest.txt")
    assert rel_paths, "manifest empty"
    missing = [rel for rel in rel_paths if not (ROOT / rel.replace("/", "\\")).is_file()]
    assert not missing, f"missing full deploy manifest files: {missing}"
