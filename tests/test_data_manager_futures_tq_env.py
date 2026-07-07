"""天勤凭证仅从环境变量读取（无代码默认明文）。"""
from __future__ import annotations

import importlib
import sys

import pytest


def load_data_manager(monkeypatch: pytest.MonkeyPatch, tmp_path):
    monkeypatch.setenv("FUTURES_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("FUTURES_LOG_DIR", str(tmp_path / "logs"))
    sys.modules.pop("data_manager_futures", None)
    return importlib.import_module("data_manager_futures")


def test_require_tq_credentials_missing(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    monkeypatch.delenv("TQ_PHONE", raising=False)
    monkeypatch.delenv("TQ_PASS", raising=False)
    dm = load_data_manager(monkeypatch, tmp_path)
    with pytest.raises(RuntimeError, match="天勤账号未配置"):
        dm.require_tq_credentials()


def test_require_tq_credentials_ok(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    monkeypatch.setenv("TQ_PHONE", "13800000000")
    monkeypatch.setenv("TQ_PASS", "test-secret")
    dm = load_data_manager(monkeypatch, tmp_path)
    phone, pwd = dm.require_tq_credentials()
    assert phone == "13800000000"
    assert pwd == "test-secret"
