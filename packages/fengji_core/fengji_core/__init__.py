"""FengJi OS core: identity engine and calibrated strategy primitives."""

from fengji_core.constants import (
    DEFAULT_STRATEGIES_CSV,
    FENGJI_TOTAL_PATTERN_STRATEGIES,
    STRATEGY_PRIORITY,
)
from fengji_core.os_engine import (
    BLUE,
    NEUTRAL,
    RED,
    FengJiOSIdentityEngine,
    IdentityNode,
    RawNode,
    TurnEvent,
    audit_identity_line,
    build_identity_line,
    role,
)

__all__ = [
    "BLUE",
    "DEFAULT_STRATEGIES_CSV",
    "FENGJI_TOTAL_PATTERN_STRATEGIES",
    "FengJiOSIdentityEngine",
    "IdentityNode",
    "NEUTRAL",
    "RED",
    "RawNode",
    "STRATEGY_PRIORITY",
    "TurnEvent",
    "audit_identity_line",
    "build_identity_line",
    "role",
]

__version__ = "0.1.0"
