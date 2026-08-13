#!/usr/bin/env python3
"""Generate illustrative Lottie JSON for DS01–DS09 + TOTAL.

Storyboard aligned with 峰极总定式规则版/N字突破03.png · N字突破04.png:
  折线逐段绘制 → 前峰/前极水平触发线 → 红/蓝启动棍在突破瞬间出现 → 止损线。
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "web" / "assets" / "lottie"

FR = 30
IP = 0
OP = 300
W, H = 160, 88


def rgba(r: float, g: float, b: float, a: float = 1.0) -> list[float]:
    return [r / 255.0, g / 255.0, b / 255.0, a]


CAMP_RED = rgba(229, 57, 53)
CAMP_BLUE = rgba(0, 122, 255)
PRICE_LINE = rgba(0, 122, 255, 0.92)
GOLD = rgba(212, 175, 55)
GOLD_SOFT = rgba(212, 175, 55, 0.35)
TRIGGER_BLUE = rgba(94, 176, 255)
STICK_ORANGE = rgba(255, 159, 10)
STOP_RED = rgba(255, 69, 58)
CONFIRM_GREEN = rgba(52, 199, 89)
MUTED_GRAY = rgba(134, 134, 139)
VIGNETTE = rgba(10, 11, 16, 0.55)
PEAK_RED = rgba(229, 57, 53, 0.95)
TROUGH_RED = rgba(180, 40, 38, 0.85)
PEAK_BLUE = rgba(45, 82, 152, 0.95)
TROUGH_BLUE = rgba(0, 122, 255, 0.85)


def const(value: Any) -> dict[str, Any]:
    return {"a": 0, "k": value}


def hold_kf(*frames: tuple[int, Any]) -> dict[str, Any]:
    keys: list[dict[str, Any]] = []
    for i, (t, val) in enumerate(frames):
        entry: dict[str, Any] = {"t": t, "s": val if isinstance(val, list) else [val]}
        if i < len(frames) - 1:
            entry["h"] = 1
        keys.append(entry)
    return {"a": 1, "k": keys}


def pct_kf(*frames: tuple[float, Any]) -> dict[str, Any]:
    return hold_kf(*[(int(round(p * OP)), v) for p, v in frames])


def opacity_pct(*frames: tuple[float, float]) -> dict[str, Any]:
    return pct_kf(*[(p, int(round(o * 100))) for p, o in frames])


def trim_end_pct(*frames: tuple[float, float]) -> dict[str, Any]:
    return pct_kf(*[(p, v) for p, v in frames])


def color_pct(*frames: tuple[float, list[float]]) -> dict[str, Any]:
    return pct_kf(*frames)


def group_transform() -> dict[str, Any]:
    return {
        "ty": "tr",
        "p": const([0, 0]),
        "a": const([0, 0]),
        "s": const([100, 100]),
        "r": const(0),
        "o": const(100),
        "sk": const(0),
        "sa": const(0),
        "nm": "Transform",
        "mn": "ADBE Vector Group",
        "hd": False,
    }


def shape_group(shapes: list[dict[str, Any]], name: str = "grp") -> dict[str, Any]:
    items = [*shapes, group_transform()]
    return {
        "ty": "gr",
        "it": items,
        "nm": name,
        "np": len(items),
        "cix": 2,
        "bm": 0,
        "ix": 1,
        "mn": "ADBE Vector Group",
        "hd": False,
    }


def fill(color: list[float] | dict[str, Any], opacity: dict[str, Any] | None = None) -> dict[str, Any]:
    c = color if isinstance(color, dict) else const(color)
    o = opacity or const(100)
    return {"ty": "fl", "c": c, "o": o, "r": 1, "bm": 0, "nm": "Fill", "mn": "ADBE Vector Graphic - Fill", "hd": False}


def stroke(
    color: list[float],
    width: float = 2.0,
    opacity: dict[str, Any] | None = None,
    dash: list[float] | None = None,
) -> dict[str, Any]:
    sh: dict[str, Any] = {
        "ty": "st",
        "c": const(color),
        "o": opacity or const(100),
        "w": const(width),
        "lc": 2,
        "lj": 2,
        "ml": 4,
        "bm": 0,
        "nm": "Stroke",
        "mn": "ADBE Vector Graphic - Stroke",
        "hd": False,
    }
    if dash:
        sh["d"] = 1
        sh["das"] = const(dash[0])
        if len(dash) > 1:
            sh["dg"] = const(dash[1])
    return sh


def polyline(points: list[tuple[float, float]], closed: bool = False) -> dict[str, Any]:
    verts = [[x, y] for x, y in points]
    zero = [[0.0, 0.0] for _ in points]
    return {
        "ty": "sh",
        "ks": const({"i": zero, "o": zero, "v": verts, "c": closed}),
        "nm": "Path",
        "mn": "ADBE Vector Shape - Group",
        "hd": False,
    }


def rect_shape(w: float, h: float, x: float = 0.0, y: float = 0.0, round_r: float = 0.0) -> dict[str, Any]:
    return {
        "ty": "rc",
        "p": const([x, y]),
        "s": const([w, h]),
        "r": const(round_r),
        "nm": "Rect",
        "mn": "ADBE Vector Shape - Rect",
        "hd": False,
    }


def ellipse(rx: float, ry: float, x: float = 0.0, y: float = 0.0) -> dict[str, Any]:
    return {
        "ty": "el",
        "p": const([x, y]),
        "s": const([rx * 2, ry * 2]),
        "nm": "Ellipse",
        "mn": "ADBE Vector Shape - Ellipse",
        "hd": False,
    }


def trim_modifier(end_kf: dict[str, Any], start_kf: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "ty": "tm",
        "s": start_kf or const(0),
        "e": end_kf,
        "o": const(0),
        "m": 1,
        "nm": "Trim",
        "mn": "ADBE Vector Filter - Trim",
        "hd": False,
    }


def layer(
    name: str,
    ind: int,
    shapes: list[dict[str, Any]],
    *,
    opacity: dict[str, Any] | None = None,
    pos: dict[str, Any] | tuple[float, float, float] | None = None,
    scale: dict[str, Any] | None = None,
) -> dict[str, Any]:
    p = pos if isinstance(pos, dict) else const(list(pos or (0, 0, 0)))
    return {
        "ddd": 0,
        "ind": ind,
        "ty": 4,
        "nm": name,
        "sr": 1,
        "ks": {
            "o": opacity or const(100),
            "r": const(0),
            "p": p,
            "a": const([0, 0, 0]),
            "s": scale or const([100, 100, 100]),
        },
        "ao": 0,
        "shapes": shapes,
        "ip": IP,
        "op": OP,
        "st": 0,
        "bm": 0,
    }


# --- N字突破示意几何（对齐 N字突破03/04：1红峰→2红极→突破前峰→红启动棍→3红峰）---
N_LONG = {
    "peak1": (14, 28),
    "trough2": (42, 64),
    "stick": (54, 28),
    "peak3": (94, 22),
    "trigger_y": 28,
    "stop_y": 72,
}

N_SHORT = {
    "peak1": (16, 58),
    "trough2": (44, 28),
    "stick": (56, 58),
    "peak3": (96, 66),
    "trigger_y": 58,
    "stop_y": 22,
}


def seg_trim(start: float, end: float) -> dict[str, Any]:
    return trim_end_pct((0.0, 0), (start, 0), (end, 100), (0.92, 100), (1.0, 100))


def seg_opacity(start: float, end: float) -> dict[str, Any]:
    return opacity_pct((0.0, 0), (start, 0), (end, 1.0), (0.92, 1.0), (1.0, 0.85))


def node_opacity(at: float) -> dict[str, Any]:
    return opacity_pct((0.0, 0), (at, 0), (at + 0.04, 1.0), (0.90, 1.0), (1.0, 0.6))


def line_seg_layer(name: str, ind: int, p1: tuple[float, float], p2: tuple[float, float], t0: float, t1: float, *, width: float = 2.2) -> dict[str, Any]:
    return layer(
        name,
        ind,
        [
            shape_group(
                [
                    polyline([p1, p2]),
                    trim_modifier(seg_trim(t0, t1)),
                    stroke(PRICE_LINE, width, seg_opacity(t0, t1)),
                ],
                name,
            )
        ],
    )


def node_layer(name: str, ind: int, x: float, y: float, at: float, *, kind: str = "peak", camp: str = "red") -> dict[str, Any]:
    if camp == "red":
        fill_c = PEAK_RED if kind == "peak" else TROUGH_RED
    else:
        fill_c = PEAK_BLUE if kind == "peak" else TROUGH_BLUE
    op = node_opacity(at)
    if kind == "peak":
        # 红峰/蓝峰：空心金环，对齐参考图可辨峰点
        r = 4.0
        shapes = [
            shape_group(
                [
                    ellipse(r, r, x, y),
                    fill(const([0, 0, 0, 0]), op),
                    stroke(GOLD, 1.4, op),
                ],
                name,
            )
        ]
    else:
        r = 3.0
        shapes = [shape_group([ellipse(r, r, x, y), fill(fill_c, op)], name)]
    return layer(name, ind, shapes)


def level_guide_layer(name: str, ind: int, y: float, x_peak: float, at: float, *, emphasis: bool = False) -> dict[str, Any]:
    """前峰/前极水平引导线（对齐 N字突破04 短横线）。"""
    op = opacity_pct((0.0, 0), (at, 0), (at + 0.04, 1.0), (0.90, 1.0), (1.0, 0.55))
    color = GOLD if emphasis else rgba(255, 255, 255, 0.55)
    width = 2.0 if emphasis else 1.2
    shapes: list[dict[str, Any]] = [
        shape_group(
            [
                polyline([(8, y), (152, y)]),
                stroke(color, width, op),
            ],
            "guide_full",
        ),
        shape_group(
            [
                polyline([(x_peak - 4, y), (x_peak + 22, y)]),
                stroke(GOLD, 2.4, op),
            ],
            "guide_peak_tick",
        ),
    ]
    return layer(name, ind, shapes)


def breakthrough_flash_layer(name: str, ind: int, x: float, y: float, at: float) -> dict[str, Any]:
    op = opacity_pct((0.0, 0), (at - 0.02, 0), (at + 0.03, 0.85), (at + 0.10, 0.2), (1.0, 0))
    scale = hold_kf(
        (0, [0, 0, 100]),
        (int(max(0, at - 0.02) * OP), [0, 0, 100]),
        (int(at * OP), [130, 130, 100]),
        (int((at + 0.10) * OP), [160, 160, 100]),
        (OP, [160, 160, 100]),
    )
    return layer(
        name,
        ind,
        [shape_group([ellipse(10, 10, x, y), fill(GOLD_SOFT, op), stroke(GOLD, 1.2, op)], "flash")],
        scale=scale,
    )


def startup_stick_layer(
    name: str,
    ind: int,
    x: float,
    trigger_y: float,
    at: float,
    *,
    side: str = "long",
) -> dict[str, Any]:
    color = CAMP_RED if side == "long" else CAMP_BLUE
    body_h = 16.0
    body_w = 8.0
    # 启动棍底边落在前峰水平线上，向上生长（对齐参考图「启动棍」）
    bottom_y = trigger_y
    center_y = bottom_y + body_h / 2
    pop = hold_kf(
        (0, [100, 0, 100]),
        (int(at * OP), [100, 0, 100]),
        (int(at * OP) + 12, [100, 110, 100]),
        (int(at * OP) + 24, [100, 100, 100]),
        (int(0.88 * OP), [100, 100, 100]),
        (OP, [100, 92, 100]),
    )
    stick_op = opacity_pct((0.0, 0), (at - 0.01, 0), (at, 1.0), (0.88, 1.0), (1.0, 0.75))
    glow_op = opacity_pct((0.0, 0), (at, 0), (at + 0.04, 0.45), (0.88, 0.35), (1.0, 0.12))
    return {
        "ddd": 0,
        "ind": ind,
        "ty": 4,
        "nm": name,
        "sr": 1,
        "ks": {
            "o": const(100),
            "r": const(0),
            "p": const([x, bottom_y, 0]),
            "a": const([x, bottom_y, 0]),
            "s": pop,
        },
        "ao": 0,
        "shapes": [
            shape_group(
                [
                    rect_shape(body_w + 6, body_h + 6, 0, -body_h / 2, 2),
                    fill(color, glow_op),
                ],
                "stick_glow",
            ),
            shape_group(
                [
                    rect_shape(body_w, body_h, 0, -body_h / 2, 1),
                    fill(color, stick_op),
                ],
                "stick_body",
            ),
        ],
        "ip": IP,
        "op": OP,
        "st": 0,
        "bm": 0,
    }


def stop_line_layer(name: str, ind: int, y: float, at: float) -> dict[str, Any]:
    rise = hold_kf(
        (0, [0, 14, 0]),
        (int(at * OP), [0, 14, 0]),
        (int(at * OP) + 18, [0, 0, 0]),
        (int(0.88 * OP), [0, 0, 0]),
        (OP, [0, 0, 0]),
    )
    op = opacity_pct((0.0, 0.2), (at, 0.2), (at + 0.06, 0.95), (0.88, 0.95), (1.0, 0.5))
    return layer(
        name,
        ind,
        [
            shape_group(
                [
                    polyline([(10, y), (150, y)]),
                    stroke(STOP_RED, 1.4, op),
                ],
                name,
            )
        ],
        pos=rise,
    )


def camp_bg_layer(ind: int, camp: str = "red") -> dict[str, Any]:
    if camp == "red":
        colors = color_pct(
            (0.0, rgba(229, 57, 53, 0.14)),
            (0.55, rgba(229, 57, 53, 0.18)),
            (1.0, rgba(229, 57, 53, 0.12)),
        )
    elif camp == "blue":
        colors = color_pct(
            (0.0, rgba(45, 82, 152, 0.22)),
            (0.55, rgba(45, 82, 152, 0.28)),
            (1.0, rgba(45, 82, 152, 0.18)),
        )
    else:
        colors = color_pct(
            (0.0, rgba(45, 82, 152, 0.20)),
            (0.28, rgba(229, 57, 53, 0.14)),
            (0.55, rgba(45, 82, 152, 0.22)),
            (1.0, rgba(0, 122, 255, 0.12)),
        )
    return layer(
        "camp_bg",
        ind,
        [shape_group([rect_shape(W, H, W / 2, H / 2, 8), fill(colors)], "camp")],
    )


def vignette_layer(ind: int) -> dict[str, Any]:
    return layer(
        "vignette",
        ind,
        [
            shape_group(
                [
                    rect_shape(W - 4, H - 4, W / 2, H / 2, 7),
                    fill(const([0, 0, 0, 0])),
                    stroke(VIGNETTE, 1.0, const(100)),
                ],
                "vignette",
            )
        ],
    )


def build_n_break_layers(
    scene: dict[str, tuple[float, float] | float],
    *,
    camp: str = "red",
    side: str = "long",
    extra: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Core N-break storyboard layers (top → bottom in Lottie stack)."""
    p1 = scene["peak1"]  # type: ignore[index]
    p2 = scene["trough2"]  # type: ignore[index]
    stick = scene["stick"]  # type: ignore[index]
    p3 = scene["peak3"]  # type: ignore[index]
    trigger_y = float(scene["trigger_y"])  # type: ignore[arg-type]
    stop_y = float(scene["stop_y"])  # type: ignore[arg-type]

    extras = extra or []
    ind = 14 + len(extras)
    stick_at = 0.38
    out: list[dict[str, Any]] = [
        stop_line_layer("stop_line", ind, stop_y, 0.58),
    ]
    ind -= 1
    out.append(startup_stick_layer("startup_stick", ind, stick[0], trigger_y, stick_at, side=side))
    ind -= 1
    out.append(breakthrough_flash_layer("break_flash", ind, stick[0], trigger_y, stick_at))
    ind -= 1
    for ex in extras:
        out.append(ex)
        ind -= 1
    out.append(line_seg_layer("seg3", ind, stick, p3, 0.40, 0.56, width=2.4))
    ind -= 1
    out.append(node_layer("node_peak3", ind, p3[0], p3[1], 0.54, kind="peak", camp=camp))
    ind -= 1
    out.append(line_seg_layer("seg2", ind, p2, stick, 0.18, 0.40, width=2.4))
    ind -= 1
    out.append(level_guide_layer("trigger_level", ind, trigger_y, p1[0], 0.14, emphasis=True))
    ind -= 1
    out.append(node_layer("node_trough2", ind, p2[0], p2[1], 0.16, kind="trough", camp=camp))
    ind -= 1
    out.append(line_seg_layer("seg1", ind, p1, p2, 0.04, 0.16, width=2.4))
    ind -= 1
    out.append(node_layer("node_peak1", ind, p1[0], p1[1], 0.04, kind="peak", camp=camp))
    ind -= 1
    out.append(level_guide_layer("trough_guide", ind, p2[1], p2[0], 0.16, emphasis=False))
    ind -= 1
    out.append(vignette_layer(ind))
    ind -= 1
    out.append(camp_bg_layer(ind, camp=camp))
    return out


def build_ds02_extra() -> list[dict[str, Any]]:
    yin_scale = hold_kf((0, [100, 100, 100]), (168, [100, 100, 100]), (192, [115, 100, 100]), (228, [115, 100, 100]), (300, [100, 100, 100]))
    yang_scale = hold_kf((0, [100, 100, 100]), (168, [100, 100, 100]), (192, [85, 100, 100]), (228, [85, 100, 100]), (300, [100, 100, 100]))
    op = opacity_pct((0.0, 0), (0.56, 0), (0.62, 0.9), (0.78, 0.9), (1.0, 0.35))
    return [
        layer("yin", 5, [shape_group([rect_shape(10, 18, 108, 46, 2), fill(rgba(229, 57, 53, 0.55), op)], "yin")], scale=yin_scale),
        layer("yang", 4, [shape_group([rect_shape(10, 22, 122, 42, 2), fill(rgba(0, 122, 255, 0.55), op)], "yang")], scale=yang_scale),
    ]


def build_ds03_extra() -> list[dict[str, Any]]:
    op = opacity_pct((0.0, 0), (0.22, 0), (0.32, 0.85), (0.46, 0.85), (0.56, 0.15), (1.0, 0.15))
    return [
        layer(
            "fake_peak",
            4,
            [shape_group([polyline([(72, 38), (88, 30)]), stroke(rgba(255, 255, 255, 0.9), 1.4, op, dash=[4, 4])], "fake")],
        )
    ]


def build_ds04_extra() -> list[dict[str, Any]]:
    clamp_op = opacity_pct((0.0, 0), (0.36, 0), (0.48, 1.0), (0.76, 1.0), (1.0, 0.5))
    clamp_scale = hold_kf((0, [100, 40, 100]), (108, [100, 40, 100]), (144, [100, 100, 100]), (228, [100, 100, 100]), (300, [100, 90, 100]))
    k2_scale = hold_kf((0, [100, 40, 100]), (112, [100, 40, 100]), (148, [100, 100, 100]), (228, [100, 100, 100]), (300, [100, 90, 100]))
    gold_fill = rgba(212, 175, 55, 0.65)
    return [
        layer("clamp_k1", 6, [shape_group([rect_shape(6, 18, 70, 52, 1), fill(gold_fill)], "k1")], opacity=clamp_op, scale=clamp_scale),
        layer("clamp_k2", 5, [shape_group([rect_shape(6, 24, 80, 48, 1), fill(gold_fill)], "k2")], opacity=clamp_op, scale=k2_scale),
        layer("clamp_k3", 4, [shape_group([rect_shape(6, 18, 90, 52, 1), fill(gold_fill)], "k3")], opacity=clamp_op, scale=clamp_scale),
    ]


def build_ds05_extra() -> list[dict[str, Any]]:
    trim = trim_end_pct((0.0, 0), (0.26, 0), (0.40, 100), (0.70, 100), (1.0, 100))
    op = opacity_pct((0.0, 0), (0.26, 0), (0.40, 1.0), (0.70, 1.0), (1.0, 0.35))
    return [
        layer(
            "finger",
            4,
            [shape_group([polyline([(96, 22), (96, 42)]), trim_modifier(trim), stroke(STICK_ORANGE, 1.5, op)], "finger")],
        )
    ]


def build_ds06_extra() -> list[dict[str, Any]]:
    trim = trim_end_pct((0.0, 0), (0.32, 0), (0.48, 100), (0.74, 100), (1.0, 100))
    op = opacity_pct((0.0, 0), (0.32, 0), (0.48, 1.0), (0.74, 1.0), (1.0, 0.4))
    pts = [(88, 28), (96, 18), (104, 28)]
    return [
        layer("expand_peak", 4, [shape_group([polyline(pts), trim_modifier(trim), stroke(GOLD, 1.5, op)], "expand")]),
    ]


def build_ds07_extra() -> list[dict[str, Any]]:
    trim_a = trim_end_pct((0.0, 0), (0.24, 0), (0.40, 100), (0.80, 100), (1.0, 100))
    op_a = opacity_pct((0.0, 0), (0.24, 0), (0.40, 1.0), (0.80, 1.0), (1.0, 0.45))
    trim_b = trim_end_pct((0.0, 0), (0.32, 0), (0.48, 100), (0.80, 100), (1.0, 100))
    op_b = opacity_pct((0.0, 0), (0.32, 0), (0.48, 1.0), (0.80, 1.0), (1.0, 0.45))
    return [
        layer("res_a", 5, [shape_group([polyline([(20, 62), (70, 38)]), trim_modifier(trim_a), stroke(rgba(0, 122, 255, 0.75), 1.4, op_a)], "res_a")]),
        layer("res_b", 4, [shape_group([polyline([(90, 38), (140, 62)]), trim_modifier(trim_b), stroke(rgba(255, 159, 10, 0.75), 1.4, op_b)], "res_b")]),
    ]


def build_ds08_extra() -> list[dict[str, Any]]:
    pts = [(16, 30), (44, 62), (56, 30), (96, 24), (118, 48)]
    layers_out: list[dict[str, Any]] = []
    delays = [0.05, 0.18, 0.34, 0.50, 0.58]
    for i, ((x, y), delay) in enumerate(zip(pts, delays)):
        start = int(delay * OP)
        op = hold_kf((0, [0]), (start, [0]), (start + 12, [100]), (int(0.76 * OP), [100]), (300, [50]))
        color = CONFIRM_GREEN if i == 4 else MUTED_GRAY
        layers_out.append(
            layer(f"pt{i+1}", 8 - i, [shape_group([ellipse(2.5, 2.5, x, y), fill(color)], f"pt{i+1}")], opacity=op)
        )
    return layers_out


def build_ds09_extra() -> list[dict[str, Any]]:
    trim = trim_end_pct((0.0, 0), (0.10, 0), (0.28, 100), (0.72, 100), (1.0, 100))
    op_line = opacity_pct((0.0, 0.2), (0.28, 0.75), (0.72, 0.55), (1.0, 0.35))
    burst_scale = hold_kf((0, [0, 0, 100]), (102, [0, 0, 100]), (132, [100, 100, 100]), (240, [100, 100, 100]), (300, [80, 80, 100]))
    return [
        layer(
            "m15_burst",
            5,
            [
                shape_group(
                    [
                        ellipse(8, 8, 54, 28),
                        fill(rgba(255, 159, 10, 0.32)),
                        stroke(STICK_ORANGE, 1.4),
                    ],
                    "burst",
                )
            ],
            scale=burst_scale,
        ),
        layer(
            "d1_trend",
            4,
            [shape_group([polyline([(8, 68), (152, 36)]), trim_modifier(trim), stroke(GOLD, 1.0, op_line, dash=[3, 3])], "d1")],
        ),
    ]


def build_total_extra() -> list[dict[str, Any]]:
    trim = trim_end_pct((0.0, 0), (0.12, 0), (0.32, 100), (0.72, 100), (1.0, 100))
    op = opacity_pct((0.0, 0), (0.12, 0), (0.32, 0.9), (0.72, 0.9), (1.0, 0.5))
    return [
        layer(
            "total_ring",
            4,
            [shape_group([ellipse(26, 26, 56, 42), trim_modifier(trim), stroke(GOLD, 1.4, op)], "ring")],
        )
    ]


BUILDERS: dict[str, Any] = {
    "DS01": lambda: build_n_break_layers(N_LONG, camp="red", side="long"),
    "DS02": lambda: build_n_break_layers(N_LONG, camp="red", side="long", extra=build_ds02_extra()),
    "DS03": lambda: build_n_break_layers(N_LONG, camp="red", side="long", extra=build_ds03_extra()),
    "DS04": lambda: build_n_break_layers(N_LONG, camp="red", side="long", extra=build_ds04_extra()),
    "DS05": lambda: build_n_break_layers(N_LONG, camp="red", side="long", extra=build_ds05_extra()),
    "DS06": lambda: build_n_break_layers(N_LONG, camp="red", side="long", extra=build_ds06_extra()),
    "DS07": lambda: build_n_break_layers(N_LONG, camp="mix", side="long", extra=build_ds07_extra()),
    "DS08": lambda: build_n_break_layers(N_LONG, camp="red", side="long", extra=build_ds08_extra()),
    "DS09": lambda: build_n_break_layers(N_LONG, camp="red", side="long", extra=build_ds09_extra()),
    "TOTAL": lambda: build_n_break_layers(N_LONG, camp="mix", side="long", extra=build_total_extra()),
}


def build_lottie(name: str) -> dict[str, Any]:
    layers = BUILDERS[name]()
    return {
        "v": "5.7.4",
        "fr": FR,
        "ip": IP,
        "op": OP,
        "w": W,
        "h": H,
        "nm": f"{name} illustration",
        "ddd": 0,
        "assets": [],
        "layers": layers,
    }


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    for sid in BUILDERS:
        path = OUT / f"{sid}.json"
        payload = build_lottie(sid)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        kb = path.stat().st_size / 1024
        print(f"Wrote {path.name} ({kb:.1f} KB, layers={len(payload['layers'])})")
    manifest = OUT / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "version": 5,
                "refinement": "o1_n_breakthrough_v4",
                "storyboard": "N字突破04：前峰金线→折线突破→启动棍底贴线→止损",
                "strategies": list(BUILDERS.keys()),
                "source": "build_strategy_lottie_illustrations.py",
                "drop_in": "Replace DSxx.json with designer export (160x88, 30fps, 300f) then rerun run_o1_lottie_placeholder_acceptance.py",
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"Wrote {manifest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
