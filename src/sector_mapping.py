"""A 股板块索引（本地 JSON 离线优先）。

Design inspired by free-stockdb MIT © 2026 hello245m.
原仓库路径: pybao/zhibiao.py:BoardIndex + docs/FREE_STOCKDB_AUDIT.md §4.4

核心设计模式：
- 四向索引一次构建（by_code / by_stock / by_name / by_category），后续查询 O(1) 命中
- 类别白名单（concept / sw1 / sw2 / sw3），未知类别抛 ValueError
- 字段投影白名单（BOARD_FIELDS），未知字段抛 ValueError
- 类别前缀的 by_name 索引（避免不同类别同名板块冲突）
- by_stock 不带 symbols（节省内存，避免递归）

数据流：
- 种子：data/sectors/a_stock_sectors.json（metadata，symbols 留空）
- 首次构建：scripts/build_sector_index.py 调用东财拉个股清单 → 写盘
- 后续：本地 JSON 离线加载；如需刷新股票清单重跑 build 脚本
"""
from __future__ import annotations

import json
from collections import defaultdict
from copy import copy
from pathlib import Path
from typing import Any


CATEGORY_MAP = {
    "concept": "概念板块（东财）",
    "sw1": "申万一级",
    "sw2": "申万二级",
    "sw3": "申万三级",
}

BOARD_FIELDS = ("code", "name", "source", "type", "group", "category", "symbols")

FIELD_ALIASES = {
    "symbol": "symbols",
    "symbols": "symbols",
    "symbls": "symbols",  # 拼写容错（free-stockdb 也保留）
    "codelist": "symbols",
}


def _is_stock_code(value: str) -> bool:
    return len(value) == 6 and value.isdigit()


def _stock_code(value: Any) -> str:
    return str(value).strip().split(".")[0]


class SectorIndex:
    """A 股板块索引（仿 free-stockdb BoardIndex）。

    构造时不抛异常（坏数据被静默跳过，但元数据缺失必跳过）；
    类别 / 字段参数在 get() / stocks_for() 时严格校验。
    """

    def __init__(self, rows: list[dict] | None = None) -> None:
        self.boards: list[dict[str, Any]] = []
        self.by_code: dict[str, dict[str, Any]] = {}
        self.by_stock: dict[str, list[dict[str, Any]]] = defaultdict(list)
        self.by_name: dict[str, list[dict[str, Any]]] = defaultdict(list)
        self.by_category: dict[str, list[dict[str, Any]]] = defaultdict(list)
        if rows:
            self._build(rows)

    @classmethod
    def from_file(cls, path: str | Path) -> "SectorIndex":
        """从 JSON 文件加载（顶层需含 sectors 数组）。"""
        p = Path(path)
        if not p.exists():
            raise FileNotFoundError(f"Sector JSON not found: {p}")
        payload = json.loads(p.read_text(encoding="utf-8"))
        rows = payload.get("sectors", [])
        return cls(rows)

    def _build(self, rows: list[dict]) -> None:
        for board in rows:
            if not isinstance(board, dict):
                continue
            code = str(board.get("code", "")).strip()
            name = str(board.get("name", "")).strip()
            category = str(board.get("category", "")).strip()
            if not code or not name or not category:
                continue
            if category not in CATEGORY_MAP:
                continue

            symbols = [
                _stock_code(symbol)
                for symbol in (board.get("symbols") or [])
                if str(symbol).strip()
            ]

            item = {
                **board,
                "code": code,
                "name": name,
                "category": category,
                "symbols": symbols,
            }

            self.boards.append(item)
            self.by_code[code] = item
            self.by_name[f"{category}_{name}"].append(item)
            self.by_category[category].append(item)

            slim = self._board(item, with_symbols=False)
            for stock in symbols:
                self.by_stock[stock].append(slim)

    def get(
        self,
        x: Any = None,
        category: str | None = None,
        fields: str | None = None,
    ) -> Any:
        """板块查询（多态）。

        调用模式：
        - get() / get(None) / get(category="concept") → 该类别全集（带 symbols）
        - get("BK1140") → 按代码单查（带 symbols）
        - get("CPO概念") → 按名称模糊匹配（带 symbols）
        - get("300394") → 股票代码 → 所属板块列表（不带 symbols）
        - get(["600519","000001"], category="sw1", fields="name") → 批量
        """
        cat = self._category(category)
        flds = self._fields(fields)

        if isinstance(x, (list, tuple, set)):
            return {str(item): self.get(item, cat, flds) for item in x}

        if x is None:
            items = self.boards if cat is None else self.by_category.get(cat, [])
            return self._result(items, flds, single=False, with_symbols=True)

        query = str(x).strip()
        if not query:
            return []

        if query in self.by_code:
            return self._result([self.by_code[query]], flds, single=True, with_symbols=True)

        if _is_stock_code(query):
            items = self.by_stock.get(query, [])
            if cat is not None:
                items = [item for item in items if item.get("category") == cat]
            return self._result(items, flds, single=False, with_symbols=False)

        if cat is not None:
            exact = self.by_name.get(f"{cat}_{query}", [])
            if exact:
                return self._result(exact, flds, single=True, with_symbols=True)
            matched = self._match_name(query, cat)
            return self._result(matched, flds, single=False, with_symbols=True)

        matched: list[dict[str, Any]] = []
        for cat_name in CATEGORY_MAP:
            matched.extend(self.by_name.get(f"{cat_name}_{query}", []))
        if not matched:
            matched = self._match_name(query, category=None)
        return self._result(matched, flds, single=False, with_symbols=True)

    def stocks_for(self, x: str) -> list[str]:
        """取板块股票清单（6 位代码列表）。

        接受板块代码 / 板块名（不带类别时跨类别查第一个命中）。
        """
        item = self.by_code.get(x)
        if not item:
            for cat_name in CATEGORY_MAP:
                exact = self.by_name.get(f"{cat_name}_{x}", [])
                if exact:
                    item = exact[0]
                    break
        if not item:
            return []
        return list(item.get("symbols") or [])

    def categories(self) -> list[str]:
        """返回所有出现过的类别。"""
        return list(self.by_category.keys())

    def _result(
        self,
        items: list[dict[str, Any]],
        fields: str | None,
        single: bool,
        with_symbols: bool,
    ) -> Any:
        boards = [self._board(item, with_symbols) for item in items]
        if fields:
            selected = fields.split(",")
            if len(selected) == 1:
                values = [item.get(selected[0]) for item in boards]
            else:
                values = [
                    [item.get(key) for key in selected]
                    for item in boards
                ]
            if single:
                if values:
                    return values[0]
                return [] if selected == ["symbols"] else None
            return values
        if single:
            return boards[0] if boards else {}
        return boards

    def _match_name(self, keyword: str, category: str | None) -> list[dict[str, Any]]:
        items = self.boards if category is None else self.by_category.get(category, [])
        return [item for item in items if keyword in item["name"]]

    def _board(self, item: dict[str, Any], with_symbols: bool) -> dict[str, Any]:
        value = {field: copy(item[field]) for field in BOARD_FIELDS if field in item}
        if not with_symbols:
            value.pop("symbols", None)
        return value

    def _category(self, category: Any) -> str | None:
        if category is None:
            return None
        if isinstance(category, int):
            raise TypeError(
                f"category must be str from {list(CATEGORY_MAP)}, got int={category}"
            )
        text = str(category).strip()
        if text not in CATEGORY_MAP:
            raise ValueError(
                f"unknown category: {text!r} (valid: {list(CATEGORY_MAP)})"
            )
        return text

    def _fields(self, fields: str | None) -> str | None:
        if fields is None:
            return None
        selected: list[str] = []
        for item in str(fields).split(","):
            item = item.strip()
            if not item:
                continue
            item = FIELD_ALIASES.get(item, item)
            if item not in BOARD_FIELDS:
                raise ValueError(
                    f"unknown field: {item!r} (valid: {list(BOARD_FIELDS)})"
                )
            selected.append(item)
        if not selected:
            return None
        return ",".join(selected)

    def __len__(self) -> int:
        return len(self.boards)

    def __contains__(self, code_or_name: str) -> bool:
        if code_or_name in self.by_code:
            return True
        for cat in CATEGORY_MAP:
            if self.by_name.get(f"{cat}_{code_or_name}"):
                return True
        return False
