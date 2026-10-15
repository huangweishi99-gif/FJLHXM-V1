"""板块敞口：品种 → 板块映射 + 敞口统计与限额检查（**默认关闭**）。

为什么要这个：国内 33 个品种看起来很分散，但黑色（RB/JM/SF）、能化（MA/TA/EG/PP/V）、
有色（NI/AO/LC）内部相关性常年在 0.7 以上，每品种还能开多仓 —— 名义分散、实际是
几个 beta 的集中押注。真正的分散要按**板块**设上限，而不只是每品种限仓。

使用：``--max-sector-positions 0``（默认）表示不启用，行为与改动前完全一致。
"""
from __future__ import annotations

from typing import Any, Iterable, Mapping

# 国内期货板块映射（按项目当前交易品种表整理）
SECTOR_MAP: dict[str, str] = {
    # 黑色 / 建材
    "RB": "BLACK",
    "JM": "BLACK",
    "SF": "BLACK",
    "FG": "BLACK",
    # 能源化工
    "SA": "ENERGY_CHEM",
    "PG": "ENERGY_CHEM",
    "FU": "ENERGY_CHEM",
    "PP": "ENERGY_CHEM",
    "SH": "ENERGY_CHEM",
    "EB": "ENERGY_CHEM",
    "EG": "ENERGY_CHEM",
    "RU": "ENERGY_CHEM",
    "BR": "ENERGY_CHEM",
    "MA": "ENERGY_CHEM",
    "V": "ENERGY_CHEM",
    "TA": "ENERGY_CHEM",
    "UR": "ENERGY_CHEM",
    "SC": "ENERGY_CHEM",
    # 有色 / 新材料
    "NI": "METAL",
    "AO": "METAL",
    "LC": "METAL",
    "SI": "METAL",
    # 贵金属
    "AU": "PRECIOUS",
    "AG": "PRECIOUS",
    # 农产品 / 油脂
    "CJ": "AGRI",
    "OI": "AGRI",
    "LH": "AGRI",
    "JD": "AGRI",
    "SR": "AGRI",
    "M": "AGRI",
    "P": "AGRI",
    "CF": "AGRI",
    "SP": "AGRI",
    # 航运
    "EC": "SHIPPING",
}

UNKNOWN_SECTOR = "UNKNOWN"


def sector_of(symbol: str) -> str:
    """品种 → 板块；未收录的返回 UNKNOWN（不参与限额，避免误伤）。"""
    raw = str(symbol or "").strip().upper()
    if not raw:
        return UNKNOWN_SECTOR
    # 兼容 RB2601 / RB2601.SHFE / rb 等写法：取字母前缀
    code = "".join(ch for ch in raw.split(".")[0] if ch.isalpha())
    return SECTOR_MAP.get(code, UNKNOWN_SECTOR)


def _open_count(symbol_state: Mapping[str, Any]) -> int:
    positions = symbol_state.get("open_positions") or []
    count = 0
    for position in positions:
        if isinstance(position, dict) and not position.get("closed"):
            count += 1
    return count


def sector_exposure(paper_state: Mapping[str, Any]) -> dict[str, int]:
    """统计当前各板块的未平仓持仓数。"""
    counts: dict[str, int] = {}
    symbols = paper_state.get("symbols") or {}
    if not isinstance(symbols, Mapping):
        return counts
    for symbol, symbol_state in symbols.items():
        if not isinstance(symbol_state, Mapping):
            continue
        count = _open_count(symbol_state)
        if count <= 0:
            continue
        sector = sector_of(str(symbol))
        counts[sector] = counts.get(sector, 0) + count
    return counts


def would_breach_sector_limit(
    paper_state: Mapping[str, Any],
    symbol: str,
    *,
    max_positions: int,
    planned: Iterable[str] | None = None,
) -> str | None:
    """若再开一仓是否会突破板块上限；返回触发的板块名，未超限返回 None。

    ``planned`` 是本轮已计划成交的品种（避免同一轮内被重复放行而整体超限）。
    """
    if max_positions <= 0:  # 0 = 功能关闭
        return None
    sector = sector_of(symbol)
    if sector == UNKNOWN_SECTOR:
        return None
    counts = sector_exposure(paper_state)
    for planned_symbol in planned or []:
        if sector_of(planned_symbol) == sector:
            counts[sector] = counts.get(sector, 0) + 1
    if counts.get(sector, 0) >= max_positions:
        return sector
    return None
