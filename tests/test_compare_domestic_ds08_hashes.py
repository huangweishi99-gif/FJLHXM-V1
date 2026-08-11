from __future__ import annotations

import hashlib
from pathlib import Path


def test_domestic_hash_normalizes_text_crlf(monkeypatch, tmp_path: Path) -> None:
    from scripts import compare_domestic_ds08_hashes as hashes

    monkeypatch.setattr(hashes, "ROOT", tmp_path)
    source = tmp_path / "src" / "example.py"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"print('ok')\r\n")

    assert hashes.local_hash("src/example.py") == hashlib.sha256(
        b"print('ok')\n"
    ).hexdigest()[:16]


def test_domestic_hash_preserves_non_text_bytes(monkeypatch, tmp_path: Path) -> None:
    from scripts import compare_domestic_ds08_hashes as hashes

    monkeypatch.setattr(hashes, "ROOT", tmp_path)
    source = tmp_path / "data" / "blob.bin"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"\x00\r\n\xff")

    assert hashes.local_hash("data/blob.bin") == hashlib.sha256(b"\x00\r\n\xff").hexdigest()[:16]
