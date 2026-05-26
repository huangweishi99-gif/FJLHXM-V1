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
    redefined_from_idx: int | None
    redefined_to: str | None


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

    def __init__(self, gap: int = 3) -> None:
        self.gap = gap
        self.reset()

    def reset(self) -> None:
        self.camp = NEUTRAL
        self.raw_nodes: list[RawNode] = []
        self.hardened_nodes: list[RawNode] = []
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
                hardened.append(node)

        return hardened

    def update_hardened_nodes(self, node: RawNode | None) -> None:
        if node is None:
            return
        if not self.hardened_nodes:
            self.hardened_nodes.append(node)
            return

        last = self.hardened_nodes[-1]
        if node.raw_type == last.raw_type:
            if node.raw_type == "HIGH" and node.price >= last.price:
                self.hardened_nodes[-1] = node
            elif node.raw_type == "LOW" and node.price <= last.price:
                self.hardened_nodes[-1] = node
            return

        if abs(node.point_idx - last.point_idx) >= self.gap:
            self.hardened_nodes.append(node)

    def process_bar(self, df: pd.DataFrame, i: int) -> None:
        row = df.iloc[i]
        date = row["date"] if "date" in df.columns else i
        high = float(row["high"])
        low = float(row["low"])
        close = float(row["close"])

        node = self.detect_raw_33_node(df, i)
        if node is not None:
            self.raw_nodes.append(node)
            self.update_hardened_nodes(node)

        self.hardened_by_bar.append(list(self.hardened_nodes))
        self.try_seed_camp(i, date, high, low)

        if node is not None:
            self.classify_identity(node)

        self.check_transition(i, date, high, low)
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
            self.red_peak = IdentityNode(last_high.point_idx, last_high.confirm_idx, last_high.price, "HIGH", "RED_PEAK", RED, "seed red peak", "seed")
            self.red_ext = IdentityNode(last_low.point_idx, last_low.confirm_idx, last_low.price, "LOW", "RED_EXT", RED, "seed red ext", "seed")
            self.identity_nodes.extend([self.red_ext, self.red_peak])
        elif low < last_low.price:
            self.camp = BLUE
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

    def check_transition(self, idx: int, date: Any, high: float, low: float) -> None:
        if self.camp == RED and self.red_ext is not None and low < self.red_ext.price:
            self.turn_red_to_blue(idx, date, low)
        elif self.camp == BLUE and self.blue_ext is not None and high > self.blue_ext.price:
            self.turn_blue_to_red(idx, date, high)

    def turn_red_to_blue(self, idx: int, date: Any, break_price: float) -> None:
        old_ext = self.red_ext
        redefine: IdentityNode | None = None
        self.camp = BLUE

        if self.last_failed_high is not None:
            node = self.last_failed_high
            redefine = IdentityNode(node.point_idx, node.confirm_idx, node.price, node.raw_type, "BLUE_EXT", BLUE, "failed high redefined to blue ext", "redefined")
        elif self.red_peak is not None:
            node = self.red_peak
            redefine = IdentityNode(node.point_idx, node.confirm_idx, node.price, node.raw_type, "BLUE_EXT", BLUE, "fallback red peak to blue ext", "fallback")

        if redefine is not None:
            self.blue_ext = redefine
            self.identity_nodes.append(redefine)

        self.blue_peak = None
        self.red_peak = None
        self.red_ext = None
        self.last_failed_high = None
        self.last_failed_low = None
        self.turns.append(TurnEvent(idx, date, "RED_TO_BLUE", "RED_EXT", old_ext.price if old_ext else np.nan, break_price, redefine.point_idx if redefine else None, redefine.identity if redefine else None))

    def turn_blue_to_red(self, idx: int, date: Any, break_price: float) -> None:
        old_ext = self.blue_ext
        redefine: IdentityNode | None = None
        self.camp = RED

        if self.last_failed_low is not None:
            node = self.last_failed_low
            redefine = IdentityNode(node.point_idx, node.confirm_idx, node.price, node.raw_type, "RED_EXT", RED, "failed low redefined to red ext", "redefined")
        elif self.blue_peak is not None:
            node = self.blue_peak
            redefine = IdentityNode(node.point_idx, node.confirm_idx, node.price, node.raw_type, "RED_EXT", RED, "fallback blue peak to red ext", "fallback")

        if redefine is not None:
            self.red_ext = redefine
            self.identity_nodes.append(redefine)

        self.red_peak = None
        self.blue_peak = None
        self.blue_ext = None
        self.last_failed_high = None
        self.last_failed_low = None
        self.turns.append(TurnEvent(idx, date, "BLUE_TO_RED", "BLUE_EXT", old_ext.price if old_ext else np.nan, break_price, redefine.point_idx if redefine else None, redefine.identity if redefine else None))

    def make_os_log_row(self, i: int, date: Any, high: float, low: float, close: float) -> dict[str, Any]:
        active_high, active_low = self.active_extremes()
        return {
            "idx": i,
            "date": date,
            "camp": self.camp,
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

    def to_frame(self, df: pd.DataFrame) -> pd.DataFrame:
        os_log = self.export_os_log().set_index("idx")
        out = df.copy()
        for column in ["camp", "active_high", "active_low", "red_peak_price", "red_ext_price", "blue_peak_price", "blue_ext_price"]:
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

    def export_tagged_nodes(self) -> pd.DataFrame:
        return pd.DataFrame([asdict(node) for node in self.identity_nodes])

    def export_turns(self) -> pd.DataFrame:
        return pd.DataFrame([asdict(turn) for turn in self.turns])

    def export_os_log(self) -> pd.DataFrame:
        return pd.DataFrame(self.logs)
