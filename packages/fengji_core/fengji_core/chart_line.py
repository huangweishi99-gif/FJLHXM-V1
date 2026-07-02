"""Web / chart-bundle 峰极连线：物理硬化节点、区间桥接、审计。

口径（与沙盒 `draw_hardened_line` / FJLHXM P0 一致）：
1. 实线 = 物理 hardened_nodes 按时间顺序；仅剔除 FAILED-only 假探点。
2. 剔除 FAILED 后若出现 HIGH→HIGH / LOW→LOW，插入区间极值桥接（几何与沙盒 zigzag 对齐）。
3. 虚线 = 最后实线锚点 → 最新 K（单段橡皮筋，style=dashed/kind=provisional）。
4. 禁止用 identity_line 替代物理主线画 Web 实线。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

import pandas as pd

from fengji_core.os_engine import build_identity_line

CAMP_IDENTITIES = frozenset({"RED_PEAK", "RED_EXT", "BLUE_PEAK", "BLUE_EXT"})


def iso_date(value: Any) -> str:
    return pd.to_datetime(value).strftime("%Y-%m-%d")


def _broken_extreme_keys(turns: list, start: int, end: int) -> set[tuple[int, str]]:
    keys: set[tuple[int, str]] = set()
    for turn in turns:
        if not (start <= turn.idx <= end):
            continue
        broken_idx = getattr(turn, "broken_point_idx", None)
        if broken_idx is None or not (start <= int(broken_idx) <= end):
            continue
        if turn.turn == "BLUE_TO_RED":
            keys.add((int(broken_idx), "BLUE_EXT"))
        elif turn.turn == "RED_TO_BLUE":
            keys.add((int(broken_idx), "RED_EXT"))
    return keys


def labelable_identity_keys(
    identity_nodes: list,
    hardened_nodes: list,
    last_row: pd.Series,
    turns: list,
    start: int,
    end: int,
) -> set[tuple[int, str]]:
    """与 plot_fengji_structure 一致：哪些身份节点可参与主峰极连线展示（沙盒标注，非 Web 实线）。"""
    hardened_keys = {(int(n.point_idx), str(n.raw_type)) for n in hardened_nodes}
    legal_line = {(int(n.point_idx), str(n.identity)) for n in build_identity_line(identity_nodes)}
    broken_keys = _broken_extreme_keys(turns, start, end)
    redefined_idxs = {
        int(n.point_idx)
        for n in identity_nodes
        if str(getattr(n, "source", "") or "") == "redefined"
    }
    pending_turn = bool(last_row.get("pending_turn", False))
    camp = int(last_row.get("camp", 0) or 0)
    has_red_pair = not pd.isna(last_row.get("red_peak_price")) and not pd.isna(last_row.get("red_ext_price"))
    has_blue_pair = not pd.isna(last_row.get("blue_peak_price")) and not pd.isna(last_row.get("blue_ext_price"))

    keys: set[tuple[int, str]] = set()
    for node in identity_nodes:
        key = (int(node.point_idx), str(node.identity))
        source = str(getattr(node, "source", "") or "")
        hardened_key = (int(node.point_idx), str(node.raw_type))
        if key in broken_keys:
            keys.add(key)
            continue
        if node.identity in {"FAILED_HIGH", "FAILED_LOW"}:
            if int(node.point_idx) in redefined_idxs:
                continue
            keys.add(key)
            continue
        if source == "redefined":
            keys.add(key)
            continue
        if key not in legal_line or hardened_key not in hardened_keys:
            continue
        if pending_turn and node.identity == "RED_PEAK" and camp == 1 and not has_red_pair:
            continue
        if pending_turn and node.identity == "RED_EXT" and camp == 1 and not has_red_pair:
            continue
        if pending_turn and node.identity == "BLUE_PEAK" and camp == -1 and not has_blue_pair:
            continue
        if pending_turn and node.identity == "BLUE_EXT" and camp == -1 and not has_blue_pair:
            continue
        keys.add(key)
    return keys


def hardened_node_excluded_from_solid(engine: Any, node: Any) -> bool:
    """仅排除「已硬化但身份只有 FAILED、没有红/蓝峰极」的节点（AG 类假点）。"""
    matches = [
        item
        for item in (getattr(engine, "identity_nodes", []) or [])
        if int(item.point_idx) == int(node.point_idx) and str(item.raw_type) == str(node.raw_type)
    ]
    if not matches:
        return False
    if any(str(item.identity) in CAMP_IDENTITIES for item in matches):
        return False
    return all(str(item.identity) in {"FAILED_HIGH", "FAILED_LOW"} for item in matches)


def chart_solid_hardened_nodes(
    engine: Any,
    source_df: pd.DataFrame,
    last_row: pd.Series,
    visible_dates: set[str],
    date_key: Callable[[Any], str] | None = None,
) -> list[Any]:
    """物理 hardened 锚点序列（Web 实线端点来源）。"""
    del last_row
    key = date_key or iso_date
    nodes = sorted(getattr(engine, "hardened_nodes", []) or [], key=lambda n: (n.point_idx, n.confirm_idx))
    out: list[Any] = []
    for node in nodes:
        if hardened_node_excluded_from_solid(engine, node):
            continue
        bar_t = key(source_df.iloc[int(node.point_idx)]["date"])
        if bar_t not in visible_dates:
            continue
        out.append(node)
    return out


def running_extreme(source_df: pd.DataFrame, start_idx: int, end_idx: int, want: str) -> tuple[int, float] | None:
    if start_idx > end_idx or start_idx < 0 or end_idx >= len(source_df):
        return None
    segment = source_df.iloc[start_idx : end_idx + 1]
    if segment.empty:
        return None
    if want == "LOW":
        lows = segment["low"].astype(float)
        rel = int(lows.values.argmin())
        return start_idx + rel, float(lows.iloc[rel])
    highs = segment["high"].astype(float)
    rel = int(highs.values.argmax())
    return start_idx + rel, float(highs.iloc[rel])


def _node_bar_time(source_df: pd.DataFrame, node: Any, date_key: Callable[[Any], str]) -> str | None:
    idx = int(node.point_idx)
    if idx < 0 or idx >= len(source_df):
        return None
    return date_key(source_df.iloc[idx]["date"])


def _append_segment(
    segments: list[dict[str, Any]],
    *,
    t0: str,
    p0: float,
    t1: str,
    p1: float,
    seg_type: str,
    style: str = "solid",
    kind: str = "hardened",
) -> None:
    if t0 == t1 and abs(p0 - p1) <= 1e-9:
        return
    segments.append(
        {
            "t0": t0,
            "p0": p0,
            "t1": t1,
            "p1": p1,
            "type": seg_type,
            "style": style,
            "kind": kind,
        }
    )


def _connect_solid_nodes(
    source_df: pd.DataFrame,
    a: Any,
    b: Any,
    segments: list[dict[str, Any]],
    date_key: Callable[[Any], str],
) -> None:
    ta = _node_bar_time(source_df, a, date_key)
    tb = _node_bar_time(source_df, b, date_key)
    if not ta or not tb:
        return
    if str(a.raw_type).upper() == str(b.raw_type).upper():
        bridge_want = "LOW" if str(a.raw_type).upper() == "HIGH" else "HIGH"
        bridge = running_extreme(source_df, int(a.point_idx), int(b.point_idx), bridge_want)
        if bridge is not None:
            bridge_idx, bridge_price = bridge
            bridge_t = date_key(source_df.iloc[bridge_idx]["date"])
            _append_segment(
                segments,
                t0=ta,
                p0=float(a.price),
                t1=bridge_t,
                p1=bridge_price,
                seg_type=str(a.raw_type),
            )
            _append_segment(
                segments,
                t0=bridge_t,
                p0=bridge_price,
                t1=tb,
                p1=float(b.price),
                seg_type=bridge_want,
            )
            return
    _append_segment(
        segments,
        t0=ta,
        p0=float(a.price),
        t1=tb,
        p1=float(b.price),
        seg_type=str(a.raw_type),
    )


def _append_provisional_trail(
    segments: list[dict[str, Any]],
    source_df: pd.DataFrame,
    last: Any,
    end_idx: int,
    date_key: Callable[[Any], str],
) -> None:
    """橡皮筋：最后固化锚点 → 沿区间极值 zigzag → 最新 K（可能走势）。"""
    last_idx = int(last.point_idx)
    if last_idx >= end_idx:
        return
    last_t = _node_bar_time(source_df, last, date_key)
    latest_t = date_key(source_df.iloc[end_idx]["date"])
    if not last_t:
        return

    cur_idx = last_idx
    cur_price = float(last.price)
    cur_type = str(last.raw_type).upper()
    max_legs = max(2, end_idx - last_idx + 2)

    for _ in range(max_legs):
        if cur_idx >= end_idx:
            break
        want = "HIGH" if cur_type == "LOW" else "LOW"
        ext = running_extreme(source_df, cur_idx + 1, end_idx, want)
        if ext is None:
            break
        nxt_idx, nxt_price = int(ext[0]), float(ext[1])
        nxt_t = date_key(source_df.iloc[nxt_idx]["date"])
        cur_t = date_key(source_df.iloc[cur_idx]["date"]) if cur_idx != last_idx else last_t
        if nxt_t != cur_t or abs(nxt_price - cur_price) > 1e-9:
            _append_segment(
                segments,
                t0=cur_t,
                p0=cur_price,
                t1=nxt_t,
                p1=nxt_price,
                seg_type="trail",
                style="dashed",
                kind="provisional",
            )
        if nxt_idx >= end_idx:
            break
        cur_idx = nxt_idx
        cur_price = nxt_price
        cur_type = want

    if not segments or str(segments[-1].get("t1")) != latest_t:
        want = "HIGH" if cur_type == "LOW" else "LOW"
        last_bar = source_df.iloc[end_idx]
        latest_p = float(last_bar["high"] if want == "HIGH" else last_bar["low"])
        start_t = date_key(source_df.iloc[cur_idx]["date"])
        if start_t != latest_t or abs(cur_price - latest_p) > 1e-9:
            _append_segment(
                segments,
                t0=start_t,
                p0=cur_price,
                t1=latest_t,
                p1=latest_p,
                seg_type="trail",
                style="dashed",
                kind="provisional",
            )


def build_hardened_segments(
    engine: Any,
    source_df: pd.DataFrame,
    display_df: pd.DataFrame | None = None,
    os_row_df: pd.DataFrame | None = None,
    date_key: Callable[[Any], str] | None = None,
) -> list[dict[str, Any]]:
    """生成 Web 峰极连线 segments（实线 + 橡皮筋 zigzag 至最新 K）。"""
    key = date_key or iso_date
    display = display_df if display_df is not None else source_df
    os_rows = os_row_df if os_row_df is not None else display
    visible_dates = {key(value) for value in display["date"]}
    last_row = os_rows.iloc[-1] if not os_rows.empty else source_df.iloc[-1]
    visible = chart_solid_hardened_nodes(engine, source_df, last_row, visible_dates, key)
    if not visible:
        return []

    segments: list[dict[str, Any]] = []
    for a, b in zip(visible[:-1], visible[1:]):
        if a.point_idx == b.point_idx:
            continue
        _connect_solid_nodes(source_df, a, b, segments, key)

    last = visible[-1]
    last_idx = int(last.point_idx)
    end_idx = len(source_df) - 1
    last_t = _node_bar_time(source_df, last, key)
    latest_t = key(source_df.iloc[end_idx]["date"])
    if not last_t or last_idx >= end_idx or latest_t not in visible_dates:
        return segments

    _append_provisional_trail(segments, source_df, last, end_idx, key)
    return segments


def sandbox_hardened_segments(
    engine: Any,
    source_df: pd.DataFrame,
    visible_dates: set[str] | None = None,
    date_key: Callable[[Any], str] | None = None,
) -> list[dict[str, Any]]:
    """沙盒参考：全部 hardened_nodes 直连（含 FAILED，无桥接）。"""
    key = date_key or iso_date
    if visible_dates is None:
        visible_dates = {key(value) for value in source_df["date"]}
    nodes = sorted(getattr(engine, "hardened_nodes", []) or [], key=lambda n: (n.point_idx, n.confirm_idx))
    visible = [n for n in nodes if key(source_df.iloc[int(n.point_idx)]["date"]) in visible_dates]
    segments: list[dict[str, Any]] = []
    for a, b in zip(visible[:-1], visible[1:]):
        if a.point_idx == b.point_idx:
            continue
        ta = _node_bar_time(source_df, a, key)
        tb = _node_bar_time(source_df, b, key)
        if not ta or not tb:
            continue
        _append_segment(
            segments,
            t0=ta,
            p0=float(a.price),
            t1=tb,
            p1=float(b.price),
            seg_type=str(a.raw_type),
        )
    return segments


@dataclass(frozen=True)
class SegmentAuditIssue:
    code: str
    message: str
    segment_index: int | None = None


def _segment_style(segment: dict[str, Any]) -> str:
    if segment.get("style") in {"dashed", "solid"}:
        return str(segment["style"])
    if segment.get("kind") == "provisional" or segment.get("type") == "trail":
        return "dashed"
    return "solid"


def _is_solid(segment: dict[str, Any]) -> bool:
    return _segment_style(segment) == "solid"


def audit_hardened_segments(
    segments: list[dict[str, Any]],
    bar_dates: set[str],
    *,
    require_trail: bool = True,
    last_bar_date: str | None = None,
) -> list[SegmentAuditIssue]:
    """审计 Web 峰极连线 segments，返回全部违规项。"""
    issues: list[SegmentAuditIssue] = []
    if not segments:
        if bar_dates:
            issues.append(SegmentAuditIssue("EMPTY_SEGMENTS", "有 K 线但 hardened_segments 为空"))
        return issues

    solid = [s for s in segments if _is_solid(s)]
    dashed = [s for s in segments if not _is_solid(s)]

    for i, seg in enumerate(segments):
        t0 = str(seg.get("t0", ""))
        t1 = str(seg.get("t1", ""))
        if t0 and t1 and t0 > t1:
            issues.append(SegmentAuditIssue("DATE_ORDER", f"段 {i} 时间逆序: {t0}>{t1}", i))
        if t0 and t0 not in bar_dates:
            issues.append(SegmentAuditIssue("DATE_MISSING", f"段 {i} t0={t0} 不在 bars 日期集", i))
        if t1 and t1 not in bar_dates:
            issues.append(SegmentAuditIssue("DATE_MISSING", f"段 {i} t1={t1} 不在 bars 日期集", i))

    for i in range(len(solid) - 1):
        a, b = solid[i], solid[i + 1]
        if str(a.get("t1")) != str(b.get("t0")) or abs(float(a.get("p1", 0)) - float(b.get("p0", 0))) > 1e-6:
            issues.append(
                SegmentAuditIssue(
                    "SOLID_CHAIN_BREAK",
                    f"实线链断裂: 段 {i} 终点与段 {i+1} 起点不一致",
                    i,
                )
            )

    if dashed:
        for i in range(len(dashed) - 1):
            a, b = dashed[i], dashed[i + 1]
            if str(a.get("t1")) != str(b.get("t0")) or abs(float(a.get("p1", 0)) - float(b.get("p0", 0))) > 1e-6:
                issues.append(
                    SegmentAuditIssue(
                        "TRAIL_CHAIN_BREAK",
                        f"橡皮筋链断裂: 虚线段 {i} 与 {i+1} 未衔接",
                        i,
                    )
                )
    if require_trail and last_bar_date and solid:
        last_solid = solid[-1]
        if str(last_solid.get("t1")) != last_bar_date:
            if not dashed:
                issues.append(SegmentAuditIssue("TRAIL_MISSING", f"最后固化点 {last_solid.get('t1')} 未到最新 K {last_bar_date}"))
            else:
                trail_head = dashed[0]
                trail_tail = dashed[-1]
                if str(trail_tail.get("t1")) != last_bar_date:
                    issues.append(
                        SegmentAuditIssue(
                            "TRAIL_NOT_LATEST",
                            f"橡皮筋终点 {trail_tail.get('t1')} ≠ 最新 K {last_bar_date}",
                            len(segments) - 1,
                        )
                    )
                if str(trail_head.get("t0")) != str(last_solid.get("t1")) or abs(
                    float(trail_head.get("p0", 0)) - float(last_solid.get("p1", 0))
                ) > 1e-6:
                    issues.append(SegmentAuditIssue("TRAIL_CHAIN_BREAK", "橡皮筋起点与最后实线终点不一致"))

    for i, seg in enumerate(solid):
        seg_type = str(seg.get("type", "")).upper()
        if i > 0 and seg_type == str(solid[i - 1].get("type", "")).upper():
            issues.append(
                SegmentAuditIssue(
                    "SOLID_TYPE_REPEAT",
                    f"相邻实线段类型重复 {seg_type}: 段 {i-1}→{i}",
                    i,
                )
            )

    return issues


def audit_web_vs_sandbox(
    engine: Any,
    source_df: pd.DataFrame,
    web_segments: list[dict[str, Any]],
    visible_dates: set[str] | None = None,
    date_key: Callable[[Any], str] | None = None,
) -> list[SegmentAuditIssue]:
    """Web 实线几何应覆盖沙盒 hardened 折线的所有拐点（含 FAILED 桥接后）。"""
    key = date_key or iso_date
    if visible_dates is None:
        visible_dates = {key(value) for value in source_df["date"]}
    sandbox = sandbox_hardened_segments(engine, source_df, visible_dates, key)
    web_solid = [s for s in web_segments if _is_solid(s)]

    sandbox_points: list[tuple[str, float]] = []
    for seg in sandbox:
        sandbox_points.append((str(seg["t0"]), float(seg["p0"])))
        sandbox_points.append((str(seg["t1"]), float(seg["p1"])))
    web_points: list[tuple[str, float]] = []
    for seg in web_solid:
        web_points.append((str(seg["t0"]), float(seg["p0"])))
        web_points.append((str(seg["t1"]), float(seg["p1"])))

    def dedupe(points: list[tuple[str, float]]) -> list[tuple[str, float]]:
        out: list[tuple[str, float]] = []
        for pt in points:
            if not out or out[-1] != pt:
                out.append(pt)
        return out

    sandbox_path = dedupe(sandbox_points)
    web_path = dedupe(web_points)
    issues: list[SegmentAuditIssue] = []
    if len(web_path) < 2:
        return issues
    sandbox_keys = {pt for pt in sandbox_path}
    for pt in web_path:
        if pt not in sandbox_keys:
            issues.append(
                SegmentAuditIssue(
                    "WEB_POINT_NOT_ON_SANDBOX",
                    f"Web 拐点 {pt[0]}@{pt[1]} 不在沙盒 hardened 折线节点集",
                )
            )
    return issues
