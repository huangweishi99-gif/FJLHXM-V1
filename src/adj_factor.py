"""A 股复权因子索引（仿 free-stockdb AdjFactorIndex 设计）。

Design inspired by free-stockdb MIT © 2026 hello245m.
对应文档：docs/FREE_STOCKDB_AUDIT.md §4.5

复权约定（东财 push2 接口口径，已固化在 _apply 内）：
- adj_factor[t] = 累计复权因子（最新日因子 = 1.0；基准日 = 当下）
- qfq_close[t] = none_close[t] / adj_factor[t]   （前复权）
- hfq_close[t] = none_close[t] × 1.0 = none_close[t]（后复权；最新一日与不复权等价）
- to_qfq(原始 none df) = none × (base_factor / adj_factor[t])
- to_hfq(qfq df) = qfq × adj_factor[t]
- to_none(qfq df) = qfq × adj_factor[t]

数据格式（data/a_stock_adj_factors.csv）：
  code,date,adj_factor
  000021,2020-01-02,0.92
  000021,2020-12-31,0.95
  000021,2024-01-02,1.00
  ...

数据流：
- 拉取：scripts/fetch_a_stock_adj_factors.py（仿 build_sector_index.py 风格）
- 加载：AdjFactorIndex.from_csv(path)
- 应用：AdjFactorIndex.to_qfq(df, code) / to_hfq(df, code) / to_none(df, code)
- 缺数据：raise AdjFactorMissingError（不静默）

设计原则：
- 纯函数 + 类，不拉取网络
- 内存索引：dict[code, list[(date, factor)]]，按日期升序
- 异常：AdjFactorMissingError 携带 code/区间/缺失日期前 5 个
- 不与回测/数据库强耦合（无 pandas 之外的依赖）
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path
from typing import Iterable

import pandas as pd


class AdjFactorMissingError(KeyError):
    """复权因子缺失异常。"""

    def __init__(
        self,
        code: str,
        start: str | None = None,
        end: str | None = None,
        missing_dates: list[date] | None = None,
    ) -> None:
        self.code = code
        self.start = start
        self.end = end
        self.missing_dates: list[date] = missing_dates or []
        msg = f"adj_factor missing for code={code}"
        if start or end:
            msg += f" range=[{start},{end}]"
        if self.missing_dates:
            preview = self.missing_dates[:5]
            tail = "..." if len(self.missing_dates) > 5 else ""
            msg += f" (missing dates: {[d.isoformat() for d in preview]}{tail})"
        super().__init__(msg)


def _to_date(value: date | str | pd.Timestamp) -> date:
    if isinstance(value, date) and not isinstance(value, pd.Timestamp):
        return value
    return pd.Timestamp(value).date()


@dataclass
class AdjFactorIndex:
    """A 股复权因子内存索引（仿 free-stockdb AdjFactorIndex）。"""

    factors: dict[str, list[tuple[date, float]]] = field(default_factory=dict)

    # ===== 构造 =====

    @classmethod
    def empty(cls) -> "AdjFactorIndex":
        return cls()

    @classmethod
    def from_csv(cls, path: str | Path) -> "AdjFactorIndex":
        """从 CSV 加载。列：code, date, adj_factor。"""
        p = Path(path)
        if not p.exists():
            raise FileNotFoundError(f"adj_factor CSV not found: {p}")
        try:
            frame = pd.read_csv(p)
        except Exception as exc:
            raise ValueError(f"adj_factor CSV 解析失败 ({p}): {exc}") from exc
        required = {"code", "date", "adj_factor"}
        if not required.issubset(set(frame.columns)):
            raise ValueError(
                f"adj_factor CSV 缺必要列 {sorted(required)}，实际 {list(frame.columns)}"
            )
        idx = cls()
        for row in frame.itertuples(index=False):
            try:
                code = str(row.code).strip().zfill(6)
                d = _to_date(row.date)
                factor = float(row.adj_factor)
            except (AttributeError, ValueError) as exc:
                raise ValueError(f"adj_factor CSV 解析行失败: {row} ({exc})") from exc
            idx.factors.setdefault(code, []).append((d, factor))
        # 排序去重
        for code in idx.factors:
            seen: set[date] = set()
            uniq: list[tuple[date, float]] = []
            for d, f in sorted(idx.factors[code], key=lambda item: item[0]):
                if d in seen:
                    continue
                seen.add(d)
                uniq.append((d, f))
            idx.factors[code] = uniq
        return idx

    @classmethod
    def from_records(cls, records: Iterable[dict]) -> "AdjFactorIndex":
        """从 record 列表加载（{code, date, adj_factor} dicts）。"""
        idx = cls()
        for row in records:
            code = str(row["code"]).strip().zfill(6)
            d = _to_date(row["date"])
            factor = float(row["adj_factor"])
            idx.factors.setdefault(code, []).append((d, factor))
        for code in idx.factors:
            idx.factors[code] = sorted(
                {(d, f) for d, f in idx.factors[code]}, key=lambda item: item[0]
            )
        return idx

    # ===== 状态查询 =====

    def __len__(self) -> int:
        return len(self.factors)

    def __contains__(self, code: str) -> bool:
        return str(code).zfill(6) in self.factors

    def codes(self) -> list[str]:
        return list(self.factors.keys())

    def has(self, code: str) -> bool:
        return str(code).zfill(6) in self.factors

    def count(self, code: str) -> int:
        return len(self.factors.get(str(code).zfill(6), []))

    def latest(self, code: str) -> tuple[date, float] | None:
        items = self.factors.get(str(code).zfill(6), [])
        return items[-1] if items else None

    def earliest(self, code: str) -> tuple[date, float] | None:
        items = self.factors.get(str(code).zfill(6), [])
        return items[0] if items else None

    def factor_on(self, code: str, dt: date | str) -> float | None:
        """某日因子（找不到返回 None）。"""
        target = _to_date(dt)
        for d, f in self.factors.get(str(code).zfill(6), []):
            if d == target:
                return f
        return None

    def range(
        self, code: str, start: date | str, end: date | str
    ) -> list[tuple[date, float]]:
        """区间内因子列表（包含 start/end 当日）。"""
        s = _to_date(start)
        e = _to_date(end)
        if s > e:
            return []
        return [
            (d, f)
            for d, f in self.factors.get(str(code).zfill(6), [])
            if s <= d <= e
        ]

    def missing(
        self, code: str, start: date | str, end: date | str
    ) -> list[date]:
        """区间内缺失因子的工作日列表。"""
        s = _to_date(start)
        e = _to_date(end)
        if s > e:
            return []
        factors = self.factors.get(str(code).zfill(6), [])
        present = {d for d, _ in factors}
        missing: list[date] = []
        cur = s
        while cur <= e:
            if cur.weekday() < 5 and cur not in present:
                missing.append(cur)
            cur += timedelta(days=1)
        return missing

    def is_full(
        self, code: str, start: date | str, end: date | str
    ) -> bool:
        """区间内每个工作日都有因子。"""
        return len(self.missing(code, start, end)) == 0 and self.has(code)

    # ===== 折算（apply 入口） =====

    def to_qfq(
        self, df: pd.DataFrame, code: str, base_factor: float = 1.0
    ) -> pd.DataFrame:
        """将 df 视为「不复权」折算为前复权 qfq。

        公式：qfq[t] = df[t] × (base_factor / adj_factor[t])
        """
        return self._apply(df, code, "qfq", base_factor)

    def to_hfq(self, df: pd.DataFrame, code: str) -> pd.DataFrame:
        """将 df 视为「qfq」折算为后复权 hfq。

        公式：hfq[t] = df[t] × adj_factor[t]
        """
        return self._apply(df, code, "hfq", base_factor=1.0)

    def to_none(self, df: pd.DataFrame, code: str) -> pd.DataFrame:
        """将 df 视为「qfq」折算为不复权。

        公式：none[t] = df[t] × adj_factor[t]
        """
        return self._apply(df, code, "none", base_factor=1.0)

    def apply(
        self, df: pd.DataFrame, code: str, fq: str, base_factor: float = 1.0
    ) -> pd.DataFrame:
        """统一入口：fq ∈ {"qfq", "hfq", "none"}。"""
        if fq == "qfq":
            return self.to_qfq(df, code, base_factor)
        if fq == "hfq":
            return self.to_hfq(df, code)
        if fq == "none":
            return self.to_none(df, code)
        raise ValueError(f"unknown fq: {fq!r} (valid: qfq / hfq / none)")

    # ===== 内部 =====

    def _apply(
        self, df: pd.DataFrame, code: str, fq: str, base_factor: float
    ) -> pd.DataFrame:
        if df.empty:
            return df.copy()
        code = str(code).zfill(6)
        factors = self.factors.get(code)
        if not factors:
            raise AdjFactorMissingError(code)
        if "date" not in df.columns:
            raise ValueError("df must contain 'date' column")
        if base_factor <= 0:
            raise ValueError(f"base_factor must be > 0, got {base_factor}")

        factor_map: dict[date, float] = {d: f for d, f in factors}
        out = df.copy()
        out["__date__"] = pd.to_datetime(out["date"]).dt.date
        out["__factor__"] = out["__date__"].map(factor_map)

        missing_rows = out["__factor__"].isna()
        if missing_rows.any():
            missing_dates = sorted(
                {d for d in out.loc[missing_rows, "__date__"]}
            )
            raise AdjFactorMissingError(
                code,
                start=str(min(missing_dates)),
                end=str(max(missing_dates)),
                missing_dates=missing_dates,
            )

        if fq in ("hfq", "none"):
            multiplier = out["__factor__"]
        else:  # qfq
            multiplier = base_factor / out["__factor__"]

        for column in ("open", "high", "low", "close"):
            if column in out.columns:
                out[column] = pd.to_numeric(out[column], errors="coerce") * multiplier
        return out.drop(columns=["__date__", "__factor__"])
