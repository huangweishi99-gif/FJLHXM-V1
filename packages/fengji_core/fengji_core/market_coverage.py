"""市场数据覆盖边界（Phase 2 D6）：A股 60m 定式门槛 · 国内期货日夜盘参考表。"""
from __future__ import annotations

from typing import Iterable

# A股：H1/60m 不足时仅允许日线定式（与 backtest_a_stock_fengji 口径一致）
DAILY_ONLY_STRATEGIES: frozenset[str] = frozenset(
    {"DS01", "DS02", "DS03", "DS04", "DS05", "DS06"}
)
H1_REQUIRED_STRATEGIES: frozenset[str] = frozenset({"DS07", "DS08"})
M15_REQUIRED_STRATEGIES: frozenset[str] = frozenset({"DS09"})

# 约 3 个月 A股 60m（4 根/日 × ~60 交易日）；东方财富常只返回 ~128 根，不足以支撑 DS07/DS08 历史级结论
A_STOCK_H1_MIN_ROWS_DS07_DS08 = 500
A_STOCK_M15_MIN_ROWS_DS09 = 800

# data_manager_futures.py 统一泵窗口（最长夜盘品种到次日 02:30，代码用 02:35 收口）
FUTURES_DATA_PUMP_WINDOWS: tuple[tuple[str, str, str], ...] = (
    ("day_am", "08:30", "11:35"),
    ("day_pm", "13:00", "15:15"),
    ("night_early", "20:30", "23:59"),
    ("night_late", "00:00", "02:35"),
)

A_STOCK_DATA_PUMP_WINDOWS: tuple[tuple[str, str, str], ...] = (
    ("day_am", "09:00", "11:35"),
    ("day_pm", "12:30", "15:05"),
)

# 国内模拟盘 34 品种夜盘结束时刻（交易所规则摘要；细则变更以交易所公告为准）
FUTURES_NIGHT_END_BY_SYMBOL: dict[str, str] = {
    # 郑商所 — 夜盘 21:00–23:00
    "SA": "23:00",
    "FG": "23:00",
    "CJ": "23:00",
    "OI": "23:00",
    "SH": "23:00",
    "SR": "23:00",
    "SF": "23:00",
    "MA": "23:00",
    "TA": "23:00",
    "UR": "23:00",
    "CF": "23:00",
    # 大商所 — 夜盘 21:00–23:00
    "PG": "23:00",
    "LH": "23:00",
    "JD": "23:00",
    "PP": "23:00",
    "EB": "23:00",
    "EG": "23:00",
    "JM": "23:00",
    "M": "23:00",
    "P": "23:00",
    "V": "23:00",
    # 广期所 — 夜盘 21:00–23:00
    "SI": "23:00",
    "LC": "23:00",
    # 上期所 / 能源 — 夜盘 21:00–23:30
    "RB": "23:30",
    "FU": "23:30",
    "SP": "23:30",
    "RU": "23:30",
    "BR": "23:30",
    # 上期所 — 夜盘 21:00–01:00
    "NI": "01:00",
    "AO": "01:00",
    "EC": "01:00",
    # 上期所 / 能源 — 夜盘 21:00–02:30
    "AU": "02:30",
    "AG": "02:30",
    "SC": "02:30",
}

FUTURES_DAY_SESSION = "09:00–10:15, 10:30–11:30, 13:30–15:00（国内期货统一日盘）"
FUTURES_NIGHT_OPEN = "21:00"


def h1_eligible_for_ds07_ds08(h1_rows: int) -> bool:
    return int(h1_rows) >= A_STOCK_H1_MIN_ROWS_DS07_DS08


def m15_eligible_for_ds09(m15_rows: int) -> bool:
    return int(m15_rows) >= A_STOCK_M15_MIN_ROWS_DS09


def filter_strategies_for_a_stock_data(
    strategies: Iterable[str],
    *,
    h1_rows: int = 0,
    m15_rows: int = 0,
) -> tuple[list[str], list[str]]:
    """返回 (可运行定式, 跳过原因列表)。"""
    requested = [str(s).strip().upper() for s in strategies if str(s).strip()]
    skipped: list[str] = []
    allowed = list(requested)

    if not h1_eligible_for_ds07_ds08(h1_rows):
        drop = [s for s in allowed if s in H1_REQUIRED_STRATEGIES]
        if drop:
            allowed = [s for s in allowed if s not in H1_REQUIRED_STRATEGIES]
            skipped.append(
                f"H1 rows={h1_rows} < {A_STOCK_H1_MIN_ROWS_DS07_DS08}，跳过 {','.join(drop)}"
            )

    if not m15_eligible_for_ds09(m15_rows):
        if "DS09" in allowed:
            allowed = [s for s in allowed if s != "DS09"]
            skipped.append(
                f"M15 rows={m15_rows} < {A_STOCK_M15_MIN_ROWS_DS09}，跳过 DS09"
            )

    return allowed, skipped


def futures_symbols_missing_night_map(symbols: Iterable[str]) -> list[str]:
    missing: list[str] = []
    for sym in symbols:
        key = str(sym).strip().upper().replace("USDT", "")
        if key and key not in FUTURES_NIGHT_END_BY_SYMBOL:
            missing.append(key)
    return sorted(set(missing))
