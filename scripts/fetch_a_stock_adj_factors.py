"""A 股复权因子拉取脚本（首次 / 增量更新）。

Design inspired by free-stockdb MIT © 2026 hello245m.
对应文档：docs/FREE_STOCKDB_AUDIT.md §4.5

数据源：东财 push2his stock kline 接口
- URL: https://push2his.eastmoney.com/api/qt/stock/kline/get
- fields2 = f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61
  - f51 = date, f52 = open, f53 = close, f54 = high, f55 = low,
    f56 = volume, f57 = amount, f58 = amplitude, f59 = turnover(成交额) OR adj_factor（依赖 fqt）
  - 注：当 fqt=0（不复权）时 f59 实为 turnover；adj_factor 字段在 f60 / f61 附近
- 实际字段定义以东财返回为准；本脚本只取 [0]=date + [10]=adj_factor_位置（按 split(',') 索引）。
  解析失败时记录失败代码、不抛错。

secid 规则：
- 上交所（6/9 开头）→ 1.{code}
- 深交所 + 北交所（0/2/3/4/8 开头）→ 0.{code}

输出：data/a_stock_adj_factors.csv
- 列：code, date, adj_factor
- 已有记录保留（按 code+date 去重）

设计原则：
- 失败时打 ERROR 但继续（不阻断整个拉取）
- 速率限制（--sleep-ms）防东财 429
- main(argv=None) 可注入参数便于测试
- 不主动跑（仅当用户显式调用时拉取）
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "data" / "a_stock_adj_factors.csv"

KLINE_FIELDS = "f1,f2,f3,f4,f5,f6"
KLINE_FIELDS2 = "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61"
FQ_TYPE = 0  # 0=不复权, 1=前复权, 2=后复权
KL_TYPE = 101  # 101=日线, 102=周线, 103=月线


def request_eastmoney(params: dict, retries: int = 4, timeout: int = 30) -> dict:
    url = "https://push2his.eastmoney.com/api/qt/stock/kline/get"
    query = urlencode(params)
    request = Request(
        f"{url}?{query}",
        headers={
            "User-Agent": "Mozilla/5.0",
            "Referer": "https://quote.eastmoney.com/",
        },
    )
    last_exc: Exception | None = None
    for attempt in range(retries):
        try:
            with urlopen(request, timeout=timeout) as response:
                payload = json.loads(response.read().decode("utf-8"))
            if payload.get("data") is None:
                raise ValueError(f"Eastmoney returned empty data: {payload}")
            return payload
        except Exception as exc:
            last_exc = exc
            time.sleep(0.8 * (attempt + 1))
    raise RuntimeError(f"Eastmoney request failed: {last_exc}") from last_exc


def detect_secid(code: str) -> str:
    """根据股票代码判断东财 secid 前缀。"""
    code = str(code).strip().zfill(6)
    if code.startswith(("6", "9")):
        return f"1.{code}"
    if code.startswith(("0", "2", "3", "4", "8")):
        return f"0.{code}"
    raise ValueError(f"无法判断 secid: {code}（沪 6/9 / 深 0/2/3/4/8）")


def parse_kline_payload(payload: dict, code: str, adj_index: int = 10) -> list[dict]:
    """解析东财 kline payload 为 adj_factor 记录。

    adj_index=10 默认取 f60；fqt=0 时 f60 通常是 adj_factor（具体以东财返回为准）。
    """
    klines = payload.get("data", {}).get("klines", [])
    out: list[dict] = []
    for line in klines:
        parts = line.split(",")
        if len(parts) <= adj_index:
            continue
        date_text = parts[0]
        adj_text = parts[adj_index]
        try:
            factor = float(adj_text)
        except (ValueError, IndexError):
            continue
        out.append({"code": code, "date": date_text, "adj_factor": factor})
    return out


def fetch_adj_factors(code: str, *, adj_index: int = 10) -> list[dict]:
    """拉取单只代码的 adj_factor 历史。"""
    secid = detect_secid(code)
    params = {
        "secid": secid,
        "ut": "fa5fd1943c7b386f172d6893dbfba10b",
        "fields1": KLINE_FIELDS,
        "fields2": KLINE_FIELDS2,
        "klt": str(KL_TYPE),
        "fqt": str(FQ_TYPE),
        "beg": "0",
        "end": "20500101",
        "lmt": "10000",
    }
    payload = request_eastmoney(params)
    return parse_kline_payload(payload, code, adj_index=adj_index)


def merge_into_csv(records: list[dict], output: Path) -> int:
    """合并新记录到现有 CSV（去重：code+date 唯一）。"""
    existing: dict[tuple[str, str], dict] = {}
    if output.exists():
        with output.open("r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                key = (
                    str(row.get("code", "")).strip().zfill(6),
                    str(row.get("date", "")).strip(),
                )
                try:
                    factor = float(row.get("adj_factor", "0") or 0)
                except ValueError:
                    factor = 0.0
                existing[key] = {
                    "code": key[0],
                    "date": key[1],
                    "adj_factor": factor,
                }
    for row in records:
        key = (
            str(row["code"]).strip().zfill(6),
            str(row["date"]).strip(),
        )
        try:
            factor = float(row["adj_factor"])
        except (KeyError, ValueError):
            continue
        existing[key] = {"code": key[0], "date": key[1], "adj_factor": factor}
    output.parent.mkdir(parents=True, exist_ok=True)
    items = sorted(existing.values(), key=lambda item: (item["code"], item["date"]))
    with output.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["code", "date", "adj_factor"])
        writer.writeheader()
        for item in items:
            writer.writerow(item)
    return len(items)


def main(argv: list[str] | None = None) -> int:
    """拉取入口（argv 可注入便于测试；None 时读 sys.argv[1:]）。"""
    parser = argparse.ArgumentParser(description="A 股复权因子拉取（东财）")
    parser.add_argument(
        "--codes",
        default="",
        help="逗号分隔的股票代码列表（空 = 拉 data/a_stock 目录里所有 6 位代码）",
    )
    parser.add_argument(
        "--output", default=str(DEFAULT_OUTPUT), help="输出 CSV 路径"
    )
    parser.add_argument(
        "--sleep-ms", type=int, default=200, help="代码间隔毫秒（防 429）"
    )
    parser.add_argument(
        "--adj-index",
        type=int,
        default=10,
        help="kline split(',') 中 adj_factor 字段索引（默认 10=f60）",
    )
    args = parser.parse_args(argv)

    if args.codes.strip():
        codes = [c.strip().zfill(6) for c in args.codes.split(",") if c.strip()]
    else:
        a_stock_dir = ROOT / "data" / "a_stock"
        codes = sorted(
            {
                p.name.split("_", 1)[0]
                for p in a_stock_dir.glob("*_1D_qfq.csv")
                if p.name.split("_", 1)[0].isdigit()
            }
        )
    if not codes:
        print("[fetch_adj] 未指定 codes 且 data/a_stock 为空", file=sys.stderr)
        return 1

    print(
        f"[fetch_adj] 拉取 {len(codes)} 个代码 → {args.output}", file=sys.stderr
    )
    output = Path(args.output)
    all_records: list[dict] = []
    failed: list[tuple[str, str]] = []
    for i, code in enumerate(codes, 1):
        try:
            records = fetch_adj_factors(code, adj_index=args.adj_index)
            all_records.extend(records)
            print(
                f"  [{i}/{len(codes)}] {code} ok ({len(records)} 条)",
                file=sys.stderr,
            )
        except Exception as exc:
            failed.append((code, str(exc)))
            print(
                f"  [{i}/{len(codes)}] {code} FAIL: {exc}", file=sys.stderr
            )
        time.sleep(args.sleep_ms / 1000.0)
    total = merge_into_csv(all_records, output)
    print(
        f"[fetch_adj] wrote {output} (total={total}, new={len(all_records)}, failed={len(failed)})",
        file=sys.stderr,
    )
    if failed:
        print("[fetch_adj] 失败列表：", file=sys.stderr)
        for code, exc in failed:
            print(f"  {code}: {exc}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
