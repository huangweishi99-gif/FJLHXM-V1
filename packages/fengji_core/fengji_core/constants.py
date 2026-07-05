"""Shared FengJi Total Pattern constants."""

FENGJI_TOTAL_PATTERN_STRATEGIES = [
    "DS01",
    "DS02",
    "DS03",
    "DS04",
    "DS05",
    "DS06",
    "DS07",
    "DS08",
    "DS09",
]

DEFAULT_STRATEGIES_CSV = ",".join(FENGJI_TOTAL_PATTERN_STRATEGIES)

STRATEGY_PRIORITY = {
    "DS01": 10,
    "DS02": 20,
    "DS03": 30,
    "DS04": 40,
    "DS05": 50,
    "DS06": 60,
    "DS07": 70,
    "DS08": 80,
    "DS09": 90,
    "TOTAL": 5,
}

# 中文展示名（Web / API / 动画文案统一口径）
STRATEGY_DISPLAY_NAMES: dict[str, str] = {
    "DS01": "挫棍",
    "DS02": "阴阳相吃",
    "DS03": "二四棒",
    "DS04": "夹棍",
    "DS05": "指形战法",
    "DS06": "外扩峰",
    "DS07": "共振决战",
    "DS08": "否定确认式",
    "DS09": "九重天",
    "TOTAL": "峰极总定式",
}
