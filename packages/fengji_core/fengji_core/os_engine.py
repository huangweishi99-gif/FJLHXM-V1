from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

import numpy as np
import pandas as pd


RED = 1
BLUE = -1
NEUTRAL = 0


@dataclass(frozen=True)
class RawNode:
    point_idx: int
    confirm_idx: int
    price: float
    raw_type: str
    dual_extreme: bool = False
    arbitration: str = ""
    source: str = "raw_33"


@dataclass(frozen=True)
class IdentityNode:
    point_idx: int
    confirm_idx: int
    price: float
    raw_type: str
    identity: str
    camp: int
    note: str = ""
    source: str = ""


@dataclass(frozen=True)
class TurnEvent:
    idx: int
    date: Any
    turn: str
    broken_identity: str
    broken_price: float
    break_price: float
    broken_point_idx: int | None
    redefined_from_idx: int | None
    redefined_to: str | None


def _raw_node_from_state(item: dict[str, Any]) -> RawNode:
    return RawNode(
        point_idx=int(item["point_idx"]),
        confirm_idx=int(item["confirm_idx"]),
        price=float(item["price"]),
        raw_type=str(item["raw_type"]),
        dual_extreme=bool(item.get("dual_extreme", False)),
        arbitration=str(item.get("arbitration", "")),
        source=str(item.get("source", "raw_33")),
    )


def _identity_node_from_state(item: dict[str, Any]) -> IdentityNode:
    return IdentityNode(
        point_idx=int(item["point_idx"]),
        confirm_idx=int(item["confirm_idx"]),
        price=float(item["price"]),
        raw_type=str(item["raw_type"]),
        identity=str(item["identity"]),
        camp=int(item["camp"]),
        note=str(item.get("note", "")),
        source=str(item.get("source", "")),
    )


def _turn_event_from_state(item: dict[str, Any]) -> TurnEvent:
    redefined_from_idx = item.get("redefined_from_idx")
    broken_point_idx = item.get("broken_point_idx")
    return TurnEvent(
        idx=int(item["idx"]),
        date=item.get("date"),
        turn=str(item["turn"]),
        broken_identity=str(item["broken_identity"]),
        broken_price=float(item["broken_price"]),
        break_price=float(item["break_price"]),
        broken_point_idx=None if broken_point_idx is None else int(broken_point_idx),
        redefined_from_idx=None if redefined_from_idx is None else int(redefined_from_idx),
        redefined_to=item.get("redefined_to"),
    )


def _maybe_raw_node(item: dict[str, Any] | None) -> RawNode | None:
    if item is None:
        return None
    return _raw_node_from_state(item)


def _maybe_identity_node(item: dict[str, Any] | None) -> IdentityNode | None:
    if item is None:
        return None
    return _identity_node_from_state(item)


def role(identity: str) -> str:
    if identity in {"RED_PEAK", "BLUE_PEAK"}:
        return "PEAK"
    if identity in {"RED_EXT", "BLUE_EXT"}:
        return "EXT"
    return "FAILED"


def build_identity_line(identity_nodes: list[IdentityNode]) -> list[IdentityNode]:
    """Build the only legal peak-extreme identity line from identity logs."""
    line: list[IdentityNode] = []
    for node in identity_nodes:
        node_role = role(node.identity)
        if node_role == "FAILED":
            continue
        if not line:
            line.append(node)
            continue

        last = line[-1]
        last_role = role(last.identity)
        if last_role == node_role:
            if node_role == "PEAK" and node.price > last.price:
                line[-1] = node
            elif node_role == "EXT" and node.price < last.price:
                line[-1] = node
            continue
        line.append(node)
    return line


def audit_identity_line(identity_line: list[IdentityNode]) -> bool:
    for idx in range(1, len(identity_line)):
        prev_role = role(identity_line[idx - 1].identity)
        curr_role = role(identity_line[idx].identity)
        assert prev_role != curr_role, "identity_line must alternate PEAK and EXT"
        assert prev_role != "FAILED" and curr_role != "FAILED"
    return True


class FengJiOSIdentityEngine:
    """Runtime for FengJi OS identity, camp, hardening, and audit state."""

    def __init__(self, gap: int = 3, record_hardened_by_bar: bool = True) -> None:
        self.gap = gap
        self.record_hardened_by_bar = record_hardened_by_bar
        self.reset()

    def reset(self) -> None:
        self.camp = NEUTRAL
        self.camp_confirmed = NEUTRAL
        self.pending_turn = False
        self._turn_idx: int | None = None
        self._turn_had_redefine = False
        self.raw_nodes: list[RawNode] = []
        self.hardened_nodes: list[RawNode] = []
        self.emergency_nodes: list[RawNode] = []
        self.identity_nodes: list[IdentityNode] = []
        self.turns: list[TurnEvent] = []
        self.logs: list[dict[str, Any]] = []
        self.hardened_by_bar: list[list[RawNode]] = []
        self.red_peak: IdentityNode | None = None
        self.red_ext: IdentityNode | None = None
        self.blue_peak: IdentityNode | None = None
        self.blue_ext: IdentityNode | None = None
        self.last_failed_high: RawNode | None = None
        self.last_failed_low: RawNode | None = None
        self.last_emergency_node: RawNode | None = None

    @property
    def processed_len(self) -> int:
        return len(self.logs)

    def to_state(self, include_hardened_by_bar: bool | None = None) -> dict[str, Any]:
        keep_hardened_by_bar = self.record_hardened_by_bar if include_hardened_by_bar is None else include_hardened_by_bar
        return {
            "version": 1,
            "gap": self.gap,
            "record_hardened_by_bar": self.record_hardened_by_bar,
            "processed_len": self.processed_len,
            "camp": self.camp,
            "camp_confirmed": self.camp_confirmed,
            "pending_turn": self.pending_turn,
            "turn_idx": self._turn_idx,
            "turn_had_redefine": self._turn_had_redefine,
            "raw_nodes": [asdict(node) for node in self.raw_nodes],
            "hardened_nodes": [asdict(node) for node in self.hardened_nodes],
            "emergency_nodes": [asdict(node) for node in self.emergency_nodes],
            "identity_nodes": [asdict(node) for node in self.identity_nodes],
            "turns": [asdict(turn) for turn in self.turns],
            "logs": self.logs,
            "hardened_by_bar": [[asdict(node) for node in nodes] for nodes in self.hardened_by_bar] if keep_hardened_by_bar else [],
            "red_peak": None if self.red_peak is None else asdict(self.red_peak),
            "red_ext": None if self.red_ext is None else asdict(self.red_ext),
            "blue_peak": None if self.blue_peak is None else asdict(self.blue_peak),
            "blue_ext": None if self.blue_ext is None else asdict(self.blue_ext),
            "last_failed_high": None if self.last_failed_high is None else asdict(self.last_failed_high),
            "last_failed_low": None if self.last_failed_low is None else asdict(self.last_failed_low),
            "last_emergency_node": None if self.last_emergency_node is None else asdict(self.last_emergency_node),
        }

    def load_state(self, state: dict[str, Any]) -> "FengJiOSIdentityEngine":
        self.gap = int(state.get("gap", self.gap))
        self.record_hardened_by_bar = bool(state.get("record_hardened_by_bar", self.record_hardened_by_bar))
        self.camp = int(state.get("camp", NEUTRAL))
        self.camp_confirmed = int(state.get("camp_confirmed", self.camp))
        self.pending_turn = bool(state.get("pending_turn", False))
        turn_idx = state.get("turn_idx")
        self._turn_idx = None if turn_idx is None else int(turn_idx)
        self._turn_had_redefine = bool(state.get("turn_had_redefine", False))
        self.raw_nodes = [_raw_node_from_state(item) for item in state.get("raw_nodes", [])]
        self.hardened_nodes = [_raw_node_from_state(item) for item in state.get("hardened_nodes", [])]
        self.emergency_nodes = [_raw_node_from_state(item) for item in state.get("emergency_nodes", [])]
        self.identity_nodes = [_identity_node_from_state(item) for item in state.get("identity_nodes", [])]
        self.turns = [_turn_event_from_state(item) for item in state.get("turns", [])]
        self.logs = list(state.get("logs", []))
        if self.camp != NEUTRAL:
            self.camp_confirmed = self.camp
            self.pending_turn = False
        self.hardened_by_bar = [
            [_raw_node_from_state(node) for node in nodes]
            for nodes in state.get("hardened_by_bar", [])
        ]
        self.red_peak = _maybe_identity_node(state.get("red_peak"))
        self.red_ext = _maybe_identity_node(state.get("red_ext"))
        self.blue_peak = _maybe_identity_node(state.get("blue_peak"))
        self.blue_ext = _maybe_identity_node(state.get("blue_ext"))
        self.last_failed_high = _maybe_raw_node(state.get("last_failed_high"))
        self.last_failed_low = _maybe_raw_node(state.get("last_failed_low"))
        self.last_emergency_node = _maybe_raw_node(state.get("last_emergency_node"))
        return self

    def detect_raw_33_node(self, df: pd.DataFrame, i: int) -> RawNode | None:
        if i < 6:
            return None

        t = i - 3
        window = df.iloc[i - 6 : i + 1]
        high = float(df.at[t, "high"])
        low = float(df.at[t, "low"])
        open_ = float(df.at[t, "open"])
        close = float(df.at[t, "close"])
        max_high = float(window["high"].max())
        min_low = float(window["low"].min())
        latest_high_idx = int(window[window["high"] == max_high].index[-1])
        latest_low_idx = int(window[window["low"] == min_low].index[-1])
        is_high = high == max_high and t == latest_high_idx
        is_low = low == min_low and t == latest_low_idx

        if is_high and not is_low:
            return RawNode(t, i, high, "HIGH")
        if is_low and not is_high:
            return RawNode(t, i, low, "LOW")
        if is_high and is_low:
            if close > open_:
                return RawNode(t, i, high, "HIGH", True, "yang_keep_HIGH")
            if close < open_:
                return RawNode(t, i, low, "LOW", True, "yin_keep_LOW")
        return None

    @staticmethod
    def _can_connect_opposite_nodes(last: RawNode, node: RawNode) -> bool:
        """峰极连线必须满足价格节奏：HIGH 之后 LOW 更低，LOW 之后 HIGH 更高。"""
        if last.raw_type == "HIGH" and node.raw_type == "LOW":
            return node.price < last.price
        if last.raw_type == "LOW" and node.raw_type == "HIGH":
            return node.price > last.price
        return False

    def harden_nodes(self, raw_nodes: list[RawNode], upto_confirm_idx: int) -> list[RawNode]:
        visible = [node for node in raw_nodes if node.confirm_idx <= upto_confirm_idx]
        visible = sorted(visible, key=lambda node: (node.point_idx, node.confirm_idx))
        hardened: list[RawNode] = []

        for node in visible:
            if not hardened:
                hardened.append(node)
                continue

            last = hardened[-1]
            if node.raw_type == last.raw_type:
                if node.raw_type == "HIGH" and node.price >= last.price:
                    hardened[-1] = node
                elif node.raw_type == "LOW" and node.price <= last.price:
                    hardened[-1] = node
                continue

            if abs(node.point_idx - last.point_idx) >= self.gap:
                if self._can_connect_opposite_nodes(last, node):
                    hardened.append(node)
                continue

        return hardened

    @staticmethod
    def _tag_raw_node(node: RawNode, *, arbitration: str, source: str) -> RawNode:
        return RawNode(
            node.point_idx,
            node.confirm_idx,
            node.price,
            node.raw_type,
            node.dual_extreme,
            arbitration,
            source,
        )

    @staticmethod
    def _bar_is_displacement(row: pd.Series, direction: str, range_baseline: float | None) -> bool:
        high = float(row["high"])
        low = float(row["low"])
        open_ = float(row["open"])
        close = float(row["close"])
        bar_range = high - low
        if bar_range <= 0:
            return False

        if direction == "down":
            directional = close < open_
        else:
            directional = close > open_
        if not directional:
            return False

        body_ratio = abs(close - open_) / bar_range
        large_body = body_ratio >= 0.55
        large_range = range_baseline is not None and range_baseline > 0 and bar_range >= range_baseline * 1.4
        return large_body or large_range

    def _urgent_gap_reason(self, last: RawNode, node: RawNode, df: pd.DataFrame | None) -> str | None:
        """Allow violent displacement exceptions without weakening the normal gap rule.

        Normal hardening remains gap>=3. A gap<3 opposite node is accepted only when
        the bar segment between the last point and the candidate contains a clear
        directional displacement candle. The node is still marked source=urgent_gap
        so downstream audits can distinguish it from ordinary 3-3/T+3 hardening.
        """
        if df is None:
            return None
        if node.point_idx <= last.point_idx:
            return None
        if node.point_idx - last.point_idx >= self.gap:
            return None
        if last.raw_type == "HIGH" and node.raw_type == "LOW":
            direction = "down"
        elif last.raw_type == "LOW" and node.raw_type == "HIGH":
            direction = "up"
        else:
            return None

        start = max(0, last.point_idx + 1)
        end = min(len(df) - 1, node.point_idx)
        if start > end:
            return None

        prior = df.iloc[max(0, last.point_idx - 20) : last.point_idx + 1]
        prior_ranges = (prior["high"].astype(float) - prior["low"].astype(float)).replace([np.inf, -np.inf], np.nan).dropna()
        range_baseline = float(prior_ranges.median()) if not prior_ranges.empty else None

        segment = df.iloc[start : end + 1]
        if any(self._bar_is_displacement(row, direction, range_baseline) for _, row in segment.iterrows()):
            return f"urgent_gap_{direction}"
        return None

    def update_hardened_nodes(self, node: RawNode | None, df: pd.DataFrame | None = None) -> bool:
        if node is None:
            return False
        if not self.hardened_nodes:
            self.hardened_nodes.append(node)
            return True

        last = self.hardened_nodes[-1]
        if node.raw_type == last.raw_type:
            if node.raw_type == "HIGH" and node.price >= last.price:
                self.hardened_nodes[-1] = node
                return True
            elif node.raw_type == "LOW" and node.price <= last.price:
                self.hardened_nodes[-1] = node
                return True
            return False

        if abs(node.point_idx - last.point_idx) >= self.gap:
            if not self._can_connect_opposite_nodes(last, node):
                return False
            self.hardened_nodes.append(node)
            return True
        urgent_reason = self._urgent_gap_reason(last, node, df)
        if urgent_reason is not None:
            if not self._can_connect_opposite_nodes(last, node):
                return False
            urgent_node = self._tag_raw_node(node, arbitration=urgent_reason, source="urgent_gap")
            self.hardened_nodes.append(urgent_node)
            self.emergency_nodes.append(urgent_node)
            self.last_emergency_node = urgent_node
            return True
        return False

    def process_bar(self, df: pd.DataFrame, i: int) -> None:
        row = df.iloc[i]
        date = row["date"] if "date" in df.columns else i
        high = float(row["high"])
        low = float(row["low"])
        close = float(row["close"])

        node = self.detect_raw_33_node(df, i)
        node_accepted = False
        accepted_node: RawNode | None = None
        if node is not None:
            self.raw_nodes.append(node)
            node_accepted = self.update_hardened_nodes(node, df)
            if node_accepted:
                accepted_node = self.hardened_nodes[-1]

        if self.record_hardened_by_bar:
            self.hardened_by_bar.append(list(self.hardened_nodes))
        self.try_seed_camp(i, date, high, low)

        if accepted_node is not None:
            self.classify_identity(accepted_node)

        self.check_transition(i, date, high, low)
        self._try_confirm_camp(i)
        self.logs.append(self.make_os_log_row(i, date, high, low, close))

    def try_seed_camp(self, idx: int, date: Any, high: float, low: float) -> None:
        del idx, date
        if self.camp != NEUTRAL or len(self.hardened_nodes) < 2:
            return

        highs = [node for node in self.hardened_nodes if node.raw_type == "HIGH"]
        lows = [node for node in self.hardened_nodes if node.raw_type == "LOW"]
        if not highs or not lows:
            return

        last_high = highs[-1]
        last_low = lows[-1]
        if high > last_high.price:
            self.camp = RED
            self.camp_confirmed = RED
            self.pending_turn = False
            self._turn_idx = None
            self._turn_had_redefine = False
            self.red_peak = IdentityNode(last_high.point_idx, last_high.confirm_idx, last_high.price, "HIGH", "RED_PEAK", RED, "seed red peak", "seed")
            self.red_ext = IdentityNode(last_low.point_idx, last_low.confirm_idx, last_low.price, "LOW", "RED_EXT", RED, "seed red ext", "seed")
            self.identity_nodes.extend([self.red_ext, self.red_peak])
        elif low < last_low.price:
            self.camp = BLUE
            self.camp_confirmed = BLUE
            self.pending_turn = False
            self._turn_idx = None
            self._turn_had_redefine = False
            self.blue_peak = IdentityNode(last_low.point_idx, last_low.confirm_idx, last_low.price, "LOW", "BLUE_PEAK", BLUE, "seed blue peak", "seed")
            self.blue_ext = IdentityNode(last_high.point_idx, last_high.confirm_idx, last_high.price, "HIGH", "BLUE_EXT", BLUE, "seed blue ext", "seed")
            self.identity_nodes.extend([self.blue_ext, self.blue_peak])

    def classify_identity(self, node: RawNode) -> None:
        if self.camp == RED:
            self.classify_red_identity(node)
        elif self.camp == BLUE:
            self.classify_blue_identity(node)

    def classify_red_identity(self, node: RawNode) -> None:
        if node.raw_type == "HIGH":
            if self.red_peak is None or node.price > self.red_peak.price:
                tagged = IdentityNode(node.point_idx, node.confirm_idx, node.price, node.raw_type, "RED_PEAK", RED, "red attack advances", "confirmed_raw")
                self.red_peak = tagged
                self.identity_nodes.append(tagged)
                self.last_failed_high = None
            elif self.red_ext is not None and node.price > self.red_ext.price:
                self.last_failed_high = node
                self.identity_nodes.append(IdentityNode(node.point_idx, node.confirm_idx, node.price, node.raw_type, "FAILED_HIGH", RED, "failed rebound high; wait for red_ext break", "confirmed_raw"))
        elif node.raw_type == "LOW":
            if self.red_ext is None or node.price > self.red_ext.price:
                tagged = IdentityNode(node.point_idx, node.confirm_idx, node.price, node.raw_type, "RED_EXT", RED, "red defense lifts", "confirmed_raw")
                self.red_ext = tagged
                self.identity_nodes.append(tagged)

    def classify_blue_identity(self, node: RawNode) -> None:
        if node.raw_type == "LOW":
            if self.blue_peak is None or node.price < self.blue_peak.price:
                tagged = IdentityNode(node.point_idx, node.confirm_idx, node.price, node.raw_type, "BLUE_PEAK", BLUE, "blue attack advances downward", "confirmed_raw")
                self.blue_peak = tagged
                self.identity_nodes.append(tagged)
                self.last_failed_low = None
            elif self.blue_ext is not None and node.price < self.blue_ext.price:
                self.last_failed_low = node
                self.identity_nodes.append(IdentityNode(node.point_idx, node.confirm_idx, node.price, node.raw_type, "FAILED_LOW", BLUE, "failed probe low; wait for blue_ext break", "confirmed_raw"))
        elif node.raw_type == "HIGH":
            if self.blue_ext is None or node.price < self.blue_ext.price:
                tagged = IdentityNode(node.point_idx, node.confirm_idx, node.price, node.raw_type, "BLUE_EXT", BLUE, "blue defense moves downward", "confirmed_raw")
                self.blue_ext = tagged
                self.identity_nodes.append(tagged)

    def _c_class_red_to_blue(self) -> bool:
        """急转势：红峰已确立后跌破红极，常无标准假峰链（宪法 §4.7 C 类）。"""
        return (
            self.last_failed_high is None
            and self.red_peak is not None
            and self.red_ext is not None
            and self.red_peak.point_idx > self.red_ext.point_idx
            and self.red_peak.confirm_idx >= self.red_ext.confirm_idx
        )

    def _c_class_blue_to_red(self) -> bool:
        """急转势：蓝峰已确立后突破蓝极，常无标准假蓝峰链（宪法 §4.7 C 类镜像）。"""
        return (
            self.last_failed_low is None
            and self.blue_peak is not None
            and self.blue_ext is not None
            and self.blue_peak.point_idx > self.blue_ext.point_idx
            and self.blue_peak.confirm_idx >= self.blue_ext.confirm_idx
        )

    def _entire_bar_below_red_ext(self, high: float) -> bool:
        return self.red_ext is not None and high < self.red_ext.price

    def _entire_bar_above_blue_ext(self, low: float) -> bool:
        return self.blue_ext is not None and low > self.blue_ext.price

    def check_transition(self, idx: int, date: Any, high: float, low: float) -> None:
        """破极转势：B 类须假峰探针；C 类允许峰后直接破极；整根 K 脱离防守极亦转势。"""
        if (
            self.camp == RED
            and self.red_ext is not None
            and low <= self.red_ext.price
            and (
                self.last_failed_high is not None
                or self._c_class_red_to_blue()
                or self._entire_bar_below_red_ext(high)
            )
        ):
            self.turn_red_to_blue(idx, date, low)
        elif (
            self.camp == BLUE
            and self.blue_ext is not None
            and high >= self.blue_ext.price
            and (
                self.last_failed_low is not None
                or self._c_class_blue_to_red()
                or self._entire_bar_above_blue_ext(low)
            )
        ):
            self.turn_blue_to_red(idx, date, high)

    def _structure_gap_ok(self, left_point_idx: int, right_point_idx: int) -> bool:
        return right_point_idx - left_point_idx >= self.gap

    def turn_red_to_blue(self, idx: int, date: Any, break_price: float) -> None:
        old_ext = self.red_ext
        redefine: IdentityNode | None = None
        self.camp = BLUE
        self.camp_confirmed = BLUE
        self.pending_turn = False
        self._turn_idx = idx
        self._turn_had_redefine = False

        if self.last_failed_high is not None:
            node = self.last_failed_high
            redefine = IdentityNode(node.point_idx, node.confirm_idx, node.price, node.raw_type, "BLUE_EXT", BLUE, "failed high redefined to blue ext", "redefined")
            self._turn_had_redefine = True
        elif self.red_peak is not None:
            # N字突破04：C 类/整根脱离且无假红峰可重定义时，启动前的红峰直接充当新蓝营防守极（蓝极）。
            node = self.red_peak
            redefine = IdentityNode(node.point_idx, node.confirm_idx, node.price, node.raw_type, "BLUE_EXT", BLUE, "red peak redefined to blue ext (C-class/detachment, N04)", "redefined")
            self._turn_had_redefine = True

        if redefine is not None:
            self.blue_ext = redefine
            self.identity_nodes.append(redefine)

        self.blue_peak = None
        self.red_peak = None
        self.red_ext = None
        self.last_failed_high = None
        self.last_failed_low = None
        self.turns.append(
            TurnEvent(
                idx,
                date,
                "RED_TO_BLUE",
                "RED_EXT",
                old_ext.price if old_ext else np.nan,
                break_price,
                old_ext.point_idx if old_ext else None,
                redefine.point_idx if redefine else None,
                redefine.identity if redefine else None,
            )
        )

    def turn_blue_to_red(self, idx: int, date: Any, break_price: float) -> None:
        old_ext = self.blue_ext
        redefine: IdentityNode | None = None
        self.camp = RED
        self.camp_confirmed = RED
        self.pending_turn = False
        self._turn_idx = idx
        self._turn_had_redefine = False

        if self.last_failed_low is not None:
            node = self.last_failed_low
            redefine = IdentityNode(node.point_idx, node.confirm_idx, node.price, node.raw_type, "RED_EXT", RED, "failed low redefined to red ext", "redefined")
            self._turn_had_redefine = True
        elif self.blue_peak is not None:
            # N字突破04：C 类/整根脱离且无假蓝峰可重定义时，启动前的蓝峰直接充当新红营防守极（红极）。
            node = self.blue_peak
            redefine = IdentityNode(node.point_idx, node.confirm_idx, node.price, node.raw_type, "RED_EXT", RED, "blue peak redefined to red ext (C-class/detachment, N04)", "redefined")
            self._turn_had_redefine = True

        if redefine is not None:
            self.red_ext = redefine
            self.identity_nodes.append(redefine)

        self.red_peak = None
        self.blue_peak = None
        self.blue_ext = None
        self.last_failed_high = None
        self.last_failed_low = None
        self.turns.append(
            TurnEvent(
                idx,
                date,
                "BLUE_TO_RED",
                "BLUE_EXT",
                old_ext.price if old_ext else np.nan,
                break_price,
                old_ext.point_idx if old_ext else None,
                redefine.point_idx if redefine else None,
                redefine.identity if redefine else None,
            )
        )

    def _try_confirm_camp(self, idx: int) -> None:
        """N字突破03: once a legal camp turn happens, authorization follows camp."""
        del idx
        if self.camp == NEUTRAL:
            return
        self.camp_confirmed = self.camp
        self.pending_turn = False

    def make_os_log_row(self, i: int, date: Any, high: float, low: float, close: float) -> dict[str, Any]:
        active_high, active_low = self.active_extremes()
        return {
            "idx": i,
            "date": date,
            "camp": self.camp,
            "camp_confirmed": self.camp_confirmed,
            "pending_turn": self.pending_turn,
            "high": high,
            "low": low,
            "close": close,
            "active_high": active_high,
            "active_low": active_low,
            "red_peak_idx": self.red_peak.point_idx if self.red_peak else None,
            "red_peak_price": self.red_peak.price if self.red_peak else np.nan,
            "red_ext_idx": self.red_ext.point_idx if self.red_ext else None,
            "red_ext_price": self.red_ext.price if self.red_ext else np.nan,
            "blue_peak_idx": self.blue_peak.point_idx if self.blue_peak else None,
            "blue_peak_price": self.blue_peak.price if self.blue_peak else np.nan,
            "blue_ext_idx": self.blue_ext.point_idx if self.blue_ext else None,
            "blue_ext_price": self.blue_ext.price if self.blue_ext else np.nan,
            "last_failed_high_idx": self.last_failed_high.point_idx if self.last_failed_high else None,
            "last_failed_high_price": self.last_failed_high.price if self.last_failed_high else np.nan,
            "last_failed_low_idx": self.last_failed_low.point_idx if self.last_failed_low else None,
            "last_failed_low_price": self.last_failed_low.price if self.last_failed_low else np.nan,
            "last_emergency_idx": self.last_emergency_node.point_idx if self.last_emergency_node else None,
            "last_emergency_price": self.last_emergency_node.price if self.last_emergency_node else np.nan,
            "last_emergency_type": self.last_emergency_node.raw_type if self.last_emergency_node else "",
            "last_emergency_reason": self.last_emergency_node.arbitration if self.last_emergency_node else "",
        }

    def active_extremes(self) -> tuple[float, float]:
        active_high = np.nan
        active_low = np.nan
        if self.camp == RED:
            active_high = self.red_peak.price if self.red_peak else np.nan
            active_low = self.red_ext.price if self.red_ext else np.nan
        elif self.camp == BLUE:
            active_high = self.blue_ext.price if self.blue_ext else np.nan
            active_low = self.blue_peak.price if self.blue_peak else np.nan
        return active_high, active_low

    def run(self, df: pd.DataFrame) -> "FengJiOSIdentityEngine":
        self.reset()
        for i in range(len(df)):
            self.process_bar(df, i)
        self.audit_identity_system()
        audit_identity_line(build_identity_line(self.identity_nodes))
        return self

    def run_from_state(self, df: pd.DataFrame, state: dict[str, Any] | None) -> "FengJiOSIdentityEngine":
        if state is None:
            return self.run(df)
        self.load_state(state)
        start = int(state.get("processed_len", self.processed_len))
        if start > len(df):
            raise ValueError("OS state has processed more bars than the input frame.")
        for i in range(start, len(df)):
            self.process_bar(df, i)
        self.audit_identity_system()
        audit_identity_line(build_identity_line(self.identity_nodes))
        return self

    def to_frame(self, df: pd.DataFrame) -> pd.DataFrame:
        os_log = self.export_os_log()
        # 日志为空时 DataFrame 没有任何列，直接 set_index 会抛 KeyError: 'idx'。
        # 短历史数据（例如 A 股 15m 只有数百根）可能一根 OS 都未形成，此时 OS 列
        # 应降级为 NaN（见下方 `column in os_log` 保护）而不是让整轮回测崩溃。
        if "idx" in os_log.columns:
            os_log = os_log.set_index("idx")
        out = df.copy()
        for column in [
            "camp",
            "camp_confirmed",
            "pending_turn",
            "active_high",
            "active_low",
            "red_peak_idx",
            "red_peak_price",
            "red_ext_idx",
            "red_ext_price",
            "blue_peak_idx",
            "blue_peak_price",
            "blue_ext_idx",
            "blue_ext_price",
            "last_failed_high_idx",
            "last_failed_high_price",
            "last_failed_low_idx",
            "last_failed_low_price",
            "last_emergency_idx",
            "last_emergency_price",
            "last_emergency_type",
            "last_emergency_reason",
        ]:
            out[column] = os_log[column].values if column in os_log else np.nan
        return out

    def audit_identity_system(self) -> bool:
        legal = {"RED_PEAK", "RED_EXT", "BLUE_PEAK", "BLUE_EXT", "FAILED_HIGH", "FAILED_LOW"}
        for node in self.identity_nodes:
            assert node.identity in legal, f"Illegal identity: {node}"
            if node.identity.startswith("RED_"):
                assert node.camp == RED
            if node.identity.startswith("BLUE_"):
                assert node.camp == BLUE
        for turn in self.turns:
            assert turn.broken_identity in {"RED_EXT", "BLUE_EXT"}
            assert turn.turn in {"RED_TO_BLUE", "BLUE_TO_RED"}
        return True

    def export_raw_nodes(self) -> pd.DataFrame:
        return pd.DataFrame([asdict(node) for node in self.raw_nodes])

    def export_emergency_nodes(self) -> pd.DataFrame:
        return pd.DataFrame([asdict(node) for node in self.emergency_nodes])

    def export_tagged_nodes(self) -> pd.DataFrame:
        return pd.DataFrame([asdict(node) for node in self.identity_nodes])

    def export_turns(self) -> pd.DataFrame:
        return pd.DataFrame([asdict(turn) for turn in self.turns])

    def export_os_log(self) -> pd.DataFrame:
        return pd.DataFrame(self.logs)
