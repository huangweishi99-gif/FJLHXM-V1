"""Pytest bootstrap: stub tqsdk/tqsdk2 when native DLL is unavailable (local Windows dev)."""
from __future__ import annotations

import sys
from types import ModuleType


def _make_fake_tq_module(name: str) -> ModuleType:
    fake = ModuleType(name)

    class TqApi:  # noqa: D101
        def close(self) -> None:
            return None

    class TqAuth:  # noqa: D101
        def __init__(self, *_args, **_kwargs) -> None:
            pass

    fake.TqApi = TqApi
    fake.TqAuth = TqAuth
    fake.__version__ = "stub"
    return fake


def _ensure_tqsdk_stubs() -> None:
    for name in ("tqsdk", "tqsdk2"):
        if name in sys.modules:
            continue
        try:
            __import__(name)
        except Exception:
            sys.modules[name] = _make_fake_tq_module(name)


_ensure_tqsdk_stubs()
