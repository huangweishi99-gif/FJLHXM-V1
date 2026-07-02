"""Ensure Phase 2 API manifest paths exist (PR #8 chart bucket)."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PHASE1 = ROOT / "scripts" / "fengji_api_phase1_manifest.txt"
PHASE2 = ROOT / "scripts" / "fengji_api_phase2_manifest.txt"


def _manifest_paths(manifest: Path) -> list[str]:
    lines = manifest.read_text(encoding="utf-8").splitlines()
    return [ln.strip() for ln in lines if ln.strip() and not ln.strip().startswith("#")]


def test_fengji_api_phase2_manifest_files_exist() -> None:
    rel_paths = _manifest_paths(PHASE1) + _manifest_paths(PHASE2)
    assert rel_paths, "manifest empty"
    missing = [rel for rel in rel_paths if not (ROOT / rel.replace("/", "\\")).is_file()]
    assert not missing, f"missing phase2 manifest files: {missing}"
