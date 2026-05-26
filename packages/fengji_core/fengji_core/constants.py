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
}
