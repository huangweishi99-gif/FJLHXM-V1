"""A 股批量查询 API（仿 free-stockdb get_data 设计）。

Design inspired by free-stockdb MIT © 2026 hello245m.
对应文档：docs/FREE_STOCKDB_AUDIT.md §4.5

接口：
- BulkQuery.get_data(code, start, end, frequency, fields, limit, desc, as_df, fq)
    → DataFrame | list[dict]
- BulkQuery.get_data_async(...) → awaitable
  （用 asyncio.to_thread 包装 get_data，便于多只代码并发）

数据流：
- DB 优先（data/market_data.sqlite 的 bars 表，market="A_STOCK"）
- 回落 cache（data/a_stock/{code}_{tf}_qfq.csv）
- 复权折算：fq='qfq' 原样返回；'hfq' / 'none' 用 AdjFactorIndex 折算
- 缺 adj_factor 时 raise AdjFactorMissingError

不与回测/事件写入耦合（仅数据查询；不动 strategy / 不动 sqlite 写入）。
"""
from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import pandas as pd

from adj_factor import AdjFactorIndex, AdjFactorMissingError
from market_data_resolve_a_stock import resolve_a_stock_csv


DEFAULT_FIELDS = ("date", "open", "high", "low", "close", "volume")
VALID_FQ = ("qfq", "hfq", "none")

TIMEFRAME_ALIASES = {
    "1d": "1D", "1D": "1D", "D1": "1D", "DAY": "1D", "DAILY": "1D", "日线": "1D",
    "1h": "1H", "1H": "1H", "H1": "1H", "60m": "1H", "60M": "1H", "60MIN": "1H", "60分钟": "1H",
    "15m": "15m", "15M": "15m", "M15": "15m", "15MIN": "15m", "15分钟": "15m",
    "5m": "5m", "5M": "5m", "M5": "5m", "5MIN": "5m", "5分钟": "5m",
}

FIELD_ALIASES = {
    "date": "date", "datetime": "date", "time": "date", "时间": "date", "日期": "date",
    "o": "open", "open": "open", "开盘": "open", "开盘价": "open",
    "h": "high", "high": "high", "最高": "high", "最高价": "high",
    "l": "low", "low": "low", "最低": "low", "最低价": "low",
    "c": "close", "close": "close", "收盘": "close", "收盘价": "close",
    "v": "volume", "vol": "volume", "volume": "volume", "成交量": "volume",
    "amount": "amount", "成交额": "amount", "a": "amount",
    "pct_chg": "pct_chg", "pct": "pct_chg", "涨跌幅": "pct_chg",
    "turnover": "turnover", "换手率": "turnover",
}


def normalize_frequency(value: str) -> str:
    text = str(value).strip()
    return TIMEFRAME_ALIASES.get(text, text)


def normalize_field(value: str) -> str:
    text = str(value).strip().lower()
    canonical = FIELD_ALIASES.get(text)
    if canonical is None:
        raise ValueError(f"unknown field: {value!r}")
    return canonical


def project_fields(frame: pd.DataFrame, fields: list[str]) -> pd.DataFrame:
    out = frame.copy()
    picked = [f for f in fields if f in out.columns]
    if not picked:
        raise ValueError(
            f"no fields in frame: requested={fields}, actual={list(out.columns)}"
        )
    return out[picked]


def filter_by_date(
    frame: pd.DataFrame, start: str = "", end: str = ""
) -> pd.DataFrame:
    if frame.empty:
        return frame
    out = frame.copy()
    out["date"] = pd.to_datetime(out["date"], errors="coerce")
    out = out.dropna(subset=["date"])
    if start:
        s = pd.Timestamp(start)
        out = out[out["date"] >= s]
    if end:
        e = pd.Timestamp(end)
        out = out[out["date"] <= e]
    return out.reset_index(drop=True)


class BulkQuery:
    """A 股批量查询 API（仿 free-stockdb get_data）。"""

    def __init__(
        self,
        *,
        cache_dir: str | Path = "data/a_stock",
        db_path: str | Path = "data/market_data.sqlite",
        adj_factor_index: AdjFactorIndex | None = None,
        adj_factor_csv: str | Path = "data/a_stock_adj_factors.csv",
    ) -> None:
        self.cache_dir = Path(cache_dir)
        self.db_path = str(db_path)
        self.adj_factor_csv = str(adj_factor_csv)
        self._adj_factor: AdjFactorIndex | None = adj_factor_index
        self._adj_factor_loaded = adj_factor_index is not None

    def _ensure_adj_factor(self) -> AdjFactorIndex | None:
        if self._adj_factor_loaded:
            return self._adj_factor
        p = Path(self.adj_factor_csv)
        if not p.exists():
            self._adj_factor_loaded = True
            self._adj_factor = None
            return None
        try:
            self._adj_factor = AdjFactorIndex.from_csv(p)
        except Exception:
            self._adj_factor = None
        self._adj_factor_loaded = True
        return self._adj_factor

    def get_data(
        self,
        code: str,
        start: str = "",
        end: str = "",
        frequency: str = "1d",
        fields: list[str] | None = None,
        limit: int | None = None,
        desc: bool = False,
        as_df: bool = True,
        fq: str = "qfq",
    ) -> pd.DataFrame | list[dict]:
        """同步批量查询 A 股 K 线。"""
        if fq not in VALID_FQ:
            raise ValueError(f"unknown fq: {fq!r} (valid: {list(VALID_FQ)})")
        normalized_tf = normalize_frequency(frequency)
        cache_path = self.cache_dir / f"{code.upper().zfill(6)}_{normalized_tf}_qfq.csv"
        csv_path, source = resolve_a_stock_csv(
            code,
            normalized_tf,
            cache_path,
            db_path=self.db_path,
        )
        if source == "missing" or not csv_path.exists():
            raise FileNotFoundError(
                f"A_STOCK {code} {normalized_tf}: no DB and no cache ({csv_path})"
            )

        try:
            frame = pd.read_csv(csv_path, encoding="utf-8-sig")
        except UnicodeDecodeError:
            frame = pd.read_csv(csv_path, encoding="gbk")

        if fq != "qfq":
            adj = self._ensure_adj_factor()
            if adj is None:
                raise AdjFactorMissingError(code)
            frame = adj.apply(frame, code, fq)

        frame = filter_by_date(frame, start=start, end=end)
        if not frame.empty and "date" in frame.columns:
            frame = frame.sort_values(
                "date", ascending=not desc
            ).reset_index(drop=True)
            if limit is not None and limit > 0 and len(frame) > limit:
                if desc:
                    frame = frame.head(limit)
                else:
                    frame = frame.tail(limit).reset_index(drop=True)

        if fields:
            fields_norm = [normalize_field(f) for f in fields]
            frame = project_fields(frame, fields_norm)

        if as_df:
            return frame
        return frame.to_dict("records")

    async def get_data_async(
        self,
        code: str,
        start: str = "",
        end: str = "",
        frequency: str = "1d",
        fields: list[str] | None = None,
        limit: int | None = None,
        desc: bool = False,
        as_df: bool = True,
        fq: str = "qfq",
    ) -> pd.DataFrame | list[dict]:
        """异步版本（asyncio.to_thread 包装 get_data，便于多只代码并发）。

        典型用法：
            results = await asyncio.gather(*[
                bq.get_data_async(code, frequency="1d")
                for code in codes
            ])
        """
        return await asyncio.to_thread(
            self.get_data,
            code,
            start,
            end,
            frequency,
            fields,
            limit,
            desc,
            as_df,
            fq,
        )
