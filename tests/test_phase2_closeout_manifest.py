"""Phase 2 closeout manifest paths exist."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "scripts" / "fengji_phase2_closeout_manifest.txt"
RESIDUAL = ROOT / "scripts" / "fengji_stash_residual_manifest.txt"


def test_phase2_closeout_manifest_files_exist() -> None:
    rel_paths = [
        ln.strip()
        for ln in MANIFEST.read_text(encoding="utf-8").splitlines()
        if ln.strip() and not ln.strip().startswith("#")
    ]
    assert rel_paths
    missing = [rel for rel in rel_paths if not (ROOT / rel).is_file()]
    assert not missing, f"missing closeout manifest: {missing}"


def test_stash_residual_manifest_has_data_prefix() -> None:
    lines = [
        ln.strip()
        for ln in RESIDUAL.read_text(encoding="utf-8").splitlines()
        if ln.strip() and not ln.strip().startswith("#")
    ]
    assert "data/" in lines
