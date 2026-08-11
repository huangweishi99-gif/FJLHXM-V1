"""Ensure archive docs manifest paths exist (2026-06-02 results batches)."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "scripts" / "fengji_archive_docs_manifest.txt"


def test_fengji_archive_docs_manifest_files_exist() -> None:
    lines = MANIFEST.read_text(encoding="utf-8").splitlines()
    rel_paths = [ln.strip() for ln in lines if ln.strip() and not ln.strip().startswith("#")]
    assert rel_paths, "manifest empty"
    missing = [rel for rel in rel_paths if not (ROOT / rel.replace("/", "\\")).is_file()]
    assert not missing, f"missing archive manifest files: {missing}"
