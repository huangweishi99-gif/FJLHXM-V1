"""AdjFactorIndex 单元测试（仿 free-stockdb AdjFactorIndex 设计）。

Design inspired by free-stockdb MIT © 2026 hello245m.
"""
from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd
import pytest

from adj_factor import AdjFactorIndex, AdjFactorMissingError


# ===== Fixtures =====

def _csv_text(rows: list[tuple[str, str, float]]) -> str:
    out = "code,date,adj_factor\n"
    for code, d, factor in rows:
        out += f"{code},{d},{factor}\n"
    return out


@pytest.fixture
def sample_csv(tmp_path: Path) -> Path:
    """3 个 code × 不同日期段。"""
    p = tmp_path / "adj_factor.csv"
    p.write_text(
        _csv_text(
            [
                ("000021", "2020-01-02", 0.50),
                ("000021", "2020-06-30", 0.75),
                ("000021", "2021-01-01", 1.00),
                ("000166", "2020-01-02", 0.90),
                ("000166", "2020-12-31", 1.00),
                ("300502", "2024-01-02", 1.00),
            ]
        ),
        encoding="utf-8",
    )
    return p


@pytest.fixture
def index(sample_csv: Path) -> AdjFactorIndex:
    return AdjFactorIndex.from_csv(sample_csv)


def _df_with_dates(dates: list[str], close: list[float]) -> pd.DataFrame:
    return pd.DataFrame({"date": dates, "open": close, "high": close, "low": close, "close": close, "volume": 0})


# ===== 空索引 =====

def test_empty_index():
    idx = AdjFactorIndex.empty()
    assert len(idx) == 0
    assert idx.codes() == []
    assert not idx.has("000021")
    assert "000021" not in idx
    assert idx.latest("000021") is None
    assert idx.earliest("000021") is None


# ===== from_csv =====

def test_from_csv_loads_all_codes(index):
    assert len(index) == 3
    assert sorted(index.codes()) == ["000021", "000166", "300502"]
    assert "000021" in index
    assert "999999" not in index


def test_from_csv_sorts_by_date(index):
    # 000021 应按日期升序
    factors = index.factors["000021"]
    assert factors[0][0] == date(2020, 1, 2)
    assert factors[-1][0] == date(2021, 1, 1)
    # 同一 code 内必须按日期升序
    dates = [d for d, _ in factors]
    assert dates == sorted(dates)


def test_from_csv_zfills_codes(index):
    # "300502" 必须保留前导 0（即使 from_csv 已 zfill）
    assert "300502" in index
    # 直接以 5 位字符串查也应命中（zfill 容错）
    assert index.has("300502")


def test_from_csv_dedupes_same_date(tmp_path: Path):
    # 同 code 同 date 重复 → 去重保留先出现的
    p = tmp_path / "dup.csv"
    p.write_text(
        _csv_text(
            [
                ("000021", "2020-01-02", 0.5),
                ("000021", "2020-01-02", 0.6),  # 同日重复
                ("000021", "2020-01-02", 0.7),  # 三次重复
            ]
        ),
        encoding="utf-8",
    )
    idx = AdjFactorIndex.from_csv(p)
    assert idx.count("000021") == 1
    assert idx.factor_on("000021", "2020-01-02") == 0.5


def test_from_csv_missing_file(tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        AdjFactorIndex.from_csv(tmp_path / "nope.csv")


def test_from_csv_missing_column(tmp_path: Path):
    p = tmp_path / "bad.csv"
    p.write_text("code,date\n000021,2020-01-02\n", encoding="utf-8")
    with pytest.raises(ValueError, match="缺必要列"):
        AdjFactorIndex.from_csv(p)


# ===== from_records =====

def test_from_records_basic():
    idx = AdjFactorIndex.from_records(
        [
            {"code": "000021", "date": "2020-01-02", "adj_factor": 0.5},
            {"code": "000021", "date": "2020-06-30", "adj_factor": 0.75},
            {"code": "000166", "date": "2020-01-02", "adj_factor": 0.9},
        ]
    )
    assert len(idx) == 2
    assert idx.count("000021") == 2


# ===== 查询接口 =====

def test_factor_on_hit_and_miss(index):
    assert index.factor_on("000021", "2020-01-02") == 0.50
    assert index.factor_on("000021", "2021-01-01") == 1.00
    assert index.factor_on("000021", "2025-01-01") is None  # 越界
    assert index.factor_on("999999", "2020-01-02") is None  # 未知 code


def test_range_filter(index):
    items = index.range("000021", "2020-01-01", "2020-12-31")
    assert len(items) == 2
    assert all(2020 <= d.year <= 2020 for d, _ in items)

    # 反向区间 → 空
    assert index.range("000021", "2020-12-31", "2020-01-01") == []


def test_latest_earliest(index):
    assert index.earliest("000021") == (date(2020, 1, 2), 0.50)
    assert index.latest("000021") == (date(2021, 1, 1), 1.00)
    assert index.earliest("999999") is None


# ===== 区间完整性 =====

def test_missing_excludes_weekends():
    """周末不应出现在 missing 列表中。"""
    idx = AdjFactorIndex.from_records(
        [
            {"code": "000021", "date": "2020-01-02", "adj_factor": 1.0},  # 周四
            {"code": "000021", "date": "2020-01-03", "adj_factor": 1.0},  # 周五
            # 2020-01-04 (周六) / 2020-01-05 (周日) 缺失是正常的
            {"code": "000021", "date": "2020-01-06", "adj_factor": 1.0},  # 周一
        ]
    )
    missing = idx.missing("000021", "2020-01-02", "2020-01-06")
    # 周末不算缺失
    assert missing == []


def test_missing_detects_gap():
    """工作日缺因子应被识别。"""
    idx = AdjFactorIndex.from_records(
        [
            {"code": "000021", "date": "2020-01-02", "adj_factor": 1.0},  # 周四
            # 2020-01-03 (周五) 缺失
            {"code": "000021", "date": "2020-01-06", "adj_factor": 1.0},  # 周一
        ]
    )
    missing = idx.missing("000021", "2020-01-02", "2020-01-06")
    assert missing == [date(2020, 1, 3)]


def test_is_full_true_and_false(index):
    # 000021 区间 [2020-01-02, 2020-06-30] 但实际只覆盖 2 个工作日（因子 2 个）
    # 真实工作日数量远大于 2 → 必缺 → is_full=False
    assert not index.is_full("000021", "2020-01-02", "2020-06-30")
    # 单点区间（start==end）且有因子 → True
    assert index.is_full("000021", "2020-01-02", "2020-01-02")
    # 未知 code → False
    assert not index.is_full("999999", "2020-01-02", "2020-01-02")


# ===== 折算（核心） =====

def test_to_qfq_basic():
    """none × (1.0 / adj_factor) = qfq。"""
    idx = AdjFactorIndex.from_records(
        [
            {"code": "000021", "date": "2020-01-02", "adj_factor": 0.5},
            {"code": "000021", "date": "2021-01-01", "adj_factor": 1.0},
        ]
    )
    df = _df_with_dates(
        ["2020-01-02", "2021-01-01"],
        [10.0, 20.0],
    )
    out = idx.to_qfq(df, "000021")
    # 2020-01-02: 10 / 0.5 = 20
    # 2021-01-01: 20 / 1.0 = 20
    assert out.loc[0, "close"] == pytest.approx(20.0)
    assert out.loc[1, "close"] == pytest.approx(20.0)
    # open/high/low 也应同乘
    assert out.loc[0, "open"] == pytest.approx(20.0)


def test_to_hfq_basic():
    """qfq × adj_factor = hfq。"""
    idx = AdjFactorIndex.from_records(
        [
            {"code": "000021", "date": "2020-01-02", "adj_factor": 0.5},
            {"code": "000021", "date": "2021-01-01", "adj_factor": 1.0},
        ]
    )
    df = _df_with_dates(
        ["2020-01-02", "2021-01-01"],
        [20.0, 20.0],
    )
    out = idx.to_hfq(df, "000021")
    # 2020-01-02: 20 × 0.5 = 10
    # 2021-01-01: 20 × 1.0 = 20
    assert out.loc[0, "close"] == pytest.approx(10.0)
    assert out.loc[1, "close"] == pytest.approx(20.0)


def test_to_none_basic():
    """qfq × adj_factor = none（与 to_hfq 同公式；语义区分由调用方负责）。"""
    idx = AdjFactorIndex.from_records(
        [
            {"code": "000021", "date": "2020-01-02", "adj_factor": 0.5},
        ]
    )
    df = _df_with_dates(["2020-01-02"], [20.0])
    out = idx.to_none(df, "000021")
    assert out.loc[0, "close"] == pytest.approx(10.0)


def test_apply_invalid_fq(index):
    df = _df_with_dates(["2020-01-02"], [10.0])
    with pytest.raises(ValueError, match="unknown fq"):
        index.apply(df, "000021", fq="xxff")


def test_apply_missing_code(index):
    df = _df_with_dates(["2020-01-02"], [10.0])
    with pytest.raises(AdjFactorMissingError) as info:
        index.apply(df, "999999", fq="hfq")
    assert info.value.code == "999999"


def test_apply_with_missing_dates_in_range(index):
    """df 中的某些日期索引里没因子 → 异常携带 missing_dates。"""
    df = _df_with_dates(
        ["2020-01-02", "2025-06-15"],  # 2025-06-15 无因子
        [10.0, 20.0],
    )
    with pytest.raises(AdjFactorMissingError) as info:
        index.apply(df, "000021", fq="hfq")
    assert info.value.code == "000021"
    assert any(d.year == 2025 for d in info.value.missing_dates)


def test_apply_empty_dataframe(index):
    """空 DataFrame 应原样返回（不抛）。"""
    out = index.apply(pd.DataFrame(columns=["date", "close"]), "000021", fq="hfq")
    assert out.empty


def test_apply_does_not_modify_input(index):
    """apply 不应原地修改 df。"""
    df = _df_with_dates(["2020-01-02"], [20.0])
    before = df.copy(deep=True)
    _ = index.apply(df, "000021", fq="hfq")
    pd.testing.assert_frame_equal(df, before)


def test_apply_base_factor_must_be_positive(index):
    df = _df_with_dates(["2020-01-02"], [10.0])
    with pytest.raises(ValueError, match="base_factor"):
        index.to_qfq(df, "000021", base_factor=0.0)


def test_apply_requires_date_column():
    idx = AdjFactorIndex.from_records(
        [{"code": "000021", "date": "2020-01-02", "adj_factor": 1.0}]
    )
    bad = pd.DataFrame({"open": [1.0], "close": [1.0]})  # 无 date
    with pytest.raises(ValueError, match="date"):
        idx.apply(bad, "000021", fq="hfq")


# ===== Dunder =====

def test_len_and_contains(index):
    assert len(index) == 3
    assert "000021" in index
    assert "BK9999" not in index
