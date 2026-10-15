"""build_sector_index.py 单元测试（mock 网络，不连真实东财）。

Design inspired by free-stockdb MIT © 2026 hello245m.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest


# 把 scripts/ 加入 sys.path
SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))


@pytest.fixture
def build_module():
    """动态导入 build_sector_index（无副作用）。"""
    import importlib

    if "build_sector_index" in sys.modules:
        del sys.modules["build_sector_index"]
    return importlib.import_module("build_sector_index")


# ===== 纯函数测试 =====

def test_merge_existing_preserves_sw_placeholders(build_module):
    fresh = [{"code": "BK0001", "name": "CPO概念", "category": "concept", "source": "eastmoney", "group": "东方财富", "symbols": []}]
    existing = {
        "version": "1",
        "sectors": [
            {"code": "sw_1_801080", "name": "电子", "category": "sw1", "source": "sw_placeholder", "symbols": []},
            {"code": "BK0001", "name": "CPO概念（过时）", "category": "concept", "source": "eastmoney", "symbols": ["300394"]},
        ],
    }
    merged = build_module.merge_existing(fresh, existing)
    codes = [s["code"] for s in merged]
    # SW 占位必须在
    assert "sw_1_801080" in codes
    # 东财 fresh 必须覆盖 existing 旧数据
    cpo = next(s for s in merged if s["code"] == "BK0001")
    assert cpo["name"] == "CPO概念"
    # 旧 symbols 保留（这次合并不应清空）
    assert cpo["symbols"] == ["300394"]


def test_merge_existing_dedupes_by_code(build_module):
    fresh = [
        {"code": "BK0001", "name": "A", "category": "concept", "source": "eastmoney", "group": "g", "symbols": []},
        {"code": "BK0001", "name": "A-dup", "category": "concept", "source": "eastmoney", "group": "g", "symbols": []},
    ]
    existing = {"sectors": []}
    merged = build_module.merge_existing(fresh, existing)
    assert sum(1 for s in merged if s["code"] == "BK0001") == 1


def test_parse_diff_handles_list_and_dict(build_module):
    # list 形态
    assert build_module.parse_diff({"data": {"diff": [{"f12": "001"}]}}) == [{"f12": "001"}]
    # dict 形态（罕见）
    assert build_module.parse_diff({"data": {"diff": {"k": {"f12": "002"}}}}) == [{"f12": "002"}]
    # 空
    assert build_module.parse_diff({"data": {}}) == []


def test_to_float_handles_dash_and_none(build_module):
    assert build_module.to_float(None) == 0.0
    assert build_module.to_float("-") == 0.0
    assert build_module.to_float("") == 0.0
    assert build_module.to_float("1.5") == 1.5
    assert build_module.to_float(2) == 2.0
    assert build_module.to_float("abc") == 0.0


# ===== 集成测试：mock request_eastmoney 跑 main() =====

def _mock_request_factory(boards_payload=None, stocks_payload=None):
    """返回一个 mock request_eastmoney 函数。"""
    calls = {"boards": 0, "stocks": 0}

    def _mock(params, retries=4, timeout=30):
        fs = params.get("fs", "")
        if "t:2" in fs or "t:3" in fs or fs.startswith("m:90"):
            calls["boards"] += 1
            return boards_payload or {
                "data": {
                    "diff": [
                        {"f12": "BK0001", "f14": "CPO概念", "f3": "1.2", "f6": "100", "f8": "2.5", "f20": "1e9", "f62": "50"},
                        {"f12": "BK0002", "f14": "半导体", "f3": "0.5", "f6": "200", "f8": "1.5", "f20": "2e9", "f62": "30"},
                    ]
                }
            }
        if fs.startswith("b:"):
            calls["stocks"] += 1
            return stocks_payload or {
                "data": {
                    "diff": [
                        {"f12": "300394"},
                        {"f12": "300502"},
                        {"f12": "002281"},
                    ]
                }
            }
        return {"data": None}

    return _mock, calls


def test_main_dry_run_writes_json(build_module, tmp_path, monkeypatch, capsys):
    output = tmp_path / "sectors.json"
    mock_req, calls = _mock_request_factory()
    monkeypatch.setattr(build_module, "request_eastmoney", mock_req)

    rc = build_module.main(
        [
            "--output",
            str(output),
            "--source",
            "concept",
        ]
    )
    assert rc == 0
    assert output.exists()
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["version"] == "2"
    assert len(payload["sectors"]) == 2
    codes = [s["code"] for s in payload["sectors"]]
    assert "BK0001" in codes
    # 不带 --include-symbols，symbols 应为空
    for s in payload["sectors"]:
        assert s["symbols"] == []
    # stdout / stderr 不应有 traceback
    captured = capsys.readouterr()
    assert "Traceback" not in captured.err


def test_main_include_symbols_populates_stocks(build_module, tmp_path, monkeypatch):
    output = tmp_path / "sectors.json"
    mock_req, calls = _mock_request_factory()
    monkeypatch.setattr(build_module, "request_eastmoney", mock_req)

    rc = build_module.main(
        [
            "--output",
            str(output),
            "--source",
            "concept",
            "--include-symbols",
            "--max-symbols",
            "10",
        ]
    )
    assert rc == 0
    payload = json.loads(output.read_text(encoding="utf-8"))
    bk0001 = next(s for s in payload["sectors"] if s["code"] == "BK0001")
    assert bk0001["symbols"] == ["300394", "300502", "002281"]
    # 至少 1 次个股查询
    assert calls["stocks"] >= 1


def test_main_merges_with_existing_sw_placeholders(build_module, tmp_path, monkeypatch):
    output = tmp_path / "sectors.json"
    # 预先种 SW 占位 + 旧 BK0001（带 symbols）
    seed = {
        "version": "1",
        "sectors": [
            {"code": "sw_1_801080", "name": "电子", "category": "sw1", "source": "sw_placeholder", "symbols": []},
            {"code": "BK0001", "name": "CPO（过时）", "category": "concept", "source": "eastmoney", "symbols": ["688999"]},
        ],
    }
    output.write_text(json.dumps(seed, ensure_ascii=False), encoding="utf-8")
    mock_req, _ = _mock_request_factory()
    monkeypatch.setattr(build_module, "request_eastmoney", mock_req)

    rc = build_module.main(["--output", str(output), "--source", "concept"])
    assert rc == 0
    payload = json.loads(output.read_text(encoding="utf-8"))
    codes = [s["code"] for s in payload["sectors"]]
    # SW 占位必保留
    assert "sw_1_801080" in codes
    # 旧 BK0001 symbols 保留（merge_existing 行为）
    bk0001 = next(s for s in payload["sectors"] if s["code"] == "BK0001")
    assert bk0001["symbols"] == ["688999"]
    # version 升到 2
    assert payload["version"] == "2"


def test_main_corrupt_existing_json_still_writes(build_module, tmp_path, monkeypatch, capsys):
    output = tmp_path / "sectors.json"
    output.write_text("this is not json", encoding="utf-8")
    mock_req, _ = _mock_request_factory()
    monkeypatch.setattr(build_module, "request_eastmoney", mock_req)

    rc = build_module.main(["--output", str(output), "--source", "concept"])
    assert rc == 0
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert len(payload["sectors"]) == 2
    # 警告信息应出现在 stderr
    captured = capsys.readouterr()
    assert "WARN" in captured.err
