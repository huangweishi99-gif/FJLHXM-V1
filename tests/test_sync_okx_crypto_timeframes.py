"""Tests for OKX-only crypto sync and data_manager skip list."""
from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def test_data_manager_does_not_include_okx_only_symbols_in_binance_list():
    sync = _load_module("sync_missing_crypto_15m", ROOT / "scripts" / "sync_missing_crypto_15m.py")
    text = (ROOT / "data_manager.py").read_text(encoding="utf-8")
    for symbol in sync.OKX_ONLY_SYMBOLS:
        assert f"'{symbol}'" not in text


def test_sync_script_timeframe_spec_covers_d1_h1_m15():
    sync = _load_module("sync_missing_crypto_15m", ROOT / "scripts" / "sync_missing_crypto_15m.py")
    assert set(sync.TIMEFRAME_SPEC) == {"M15", "D1", "H1"}
    assert sync.TIMEFRAME_SPEC["D1"]["folder"] == "1d"
    assert sync.TIMEFRAME_SPEC["D1"]["default_days"] == 1825


def test_crypto_ingest_okx_cursor_uses_utc_timestamp():
    """Naive UTC + .timestamp() on CST hosts skews OKX after-cursor by ~8h."""
    ingest = _load_module("crypto_ingest", ROOT / "services" / "crypto_ingest.py")
    text = (ROOT / "services" / "crypto_ingest.py").read_text(encoding="utf-8")
    assert "utc_now()" in text
    assert "okx_after_cursor_ms" in text
    assert "validate_okx_freshness" in text
    body = text.split("def fetch_okx_candle_rows")[1].split("\ndef ")[0]
    assert "replace(tzinfo=None)" not in body


def test_okx_after_cursor_ms_matches_utc_epoch():
    from datetime import datetime, timezone

    ingest = _load_module("crypto_ingest2", ROOT / "services" / "crypto_ingest.py")
    fixed = datetime(2026, 6, 29, 4, 50, 0, tzinfo=timezone.utc)
    assert ingest.okx_after_cursor_ms(end=fixed) == "1782708600000"


def test_validate_okx_freshness_rejects_stale_h1():
    from datetime import datetime, timedelta, timezone
    from unittest.mock import patch

    ingest = _load_module("crypto_ingest3", ROOT / "services" / "crypto_ingest.py")
    fixed = datetime(2026, 6, 29, 12, 0, 0, tzinfo=timezone.utc)
    stale = (fixed - timedelta(hours=10)).strftime("%Y-%m-%d %H:%M:%S")
    rows = [{"timestamp": stale, "open": 1, "high": 1, "low": 1, "close": 1, "volume": 1}]
    with patch.object(ingest, "utc_now", return_value=fixed):
        try:
            ingest.validate_okx_freshness(rows, bar="1H")
            assert False, "expected stale error"
        except ValueError as exc:
            assert "stale" in str(exc).lower()


def test_check_okx_csv_freshness_script_ok(tmp_path):
    from datetime import datetime, timedelta, timezone
    from unittest.mock import patch

    check = _load_module("check_okx_csv_freshness", ROOT / "scripts" / "check_okx_csv_freshness.py")
    ingest = _load_module("crypto_ingest4", ROOT / "services" / "crypto_ingest.py")
    data_dir = tmp_path / "data"
    for folder, ts in (
        ("15m", (datetime(2026, 6, 29, 6, 45, 0, tzinfo=timezone.utc)).strftime("%Y-%m-%d %H:%M:%S")),
        ("1h", (datetime(2026, 6, 29, 6, 0, 0, tzinfo=timezone.utc)).strftime("%Y-%m-%d %H:%M:%S")),
        ("1d", "2026-06-28"),
    ):
        d = data_dir / folder
        d.mkdir(parents=True)
        (d / "HYPEUSDT.csv").write_text(
            "timestamp,open,high,low,close,volume\n" + f"{ts},1,1,1,1,1\n",
            encoding="utf-8",
        )
    fixed = datetime(2026, 6, 29, 7, 0, 0, tzinfo=timezone.utc)
    with patch.object(ingest, "utc_now", return_value=fixed):
        with patch.object(check, "utc_now", return_value=fixed):
            rows = check.check_symbol("HYPEUSDT", data_dir=data_dir)
    assert all(r["status"] == "ok" for r in rows)
