"""A 股板块索引构建脚本（首次 / 增量更新）。

Design inspired by free-stockdb MIT © 2026 hello245m.
对应文档：docs/FREE_STOCKDB_AUDIT.md §4.4 + §4.7

数据源：东财 push2 接口
- 概念板块 fs=m:90+t:2
- 行业板块 fs=m:90+t:3
- 板块内个股：fs=b:<BOARD_CODE>（f:!2 排除北交所）

输出：data/sectors/a_stock_sectors.json
- version 升级（v1=种子，v2=首次东财拉取，v3+=增量）
- 保留 SW 1-3 占位行不被覆盖
- symbols 字段在 --include-symbols 时填充

设计原则：
- 失败时打印清晰错误并保留旧 JSON（不破坏现状）
- 拉取速率限制（板块间隔 0.05s）避免东财 429
- 合并现有 JSON（首次空 → 完整重写；后续 → 增量化）
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "data" / "sectors" / "a_stock_sectors.json"

BOARD_FIELDS = "f12,f14,f3,f6,f8,f20,f21,f62"
STOCK_FIELDS = "f12,f14"

# 东财 fs 模板
FS_CONCEPT = "m:90+t:2"
FS_INDUSTRY = "m:90+t:3"

DEFAULT_CATEGORIES = {
    "concept": "概念板块（东财）",
    "industry": "东财行业",
    "sw1": "申万一级（占位）",
    "sw2": "申万二级（占位）",
    "sw3": "申万三级（占位）",
}


def request_eastmoney(params: dict, retries: int = 4, timeout: int = 30) -> dict:
    """拉取东财 push2 接口（带重试 + UA）。"""
    url = "https://push2.eastmoney.com/api/qt/clist/get"
    query = urlencode(params)
    request = Request(f"{url}?{query}", headers={"User-Agent": "Mozilla/5.0"})
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


def parse_diff(payload: dict) -> list[dict]:
    diff = payload.get("data", {}).get("diff", [])
    if isinstance(diff, dict):
        return list(diff.values())
    return list(diff or [])


def to_float(value: Any) -> float:
    try:
        if value in {None, "-", ""}:
            return 0.0
        return float(value)
    except Exception:
        return 0.0


def fetch_board_list(source: str) -> list[dict]:
    """拉取板块清单（不含个股，仅 metadata）。"""
    fs_values: list[str]
    if source == "concept":
        fs_values = [FS_CONCEPT]
    elif source == "industry":
        fs_values = [FS_INDUSTRY]
    else:
        fs_values = [FS_CONCEPT, FS_INDUSTRY]

    rows: list[dict] = []
    for fs in fs_values:
        payload = request_eastmoney(
            {
                "pn": "1",
                "pz": "10000",
                "po": "1",
                "np": "1",
                "fid": "f62",
                "fs": fs,
                "fields": BOARD_FIELDS,
            }
        )
        board_type = "concept" if "t:2" in fs else "industry"
        for item in parse_diff(payload):
            code = str(item.get("f12", "")).strip()
            name = str(item.get("f14", "")).strip()
            if not code or not name:
                continue
            rows.append(
                {
                    "code": code,
                    "name": name,
                    "category": board_type,
                    "source": "eastmoney",
                    "group": "东方财富概念"
                    if board_type == "concept"
                    else "东财行业",
                    "symbols": [],
                }
            )
    return rows


def fetch_sector_stocks(board_code: str, board_type: str) -> list[str]:
    """拉取板块内的股票清单（仅股票代码）。"""
    if board_type == "concept":
        fs = f"b:{board_code}+f:!2"
    else:
        fs = f"b:{board_code}"
    try:
        payload = request_eastmoney(
            {
                "pn": "1",
                "pz": "10000",
                "po": "1",
                "np": "1",
                "fid": "f12",
                "fs": fs,
                "fields": STOCK_FIELDS,
            }
        )
    except Exception:
        return []
    symbols: list[str] = []
    for item in parse_diff(payload):
        code = str(item.get("f12", "")).strip()
        if code.isdigit() and len(code) == 6:
            symbols.append(code)
    return symbols


def merge_existing(
    fresh: list[dict],
    existing: dict,
) -> list[dict]:
    """合并东财新数据 + 现有 JSON（保留 SW 占位 + 旧 symbols）。"""
    existing_sectors = existing.get("sectors", [])
    # 保留 SW 占位行（不被东财覆盖）
    sw_placeholders = [
        s
        for s in existing_sectors
        if str(s.get("source", "")).startswith("sw_placeholder")
    ]
    # 按 code 索引现有数据（含旧 symbols）
    prev_by_code: dict[str, dict] = {
        str(s.get("code", "")).strip(): s
        for s in existing_sectors
        if s.get("code")
    }
    seen: set[str] = set()
    merged: list[dict] = []
    for row in fresh:
        code = row["code"]
        if code in seen:
            continue
        seen.add(code)
        # 保留旧 symbols（不破坏已有清单）
        prev = prev_by_code.get(code)
        if prev and prev.get("symbols"):
            row["symbols"] = list(prev["symbols"])
        merged.append(row)
    # 把 SW 占位追加
    for ph in sw_placeholders:
        code = ph.get("code", "")
        if code and code not in seen:
            merged.append(ph)
    return merged


def main(argv: list[str] | None = None) -> int:
    """构建入口（argv 可注入便于测试；None 时读 sys.argv[1:]）。"""
    parser = argparse.ArgumentParser(description="A 股板块索引构建（东财）")
    parser.add_argument(
        "--output", default=str(DEFAULT_OUTPUT), help="输出 JSON 路径"
    )
    parser.add_argument(
        "--source",
        choices=["concept", "industry", "all"],
        default="all",
        help="拉取范围",
    )
    parser.add_argument(
        "--include-symbols",
        action="store_true",
        help="拉取每个板块的个股清单（耗时较长）",
    )
    parser.add_argument(
        "--max-symbols",
        type=int,
        default=200,
        help="每板块个股上限（防超大板块）",
    )
    parser.add_argument(
        "--sleep-ms",
        type=int,
        default=50,
        help="板块间隔毫秒（防 429）",
    )
    args = parser.parse_args(argv)

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)

    existing: dict = {}
    if output.exists():
        try:
            existing = json.loads(output.read_text(encoding="utf-8"))
        except Exception as exc:
            print(f"[build] WARN: 现有 JSON 解析失败: {exc}，将整体重建", file=sys.stderr)
            existing = {}

    print(f"[build] 拉取 source={args.source} ...", file=sys.stderr)
    fresh: list[dict] = []
    if args.source in {"concept", "all"}:
        print("[build] fetching concept boards...", file=sys.stderr)
        fresh.extend(fetch_board_list("concept"))
    if args.source in {"industry", "all"}:
        print("[build] fetching industry boards...", file=sys.stderr)
        fresh.extend(fetch_board_list("industry"))

    merged = merge_existing(fresh, existing)
    print(f"[build] 合并后 {len(merged)} 个板块（{len(fresh)} fresh + SW 占位）", file=sys.stderr)

    if args.include_symbols:
        target_count = sum(
            1
            for row in merged
            if not str(row.get("source", "")).startswith("sw_placeholder")
        )
        print(
            f"[build] 拉取个股清单（{target_count} 个板块，每板块限 {args.max_symbols}）...",
            file=sys.stderr,
        )
        for i, row in enumerate(merged, 1):
            if str(row.get("source", "")).startswith("sw_placeholder"):
                continue
            board_type = row.get("category", "")
            try:
                symbols = fetch_sector_stocks(row["code"], board_type)
            except Exception as exc:
                print(
                    f"  [{i}/{len(merged)}] {row['code']} {row['name']} FAIL: {exc}",
                    file=sys.stderr,
                )
                continue
            if symbols:
                row["symbols"] = symbols[: args.max_symbols]
            if i % 50 == 0:
                print(f"  [{i}/{len(merged)}] done", file=sys.stderr)
            time.sleep(args.sleep_ms / 1000.0)

    # 升级 version：现有 v1 → 升级到 v2；现有 v2 → v3 ...
    old_version = str(existing.get("version", "1"))
    try:
        old_num = int(old_version)
        new_version = str(max(old_num + 1, 2)) if not old_version == "1" else "2"
    except ValueError:
        new_version = "2"

    payload = {
        "version": new_version,
        "as_of": datetime.now().strftime("%Y-%m-%d"),
        "note": "A 股板块 metadata 由东财推送接口生成。Design inspired by free-stockdb MIT © 2026 hello245m。",
        "source": "eastmoney + sw_placeholder",
        "categories": existing.get("categories", DEFAULT_CATEGORIES),
        "sectors": merged,
    }
    output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(
        f"[build] wrote {output} (version={new_version}, sectors={len(merged)})",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
