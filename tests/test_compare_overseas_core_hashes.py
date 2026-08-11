from __future__ import annotations

import hashlib
from pathlib import Path


def test_shell_hash_normalizes_crlf(monkeypatch, tmp_path: Path) -> None:
    from scripts import compare_overseas_core_hashes as hashes

    monkeypatch.setattr(hashes, "ROOT", tmp_path)
    script = tmp_path / "scripts" / "watchdog_overseas.sh"
    script.parent.mkdir(parents=True)
    script.write_bytes(b"#!/usr/bin/env bash\r\necho ok\r\n")

    assert hashes.local_hash("scripts/watchdog_overseas.sh") == hashlib.sha256(
        b"#!/usr/bin/env bash\necho ok\n"
    ).hexdigest()


def test_non_shell_hash_preserves_bytes(monkeypatch, tmp_path: Path) -> None:
    from scripts import compare_overseas_core_hashes as hashes

    monkeypatch.setattr(hashes, "ROOT", tmp_path)
    source = tmp_path / "src" / "example.py"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"print('ok')\r\n")

    assert hashes.local_hash("src/example.py") == hashlib.sha256(b"print('ok')\r\n").hexdigest()
