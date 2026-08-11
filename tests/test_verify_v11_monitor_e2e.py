"""Unit tests for scripts/verify_v11_monitor_e2e.py auth helpers."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "verify_v11_monitor_e2e.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("verify_v11_monitor_e2e", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules["verify_v11_monitor_e2e"] = mod
    spec.loader.exec_module(mod)
    return mod


def test_resolve_pro_token_prefers_explicit_arg() -> None:
    mod = _load_module()
    token, mode = mod.resolve_pro_token("http://x", pro_token="jwt-explicit", mint_pro_token=True)
    assert token == "jwt-explicit"
    assert mode == "pro_token_arg"


def test_resolve_pro_token_env_fallback(monkeypatch) -> None:
    mod = _load_module()
    monkeypatch.setenv("FENGJI_V11_E2E_PRO_TOKEN", "jwt-from-env")
    token, mode = mod.resolve_pro_token("http://x", pro_token="", mint_pro_token=False)
    assert token == "jwt-from-env"
    assert mode == "pro_token_arg"


def test_resolve_pro_token_anonymous_when_disabled() -> None:
    mod = _load_module()
    token, mode = mod.resolve_pro_token("http://x", pro_token="", mint_pro_token=False)
    assert token is None
    assert mode == "anonymous"


def test_mint_pro_access_token_success() -> None:
    mod = _load_module()
    with patch.object(mod, "_post_json") as post:
        post.side_effect = [
            (200, {"access_token": "tok-free", "user": {"plan": "free"}}),
            (200, {"access_token": "tok-pro", "user": {"plan": "pro"}}),
        ]
        token, detail = mod.mint_pro_access_token("http://127.0.0.1:8000")
    assert token == "tok-pro"
    assert detail.startswith("mint_pro")


def test_mint_pro_access_token_manual_confirm_failure() -> None:
    mod = _load_module()
    with patch.object(mod, "_post_json") as post:
        post.side_effect = [
            (200, {"access_token": "tok-free"}),
            (503, {"detail": "manual confirm disabled"}),
        ]
        token, detail = mod.mint_pro_access_token("http://127.0.0.1:8000")
    assert token is None
    assert "manual_confirm_failed" in detail
