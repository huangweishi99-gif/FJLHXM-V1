"""fetch_a_stock_adj_factors.py 单元测试（mock 网络，不连真实东财）。

Design inspired by free-stockdb MIT © 2026 hello245m.
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path

import pytest


SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))


@pytest.fixture
def fetch_module():
    import importlib
    if "fetch_a_stock_adj_factors" in sys.modules:
        del sys.modules["fetch_a_stock_adj_factors"]
    return importlib.import_module("fetch_a_stock_adj_factors")


# ===== 纯函数：detect_secid =====

def test_detect_secid_sh(fetch_module):
    """6/9 开头 → 1.{code}。"""
    assert fetch_module.detect_secid("600036") == "1.600036"
    assert fetch_module.detect_secid("900901") == "1.900901"
    # 不补 0
    assert fetch_module.detect_secid("000001") == "0.000001"


def test_detect_secid_sz(fetch_module):
    """0/2/3 开头 → 0.{code}。"""
    assert fetch_module.detect_secid("000001") == "0.000001"
    assert fetch_module.detect_secid("300502") == "0.300502"
    assert fetch_module.detect_secid("200001") == "0.200001"


def test_detect_secid_bj(fetch_module):
    """4/8 开头 → 0.{code}（北交所）。"""
    assert fetch_module.detect_secid("430001") == "0.430001"
    assert fetch_module.detect_secid("830001") == "0.830001"


def test_detect_secid_invalid(fetch_module):
    """无法判断的 code → ValueError。"""
    with pytest.raises(ValueError, match="无法判断 secid"):
        fetch_module.detect_secid("123456")  # 1 开头不在白名单
    with pytest.raises(ValueError, match="无法判断 secid"):
        fetch_module.detect_secid("789abc")  # 非数字


def test_detect_secid_zfill(fetch_module):
    """5 位代码 zfill 后 6 位再判前缀（zfill 改变首位不会误判：补 0 后变 0 开头 → 深交所）。"""
    # "60036" zfill → "060036" → 0 开头 → 深交所
    assert fetch_module.detect_secid("60036") == "0.060036"
    # "00036" zfill → "000036" → 0 开头 → 深交所
    assert fetch_module.detect_secid("00036") == "0.000036"


# ===== 纯函数：parse_kline_payload =====

def test_parse_kline_payload_basic(fetch_module):
    payload = {
        "data": {
            "klines": [
                "2020-01-02,10.0,10.5,10.2,10.4,1000,1e7,1.0,0.5,1.0,1.000",
                "2020-01-03,10.4,10.6,10.3,10.5,1200,1.2e7,1.0,0.5,1.0,0.990",
            ]
        }
    }
    records = fetch_module.parse_kline_payload(payload, "000021", adj_index=10)
    assert len(records) == 2
    assert records[0] == {"code": "000021", "date": "2020-01-02", "adj_factor": 1.0}
    assert records[1]["adj_factor"] == 0.990


def test_parse_kline_payload_short_line_skipped(fetch_module):
    payload = {
        "data": {
            "klines": [
                "2020-01-02,10.0,10.5,10.2,10.4,1000",  # 6 列，adj_index=10 越界
                "2020-01-03,10.4,10.6,10.3,10.5,1200,1.2e7,1.0,0.5,1.0,0.950",
            ]
        }
    }
    records = fetch_module.parse_kline_payload(payload, "000021", adj_index=10)
    assert len(records) == 1
    assert records[0]["date"] == "2020-01-03"


def test_parse_kline_payload_invalid_factor_skipped(fetch_module):
    payload = {
        "data": {
            "klines": [
                "2020-01-02,10.0,10.5,10.2,10.4,1000,1e7,1.0,0.5,1.0,abc",  # 非数字
                "2020-01-03,10.4,10.6,10.3,10.5,1200,1.2e7,1.0,0.5,1.0,0.950",
            ]
        }
    }
    records = fetch_module.parse_kline_payload(payload, "000021", adj_index=10)
    assert len(records) == 1
    assert records[0]["date"] == "2020-01-03"


def test_parse_kline_payload_custom_adj_index(fetch_module):
    payload = {
        "data": {
            "klines": [
                "2020-01-02,10.0,10.5,10.2,10.4,1000,1e7,1.0,0.5,1.0,0.88",
            ]
        }
    }
    # adj_index=9 → f59
    records = fetch_module.parse_kline_payload(payload, "000021", adj_index=9)
    assert records[0]["adj_factor"] == 1.0  # f59 = 1.0


# ===== 纯函数：merge_into_csv =====

def test_merge_into_csv_no_existing(tmp_path: Path, fetch_module):
    records = [
        {"code": "000021", "date": "2020-01-02", "adj_factor": 0.5},
        {"code": "000021", "date": "2020-01-03", "adj_factor": 0.6},
    ]
    out = tmp_path / "adj.csv"
    n = fetch_module.merge_into_csv(records, out)
    assert n == 2
    rows = list(csv.DictReader(out.open("r", encoding="utf-8")))
    assert len(rows) == 2
    assert rows[0]["code"] == "000021"


def test_merge_into_csv_dedup_by_code_date(tmp_path: Path, fetch_module):
    out = tmp_path / "adj.csv"
    out.write_text("code,date,adj_factor\n000021,2020-01-02,0.5\n", encoding="utf-8")
    new_records = [
        {"code": "000021", "date": "2020-01-02", "adj_factor": 0.9},  # 同日 → 覆盖
        {"code": "000021", "date": "2020-01-03", "adj_factor": 0.6},  # 新增
    ]
    n = fetch_module.merge_into_csv(new_records, out)
    assert n == 2
    rows = list(csv.DictReader(out.open("r", encoding="utf-8")))
    # 覆盖后 0.9
    by_date = {r["date"]: float(r["adj_factor"]) for r in rows}
    assert by_date["2020-01-02"] == 0.9
    assert by_date["2020-01-03"] == 0.6


def test_merge_into_csv_invalid_factor_skipped(tmp_path: Path, fetch_module):
    out = tmp_path / "adj.csv"
    new_records = [
        {"code": "000021", "date": "2020-01-02", "adj_factor": "abc"},
        {"code": "000021", "date": "2020-01-03", "adj_factor": 0.5},
    ]
    n = fetch_module.merge_into_csv(new_records, out)
    # 1 条合法
    assert n == 1


# ===== 集成测试：mock request_eastmoney 跑 main() =====

def _mock_request_factory(per_code_payload: dict | None = None):
    """per_code_payload: {code: payload_dict}；默认所有 code 返回同一 payload。"""
    default = {
        "data": {
            "klines": [
                "2020-01-02,10.0,10.5,10.2,10.4,1000,1e7,1.0,0.5,1.0,1.000",
                "2020-01-03,10.4,10.6,10.3,10.5,1200,1.2e7,1.0,0.5,1.0,0.990",
            ]
        }
    }

    def _mock(params, retries=4, timeout=30):
        code = params.get("secid", "").split(".")[-1]
        if per_code_payload and code in per_code_payload:
            return per_code_payload[code]
        return default

    return _mock


def test_main_with_codes_arg(fetch_module, tmp_path, monkeypatch):
    out = tmp_path / "adj.csv"
    monkeypatch.setattr(fetch_module, "request_eastmoney", _mock_request_factory())
    rc = fetch_module.main(["--codes", "000021,600036", "--output", str(out)])
    assert rc == 0
    rows = list(csv.DictReader(out.open("r", encoding="utf-8")))
    codes = {r["code"] for r in rows}
    assert codes == {"000021", "600036"}
    # 每个 code 2 条 → 4 行
    assert len(rows) == 4


def test_main_no_codes_no_a_stock_dir(fetch_module, tmp_path, monkeypatch, capsys):
    """未指定 codes + data/a_stock 为空 → 退出码 1 + 提示。"""
    # monkeypatch ROOT 路径不太方便，直接传 --codes "" 是等价的
    rc = fetch_module.main(["--codes", "", "--output", str(tmp_path / "adj.csv")])
    assert rc == 1
    captured = capsys.readouterr()
    assert "未指定 codes" in captured.err


def test_main_failed_codes_continue(fetch_module, tmp_path, monkeypatch, capsys):
    """失败的 code 不阻断其他 code。"""
    out = tmp_path / "adj.csv"

    def _mock_partial(params, retries=4, timeout=30):
        if params.get("secid", "").endswith("999999"):
            raise RuntimeError("simulated failure")
        return {"data": {"klines": ["2020-01-02,10,11,10,10.5,100,1e6,1,0,1,0.5"]}}

    monkeypatch.setattr(fetch_module, "request_eastmoney", _mock_partial)
    rc = fetch_module.main(["--codes", "000021,999999,600036", "--output", str(out)])
    assert rc == 0
    rows = list(csv.DictReader(out.open("r", encoding="utf-8")))
    codes = {r["code"] for r in rows}
    assert "000021" in codes
    assert "600036" in codes
    assert "999999" not in codes
    captured = capsys.readouterr()
    assert "失败列表" in captured.err


def test_main_default_codes_from_a_stock_dir(
    fetch_module, tmp_path, monkeypatch
):
    """未指定 codes → 自动从 data/a_stock 目录提取 6 位代码。"""
    # 创建临时 a_stock 目录结构
    a_stock = tmp_path / "data" / "a_stock"
    a_stock.mkdir(parents=True)
    (a_stock / "000021_1D_qfq.csv").write_text("date,close\n2020-01-02,10\n")
    (a_stock / "600036_1D_qfq.csv").write_text("date,close\n2020-01-02,20\n")
    (a_stock / "300502_1D_qfq.csv").write_text("date,close\n2020-01-02,30\n")
    # 不属于 1D_qfq 的文件应被忽略
    (a_stock / "000021_60m_qfq.csv").write_text("date,close\n2020-01-02,10\n")

    # 用 --output 临时 + monkeypatch ROOT 来重定向
    import scripts.fetch_a_stock_adj_factors as mod
    out = tmp_path / "adj.csv"
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    monkeypatch.setattr(mod, "request_eastmoney", _mock_request_factory())
    rc = mod.main(["--output", str(out)])
    assert rc == 0
    rows = list(csv.DictReader(out.open("r", encoding="utf-8")))
    codes = {r["code"] for r in rows}
    # 60m 文件被忽略 → 3 个 code
    assert codes == {"000021", "600036", "300502"}
    # 每个 code 2 条 → 6 行
    assert len(rows) == 6
