from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class FuturesSpec:
    name: str
    code: str
    multiplier: float
    tick_size: float
    margin_rate: float


# Broker-style margin rates are intentionally conservative working defaults.
# They are configurable and should be updated from the user's live broker sheet
# when exact account rules are available.
FUTURES_SPECS: dict[str, FuturesSpec] = {
    "LPG": FuturesSpec("LPG", "PG", 20, 1, 0.12),
    "液化气": FuturesSpec("液化气", "PG", 20, 1, 0.12),
    "PTA": FuturesSpec("PTA", "TA", 5, 2, 0.08),
    "PVC": FuturesSpec("PVC", "V", 5, 1, 0.10),
    "乙二醇": FuturesSpec("乙二醇", "EG", 10, 1, 0.10),
    "合成橡胶": FuturesSpec("合成橡胶", "BR", 5, 5, 0.12),
    "尿素": FuturesSpec("尿素", "UR", 20, 1, 0.10),
    "工业硅": FuturesSpec("工业硅", "SI", 5, 5, 0.12),
    "棉花": FuturesSpec("棉花", "CF", 5, 5, 0.09),
    "橡胶": FuturesSpec("橡胶", "RU", 10, 5, 0.10),
    "氧化铝": FuturesSpec("氧化铝", "AO", 20, 1, 0.10),
    "沪镍": FuturesSpec("沪镍", "NI", 1, 10, 0.12),
    "烧碱": FuturesSpec("烧碱", "SH", 30, 1, 0.12),
    "焦煤": FuturesSpec("焦煤", "JM", 60, 0.5, 0.20),
    "燃油": FuturesSpec("燃油", "FU", 10, 1, 0.15),
    "玻璃": FuturesSpec("玻璃", "FG", 20, 1, 0.12),
    "生猪": FuturesSpec("生猪", "LH", 16, 5, 0.12),
    "甲醇": FuturesSpec("甲醇", "MA", 10, 1, 0.10),
    "白糖": FuturesSpec("白糖", "SR", 10, 1, 0.08),
    "硅铁": FuturesSpec("硅铁", "SF", 5, 2, 0.12),
    "碳酸锂": FuturesSpec("碳酸锂", "LC", 1, 50, 0.17),
    "红枣": FuturesSpec("红枣", "CJ", 5, 5, 0.12),
    "棕榈": FuturesSpec("棕榈", "P", 10, 2, 0.10),
    "纯碱": FuturesSpec("纯碱", "SA", 20, 1, 0.12),
    "纸浆": FuturesSpec("纸浆", "SP", 10, 2, 0.10),
    "苯乙烯": FuturesSpec("苯乙烯", "EB", 5, 1, 0.10),
    "菜油": FuturesSpec("菜油", "OI", 10, 1, 0.09),
    "菜粕": FuturesSpec("菜粕", "RM", 10, 1, 0.09),
    "螺纹钢": FuturesSpec("螺纹钢", "RB", 10, 1, 0.10),
    "豆粕": FuturesSpec("豆粕", "M", 10, 1, 0.08),
    "铁矿": FuturesSpec("铁矿", "I", 100, 0.5, 0.15),
    "锰硅": FuturesSpec("锰硅", "SM", 5, 2, 0.12),
    "鸡蛋": FuturesSpec("鸡蛋", "JD", 10, 1, 0.10),
}


def infer_spec_key(value: str | Path) -> str | None:
    text = Path(value).stem if isinstance(value, Path) else Path(str(value)).stem
    upper = text.upper()
    tokens = [token for token in upper.replace("-", "_").split("_") if token]
    for key, spec in FUTURES_SPECS.items():
        code = spec.code.upper()
        if key in text:
            return key
        if code in tokens or any(token.startswith(code + "0") for token in tokens):
            return key
    return None


def get_futures_spec(value: str | Path) -> FuturesSpec | None:
    key = infer_spec_key(value)
    return FUTURES_SPECS[key] if key else None
