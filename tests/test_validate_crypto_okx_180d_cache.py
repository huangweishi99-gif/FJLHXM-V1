"""Cache row-count guard for crypto_okx 180d files."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def test_validate_crypto_okx_180d_cache_ok(tmp_path: Path) -> None:
    cache = tmp_path / "crypto_okx"
    cache.mkdir()
    (cache / "BTC-USDT_1D_180d.csv").write_text(
        "date,open,high,low,close,volume\n2026-01-01 00:00:00,1,1,1,1,1\n",
        encoding="utf-8",
    )
    script = Path(__file__).resolve().parents[1] / "scripts" / "validate_crypto_okx_180d_cache.py"
    proc = subprocess.run(
        [sys.executable, str(script), "--dir", str(cache)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0
    assert "CRYPTO_180D_CACHE_OK" in proc.stdout


def test_validate_crypto_okx_180d_cache_fail(tmp_path: Path) -> None:
    cache = tmp_path / "crypto_okx"
    cache.mkdir()
    lines = ["date,open,high,low,close,volume\n"] + [
        f"2026-01-01 00:{i:02d}:00,1,1,1,1,1\n" for i in range(25000)
    ]
    (cache / "XRP-USDT_15m_180d.csv").write_text("".join(lines), encoding="utf-8")
    script = Path(__file__).resolve().parents[1] / "scripts" / "validate_crypto_okx_180d_cache.py"
    proc = subprocess.run(
        [sys.executable, str(script), "--dir", str(cache)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 1
    assert "CRYPTO_180D_CACHE_FAIL" in proc.stdout
