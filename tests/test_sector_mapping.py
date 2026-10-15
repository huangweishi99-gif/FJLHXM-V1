"""SectorIndex 单元测试（仿 free-stockdb BoardIndex 设计）。

Design inspired by free-stockdb MIT © 2026 hello245m.

注意：本文件用 inline fixture，不依赖东财 / 不依赖网络 / 不依赖 data/sectors/a_stock_sectors.json。
集成测试（from_file 真实种子）在 test_from_file_real_seed 中。
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from sector_mapping import (
    BOARD_FIELDS,
    CATEGORY_MAP,
    FIELD_ALIASES,
    SectorIndex,
    _is_stock_code,
    _stock_code,
)


# ===== Fixtures =====

def _fixture_rows() -> list[dict]:
    """3 个概念 + 2 个申万一级 + 1 个申万二级；3 只股票分别跨 1/2/3 个板块。"""
    return [
        # 概念板块
        {
            "code": "BK0001",
            "name": "CPO概念",
            "category": "concept",
            "source": "eastmoney",
            "group": "东方财富概念",
            "symbols": ["300394", "300502", "002281"],
        },
        {
            "code": "BK0002",
            "name": "半导体",
            "category": "concept",
            "source": "eastmoney",
            "group": "东方财富概念",
            "symbols": ["688981", "002371"],
        },
        {
            "code": "BK0003",
            "name": "光伏概念",
            "category": "concept",
            "source": "eastmoney",
            "group": "东方财富概念",
            "symbols": ["601012"],
        },
        # 申万一级（占位）
        {
            "code": "sw_1_801080",
            "name": "电子",
            "category": "sw1",
            "source": "sw_placeholder",
            "group": "申万行业指数列表",
            "symbols": ["688981", "002371", "300394"],
        },
        {
            "code": "sw_1_801780",
            "name": "银行",
            "category": "sw1",
            "source": "sw_placeholder",
            "group": "申万行业指数列表",
            "symbols": ["600036", "601398"],
        },
        # 申万二级
        {
            "code": "sw_2_801081",
            "name": "半导体",
            "category": "sw2",
            "source": "sw_placeholder",
            "group": "申万行业指数",
            "symbols": ["688981", "002371"],
        },
    ]


@pytest.fixture
def index() -> SectorIndex:
    return SectorIndex(_fixture_rows())


# ===== 基本构造 =====

def test_empty_index_constructs():
    idx = SectorIndex()
    assert len(idx) == 0
    assert idx.boards == []
    assert idx.get() == []
    assert idx.get("CPO概念") == []


def test_build_populates_four_indices(index):
    # 6 个板块
    assert len(index) == 6
    # by_code
    assert "BK0001" in index.by_code
    assert "sw_1_801080" in index.by_code
    # by_category
    assert set(index.categories()) == {"concept", "sw1", "sw2"}
    # by_name（带类别前缀）
    assert len(index.by_name["concept_CPO概念"]) == 1
    # by_stock：688981 同时在 sw1 + sw2 + concept
    stock_688981 = index.by_stock["688981"]
    assert len(stock_688981) == 3


def test_skips_malformed_rows():
    rows = _fixture_rows() + [
        {"name": "缺 code"},  # 缺 code 应跳过
        {"code": "X", "name": "缺 category"},  # 缺 category 应跳过
        {"code": "Y", "name": "未知 category", "category": "sw99"},  # 未知 category 跳过
        "not a dict",  # 非 dict 跳过
    ]
    idx = SectorIndex(rows)
    assert len(idx) == 6  # 只保留 6 个有效


# ===== 按代码查 =====

def test_query_by_code_returns_full_with_symbols(index):
    result = index.get("BK0001")
    assert result["code"] == "BK0001"
    assert result["name"] == "CPO概念"
    assert result["symbols"] == ["300394", "300502", "002281"]


def test_query_by_code_not_found_returns_empty(index):
    assert index.get("BK9999") == []


# ===== 按名称查 =====

def test_query_by_name_exact_match(index):
    result = index.get("CPO概念")
    # 全 categories 模糊命中（concept 类别有）
    assert isinstance(result, list)
    assert any(b["code"] == "BK0001" for b in result)


def test_query_by_name_with_category_filter(index):
    # "半导体" 在 concept + sw2 都有；sw1 下没有（fixture sw1 是"电子"）
    sw2 = index.get("半导体", category="sw2")
    concept = index.get("半导体", category="concept")
    sw1_miss = index.get("半导体", category="sw1")

    assert sw2["code"] == "sw_2_801081"
    assert concept["code"] == "BK0002"
    # sw1 下没"半导体" → 应返回空 list
    assert sw1_miss == []


def test_query_by_name_fuzzy_substring(index):
    # "光" 应模糊匹配 "光伏概念"
    result = index.get("光")
    assert any(b["code"] == "BK0003" for b in result)


# ===== 按股票代码查 =====

def test_query_by_stock_returns_membership_without_symbols(index):
    # 300394 同时在 CPO + 电子
    result = index.get("300394")
    assert isinstance(result, list)
    assert len(result) == 2
    codes = {b["code"] for b in result}
    assert "BK0001" in codes
    assert "sw_1_801080" in codes
    # by_stock 不应带 symbols
    for board in result:
        assert "symbols" not in board


def test_query_by_stock_with_category_filter(index):
    result = index.get("300394", category="concept")
    assert len(result) == 1
    assert result[0]["code"] == "BK0001"


def test_query_by_stock_no_membership(index):
    assert index.get("999999") == []


# ===== 类别过滤 =====

def test_get_by_category_returns_all_in_category(index):
    concept = index.get(category="concept")
    assert isinstance(concept, list)
    assert len(concept) == 3
    assert all(b["category"] == "concept" for b in concept)

    sw1 = index.get(category="sw1")
    assert len(sw1) == 2


# ===== 字段投影 =====

def test_fields_projection_multi(index):
    result = index.get("BK0001", fields="name,code")
    assert result == ["CPO概念", "BK0001"]


def test_fields_projection_single_returns_scalar(index):
    result = index.get("BK0001", fields="name")
    assert result == "CPO概念"


def test_fields_projection_unknown_field_raises(index):
    with pytest.raises(ValueError, match="unknown field"):
        index.get("BK0001", fields="bad_field")


def test_fields_alias_symbols(index):
    # FIELD_ALIASES["symbol"] → "symbols"
    result = index.get("BK0001", fields="symbol")
    assert result == ["300394", "300502", "002281"]


# ===== 校验 =====

def test_unknown_category_raises(index):
    with pytest.raises(ValueError, match="unknown category"):
        index.get("CPO概念", category="sw99")


def test_int_category_raises_type_error(index):
    with pytest.raises(TypeError):
        index.get("CPO概念", category=1)  # type: ignore[arg-type]


# ===== 批量查询 =====

def test_batch_query_returns_dict(index):
    # 仿 free-stockdb 行为：批量单字段返回 {code: [scalar]}（list 形态保证结构一致）
    result = index.get(["300394", "601398"], category="sw1", fields="name")
    assert isinstance(result, dict)
    # 300394 在 sw1 电子；601398 在 sw1 银行
    assert result["300394"] == ["电子"]
    assert result["601398"] == ["银行"]


# ===== stocks_for =====

def test_stocks_for_by_code(index):
    assert index.stocks_for("BK0001") == ["300394", "300502", "002281"]


def test_stocks_for_by_name(index):
    # "半导体" 跨 concept / sw1 / sw2 三个类别，stock_for 取第一个命中
    stocks = index.stocks_for("半导体")
    assert "688981" in stocks


def test_stocks_for_unknown_returns_empty(index):
    assert index.stocks_for("NOT_A_BOARD") == []


# ===== dunder =====

def test_len_and_contains(index):
    assert len(index) == 6
    assert "BK0001" in index
    assert "CPO概念" in index
    assert "BK9999" not in index


# ===== 真实种子文件 =====

def test_from_file_real_seed():
    seed = Path(__file__).resolve().parents[1] / "data" / "sectors" / "a_stock_sectors.json"
    if not seed.exists():
        pytest.skip(f"seed file not present: {seed}")
    idx = SectorIndex.from_file(seed)
    # 至少 11 个板块（11 个概念 + ≥3 个 SW 占位 = 14）
    assert len(idx) >= 11
    # 必须含 CPO 概念
    assert idx.get("CPO概念") != [] or any(
        b.get("name") == "CPO概念" for b in idx.boards
    )


# ===== 工具函数 =====

def test_helpers():
    assert _is_stock_code("300394")
    assert _is_stock_code("600036.SH") is False
    assert _stock_code("600036.SH") == "600036"
    assert _stock_code(600036) == "600036"


# ===== 常量 =====

def test_constants_contain_expected_keys():
    assert {"concept", "sw1", "sw2", "sw3"} <= set(CATEGORY_MAP.keys())
    assert "code" in BOARD_FIELDS
    assert "symbols" in BOARD_FIELDS
    assert "symbol" in FIELD_ALIASES


# ===== 端到端：用 tmp_path 落盘再加载 =====

def test_round_trip_via_tmp_json(tmp_path: Path):
    rows = _fixture_rows()
    target = tmp_path / "sectors.json"
    target.write_text(json.dumps({"sectors": rows}, ensure_ascii=False), encoding="utf-8")
    idx = SectorIndex.from_file(target)
    assert len(idx) == 6
    assert idx.get("BK0001")["name"] == "CPO概念"
    assert idx.stocks_for("sw_1_801080") == ["688981", "002371", "300394"]


# ===== 缺文件 =====

def test_from_file_missing_raises(tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        SectorIndex.from_file(tmp_path / "nope.json")
