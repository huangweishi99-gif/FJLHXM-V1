#!/usr/bin/env python
"""FJLHXM-UI.pen · 峰极量化 Web 设计稿（Glass Gold · 毛玻璃深色 + 细金边）。"""
from __future__ import annotations

import json
import random
import string
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PEN = ROOT / "FJLHXM-UI.pen"
VERSION_TAG = "Glass Gold V5 · 定稿"

# 深色毛玻璃 + 深蓝中边框（峰极量化视觉规范）
C = {
    "bg": "#0a0b10",
    "bg_deep": "#060608",
    "glass": "#ffffff14",
    "glass_inner": "#ffffff0a",
    "glass_nav": "#ffffff10",
    "glass_plot": "#00000055",
    "text": "#f5f5f7",
    "text2": "#a8a8b3",
    "text3": "#6e6e78",
    "blue": "#5eb0ff",
    "green": "#3ddc84",
    "red": "#ff6b6b",
    "camp_red": "#ff6b6b",
    "camp_blue": "#5eb0ff",
    "gold": "#D4AF37",
    "gold_dim": "#C9A96266",
    "gold_border": "#2d5098cc",
    "border_strong": "#3a6cc8",
    "separator": "#2d509844",
    # legacy aliases used by helpers
    "card": "#ffffff14",
    "bg2": "#ffffff0a",
}

GLASS_BLUR = [{"type": "background_blur", "radius": 24}]
GLASS_SHADOW = [
    {
        "type": "shadow",
        "shadowType": "outer",
        "offset": {"x": 0, "y": 8},
        "blur": 32,
        "spread": 0,
        "color": "#00000055",
    }
]

PAGE_BG = {
    "type": "gradient",
    "gradientType": "radial",
    "center": {"x": 0.5, "y": 0.35},
    "size": {"width": 1.4, "height": 1.2},
    "colors": [
        {"color": "#1a1528", "position": 0},
        {"color": "#0a0b10", "position": 0.55},
        {"color": "#060608", "position": 1},
    ],
}

ORIGIN_X = 3200
ROW_H = 920
COL_W = 1520
PAGE_W = 1280
PAGE_H = 832
CONTENT_W = 1080
LATEST_OPEN_LIMIT = 7
POS_CARD_H = 58
DASH_MODULE_GAP = 16
DASH_INNER_GAP = 12
DASH_PANEL_PAD = 12
POS_SIDEBAR_W = 224


def _id() -> str:
    return "".join(random.choices(string.ascii_letters + string.digits, k=5))


def text(
    content: str,
    *,
    size=14,
    weight="normal",
    fill=None,
    align=None,
    lineHeight=None,
    textGrowth=None,
    width=None,
) -> dict:
    n = {
        "type": "text",
        "id": _id(),
        "name": "Text",
        "content": content,
        "fill": fill or C["text"],
        "fontFamily": "Inter",
        "fontSize": size,
        "fontWeight": weight,
        "lineHeight": lineHeight if lineHeight is not None else (1.35 if size >= 28 else 1.4),
    }
    if align:
        n["textAlign"] = align
    if textGrowth:
        n["textGrowth"] = textGrowth
    if width is not None:
        n["width"] = width
    return n


def box(name, w, h, *, fill=None, layout="vertical", pad=None, gap=0, r=0, children=None, glass=False, gold=False, **kw) -> dict:
    n = {
        "type": "frame",
        "id": _id(),
        "name": name,
        "width": w,
        "height": h,
        "fill": fill if fill is not None else "transparent",
        "layout": layout,
        "clip": True,
        "children": children or [],
    }
    if pad is not None:
        n["padding"] = pad
    if gap:
        n["gap"] = gap
    if r:
        n["cornerRadius"] = r
    if glass:
        n["effect"] = GLASS_BLUR + GLASS_SHADOW
    if gold:
        n["stroke"] = C["gold_border"]
        n["strokeWidth"] = 1.5
        n["strokeAlignment"] = "inner"
    n.update(kw)
    return n


def panel(name, w, h, *, r=16, fill=None, pad=None, gap=0, children=None, **kw) -> dict:
    """毛玻璃组块：半透明底 + 背景模糊 + 细金边 + 圆角。"""
    return box(
        name,
        w,
        h,
        fill=fill if fill is not None else C["glass"],
        r=r,
        pad=pad,
        gap=gap,
        glass=True,
        gold=True,
        children=children,
        **kw,
    )


def inner(name, w, h, *, r=12, fill=None, children=None, **kw) -> dict:
    """组块内层：更淡毛玻璃 + 细金边。"""
    return box(
        name,
        w,
        h,
        fill=fill if fill is not None else C["glass_inner"],
        r=r,
        glass=True,
        gold=True,
        children=children,
        **kw,
    )


def divider(w="fill_container") -> dict:
    return box("Divider", w, 1, fill=C["gold_dim"], layout="none")


def link(label: str, active: bool = False) -> dict:
    return text(label, size=14, weight="500" if active else "normal", fill=C["gold"] if active else C["text2"])


def btn(label: str, *, primary: bool = False) -> dict:
    if primary:
        return box(
            label,
            "fit_content(100)",
            36,
            fill="#5eb0ff33",
            layout="horizontal",
            pad=[0, 18],
            r=980,
            glass=True,
            gold=True,
            alignItems="center",
            justifyContent="center",
            children=[text(label, size=14, weight="500", fill="#ffffff")],
        )
    return box(
        label,
        "fit_content(100)",
        36,
        fill="transparent",
        layout="horizontal",
        pad=[0, 8],
        alignItems="center",
        justifyContent="center",
        children=[text(label, size=14, weight="500", fill=C["blue"])],
    )


def nav(active: str) -> dict:
    items = ["首页", "历史回测", "模拟监测", "策略学堂", "订阅", "交流群"]
    cur = active if active in items else ""
    return box(
        "Nav",
        "fill_container",
        48,
        fill=C["glass_nav"],
        layout="horizontal",
        pad=[0, 48],
        alignItems="center",
        justifyContent="space_between",
        glass=True,
        stroke=C["gold_border"],
        strokeWidth={"bottom": 1.5},
        strokeAlignment="inner",
        children=[
            box(
                "Brand",
                "fit_content(160)",
                32,
                layout="horizontal",
                gap=8,
                alignItems="center",
                children=[
                    box("Mark", 28, 28, fill=C["gold"], r=8, layout="horizontal", alignItems="center", justifyContent="center", children=[
                        text("峰", size=12, weight="700", fill="#0a0b10"),
                    ]),
                    text("峰极量化", size=17, weight="600"),
                ],
            ),
            box(
                "Links",
                "fit_content(520)",
                32,
                layout="horizontal",
                gap=22,
                alignItems="center",
                children=[link(l, l == cur) for l in items],
            ),
            box(
                "Actions",
                "fit_content(380)",
                32,
                layout="horizontal",
                gap=10,
                alignItems="center",
                children=[
                    btn("🌙", primary=False),
                    btn("订阅", primary=False),
                    inner("UserBadge", "fit_content(88)", 28, r=8, pad=[0, 10], alignItems="center", justifyContent="center", fill="#5eb0ff22", children=[
                        text("专业", size=11, weight="600", fill=C["blue"]),
                    ]),
                    text("w08***al", size=11, fill=C["text2"]),
                    btn("退出", primary=False),
                    btn("开始回测", primary=True),
                ],
            ),
        ],
    )


def page_shell(name: str, active: str, body: list, *, x: int, y: int) -> dict:
    return box(
        name,
        PAGE_W,
        PAGE_H,
        fill=PAGE_BG,
        layout="vertical",
        x=x,
        y=y,
        theme={"Mode": "Dark", "Brand": "FengJi"},
        children=[
            nav(active),
            box(
                "Main",
                "fill_container",
                "fill_container",
                layout="vertical",
                alignItems="center",
                pad=[40, 0, 48, 0],
                children=[
                    box("Container", CONTENT_W, "fill_container", layout="vertical", gap=24, alignItems="stretch", children=body),
                ],
            ),
        ],
    )


def tab_row(labels: list[str], active: str) -> dict:
    nodes = []
    for lbl in labels:
        on = lbl == active
        nodes.append(
            box(
                f"Tab/{lbl}",
                "fit_content(72)",
                36,
                layout="vertical",
                gap=6,
                alignItems="center",
                children=[
                    text(lbl, size=14, weight="600" if on else "normal", fill=C["gold"] if on else C["text2"]),
                    box("Line", 24 if on else 0, 2, fill=C["gold"] if on else "transparent", r=1),
                ],
            )
        )
    return box("Tabs", "fill_container", 36, layout="horizontal", gap=24, justifyContent="center", alignItems="center", children=nodes)


def symbol_tf_tab_row(labels: list[str], active: str, *, size: int = 16) -> dict:
    """品种详情页 · 周期 Tab（字号略大，与标题同行）。"""
    nodes = []
    for lbl in labels:
        on = lbl == active
        nodes.append(
            box(
                f"Tab/{lbl}",
                "fit_content(52)",
                38,
                layout="vertical",
                gap=5,
                alignItems="center",
                children=[
                    text(lbl, size=size, weight="600" if on else "normal", fill=C["gold"] if on else C["text2"]),
                    box("Line", 26 if on else 0, 2, fill=C["gold"] if on else "transparent", r=1),
                ],
            )
        )
    return box("Tabs", "fit_content(220)", 38, layout="horizontal", gap=20, alignItems="end", children=nodes)


def _tier_color(tier: str) -> str:
    return {
        "STRONG": C["gold"],
        "MEDIUM": C["blue"],
        "WEAK": C["red"],
        "INSUFFICIENT_DATA": C["text3"],
    }.get(tier, C["text2"])


def _tier_label(tier: str) -> str:
    return {
        "STRONG": "强",
        "MEDIUM": "中",
        "WEAK": "弱",
        "INSUFFICIENT_DATA": "样本不足",
    }.get(tier, tier)


def _center_text(content: str, *, size=14, weight="normal", fill=None) -> dict:
    return text(
        content,
        size=size,
        weight=weight,
        fill=fill or C["text"],
        textGrowth="fixed-width",
        width="fill_container",
        align="center",
        lineHeight=1.25 if size <= 12 else 1.35,
    )


def _pos_card(name: str, dir_lbl: str, sid: str, px: str, tm: str, *, selected: bool = False) -> dict:
    dir_c = C["camp_red"] if dir_lbl == "做多" else C["green"]
    return panel(
        name,
        "fill_container",
        "fill_container",
        r=12,
        pad=[6, 8],
        gap=0,
        layout="vertical",
        justifyContent="stretch",
        alignItems="stretch",
        stroke=C["border_strong"] if selected else C["gold_border"],
        strokeWidth=1.5,
        strokeAlignment="inner",
        children=[
            box(
                "Head",
                "fill_container",
                "fit_content",
                layout="horizontal",
                gap=6,
                alignItems="start",
                justifyContent="space_between",
                children=[
                    text(name, size=11, weight="600", textGrowth="fixed-width", width="fill_container", lineHeight=1.3),
                    text(dir_lbl, size=9, weight="600", fill=dir_c),
                ],
            ),
            box(
                "Core",
                "fill_container",
                "fill_container",
                layout="vertical",
                alignItems="center",
                justifyContent="center",
                pad=[4, 0, 2, 0],
                children=[
                    text(px, size=19, weight="800", fill=C["gold"]),
                ],
            ),
            box(
                "PriceLabel",
                "fill_container",
                "fit_content(12)",
                layout="horizontal",
                justifyContent="end",
                alignItems="end",
                children=[
                    text("开仓价格", size=9, weight="500", fill=C["text2"]),
                ],
            ),
        ],
    )


def _detail_cell(label: str, *value_nodes: dict) -> dict:
    return box(
        label,
        "fill_container",
        "fill_container",
        layout="vertical",
        gap=4,
        alignItems="center",
        justifyContent="center",
        children=[_center_text(label, size=10, fill=C["text2"]), *value_nodes],
    )


def screen_dashboard() -> dict:
    """首页 index.html · 与 Web 一致：加载态侧栏 + 选择品种占位 + 详情格。"""
    detail_labels = [
        "品种",
        "模拟买入",
        "开仓时间",
        "开仓价",
        "手数 / 金额",
        "守护点",
        "信号强弱",
        "净盈亏",
    ]
    detail = panel(
        "Detail",
        "fill_container",
        88,
        r=16,
        layout="horizontal",
        alignItems="stretch",
        gap=0,
        pad=[DASH_PANEL_PAD, DASH_PANEL_PAD],
        children=[
            _detail_cell(lbl, _center_text("—", size=13, weight="600"))
            for lbl in detail_labels
        ],
    )

    chart_mock = panel(
        "ChartMock",
        "fill_container",
        "fill_container",
        r=20,
        layout="vertical",
        pad=[DASH_PANEL_PAD, DASH_PANEL_PAD],
        gap=DASH_INNER_GAP,
        children=[
            box("Toolbar", "fill_container", 24, layout="horizontal", gap=10, alignItems="center", children=[
                text("选择左侧品种", size=16, weight="600"),
                text("—", size=11, fill=C["text2"]),
                inner("CampTag", "fit_content(56)", 22, r=6, pad=[0, 8], alignItems="center", justifyContent="center", fill="#ffffff08", children=[
                    text("峰极 OS", size=10, weight="600", fill=C["gold"]),
                ]),
            ]),
            inner(
                "Plot",
                "fill_container",
                "fill_container",
                r=14,
                layout="vertical",
                alignItems="center",
                justifyContent="center",
                fill=C["glass_plot"],
                children=[
                    text("K 线加载区", size=11, fill=C["text3"]),
                ],
            ),
        ],
    )

    empty_sidebar = panel(
        "Positions",
        POS_SIDEBAR_W,
        "fill_container",
        r=18,
        layout="vertical",
        pad=[DASH_PANEL_PAD, DASH_PANEL_PAD],
        gap=DASH_INNER_GAP,
        alignItems="center",
        justifyContent="center",
        children=[
            text("◌", size=18, fill=C["text3"]),
            text("加载持仓…", size=11, fill=C["text3"]),
        ],
    )

    body = [
        box(
            "MonitorHead",
            "fill_container",
            36,
            layout="horizontal",
            justifyContent="space_between",
            alignItems="center",
            children=[
                box("L", "fit_content(280)", 32, layout="horizontal", gap=10, alignItems="center", children=[
                    box("Dot", 8, 8, fill=C["green"], r=4, layout="none"),
                    text("峰极量化", size=17, weight="600"),
                    inner("Badge", "fit_content(48)", 22, r=6, pad=[0, 8], alignItems="center", justifyContent="center", fill="#ffffff10", children=[
                        text("加载中", size=10, weight="600", fill=C["text2"]),
                    ]),
                ]),
                box("R", "fit_content(160)", 32, layout="horizontal", gap=10, alignItems="center", children=[
                    text("—", size=12, fill=C["text2"]),
                    btn("刷新", primary=False),
                ]),
            ],
        ),
        box(
            "Split",
            "fill_container",
            "fill_container",
            layout="horizontal",
            gap=DASH_MODULE_GAP,
            alignItems="stretch",
            children=[
                empty_sidebar,
                box(
                    "Center",
                    "fill_container",
                    "fill_container",
                    layout="vertical",
                    gap=DASH_MODULE_GAP,
                    alignItems="stretch",
                    children=[chart_mock, detail],
                ),
            ],
        ),
        text(
            "V1 只读模拟监测国内服务器模拟盘，不向交易所发单。数据延迟取决于 paper_state 同步频率。",
            size=11,
            fill=C["text3"],
            align="center",
        ),
    ]
    return page_shell(f"01 · Dashboard · {VERSION_TAG}", "首页", body, x=ORIGIN_X, y=0)


def _toolbar_field(label: str, control: dict) -> dict:
    return box(
        label,
        "fill_container",
        "fit_content",
        layout="vertical",
        gap=6,
        alignItems="stretch",
        children=[
            text(label, size=10, fill=C["text2"]),
            control,
        ],
    )


def _toolbar_control(text_value: str) -> dict:
    return inner(
        "Control",
        "fill_container",
        40,
        r=10,
        pad=[0, 12],
        alignItems="center",
        justifyContent="center",
        children=[text(text_value, size=13, fill=C["text"])],
    )


def _toolbar_market_seg(active: str = "期货") -> dict:
    markets = ["期货", "A股", "虚拟货币", "美国"]
    return inner(
        "MarketSeg",
        "fill_container",
        40,
        r=10,
        pad=3,
        layout="horizontal",
        gap=3,
        alignItems="stretch",
        children=[
            inner(
                m,
                "fill_container",
                "fill_container",
                r=7,
                alignItems="center",
                justifyContent="center",
                fill="rgba(94,176,255,0.22)" if m == active else "transparent",
                children=[text(m, size=11, weight="600" if m == active else "500", fill=C["text"] if m == active else C["text2"])],
            )
            for m in markets
        ],
    )


def _trade_detail_field(label: str, value: str, value_fill: str | None = None) -> dict:
    return panel(
        label,
        "fill_container",
        56,
        r=10,
        pad=[8, 6],
        gap=4,
        alignItems="center",
        children=[
            text(label, size=9, fill=C["text2"]),
            text(value, size=11, weight="600", fill=value_fill or C["text"]),
        ],
    )


def _trade_detail_grid() -> dict:
    columns = [
        [("定式", "DS02"), ("方向", "做多"), ("信号", "中")],
        [("买入时间", "05-12 10:30"), ("买入价", "6120"), ("手数", "2 手")],
        [("卖出时间", "05-18 14:00"), ("平仓价", "6088"), ("净盈亏", "-1200", C["red"])],
    ]
    return box(
        "DetailGrid",
        "fill_container",
        "fill_container",
        layout="horizontal",
        gap=8,
        pad=[10, 10],
        children=[
            box(
                f"Col{ci}",
                "fill_container",
                "fill_container",
                layout="vertical",
                gap=8,
                children=[
                    _trade_detail_field(row[0], row[1], row[2] if len(row) > 2 else None)
                    for row in col
                ],
            )
            for ci, col in enumerate(columns)
        ],
    )


def _years_seg(active: str = "3年") -> dict:
    years = ["1年", "3年", "5年"]
    return inner(
        "YearsSeg",
        "fill_container",
        40,
        r=10,
        pad=3,
        layout="horizontal",
        gap=3,
        alignItems="stretch",
        children=[
            inner(
                y,
                "fill_container",
                "fill_container",
                r=7,
                alignItems="center",
                justifyContent="center",
                fill="rgba(94,176,255,0.22)" if y == active else "transparent",
                children=[text(y, size=11, weight="600" if y == active else "500", fill=C["text"] if y == active else C["text2"])],
            )
            for y in years
        ],
    )


def screen_backtest() -> dict:
    body = [
        panel(
            "Toolbar",
            "fill_container",
            "fit_content(118)",
            r=16,
            pad=[18, 20],
            gap=10,
            children=[
                box(
                    "Row",
                    "fill_container",
                    "fit_content(64)",
                    layout="horizontal",
                    gap=16,
                    alignItems="end",
                    children=[
                        _toolbar_field("品种搜索", _toolbar_control("000021")),
                        _toolbar_field("市场", _toolbar_control("A股")),
                        _toolbar_field("定式", _toolbar_control("TOTAL · 峰极总定式")),
                        _toolbar_field("回测时间", _years_seg("3年")),
                        box(
                            "Action",
                            "fit_content(108)",
                            "fit_content",
                            layout="vertical",
                            gap=6,
                            alignItems="stretch",
                            children=[
                                text("操作", size=10, fill="transparent"),
                                btn("加载回测", primary=True),
                            ],
                        ),
                    ],
                ),
                box(
                    "Hint",
                    "fill_container",
                    "fit_content(20)",
                    layout="horizontal",
                    justifyContent="center",
                    alignItems="center",
                    children=[
                        text("读取样本概览…", size=11, fill=C["text3"], align="center"),
                    ],
                ),
            ],
        ),
        box(
            "Split",
            "fill_container",
            "fill_container",
            layout="horizontal",
            gap=16,
            alignItems="stretch",
            children=[
                box(
                    "Left",
                    "fill_container",
                    "fill_container",
                    layout="vertical",
                    gap=12,
                    children=[
                        panel(
                            "KlineCard",
                            "fill_container",
                            "fill_container",
                            r=16,
                            layout="vertical",
                            pad=0,
                            gap=0,
                            children=[
                                box("Head", "fill_container", 36, layout="horizontal", justifyContent="space_between", alignItems="center", pad=[10, 14], children=[
                                    text("历史回测 K 线", size=12, weight="600", fill=C["text2"]),
                                    text("—", size=10, fill=C["text3"]),
                                ]),
                                inner("Plot", "fill_container", "fill_container", r=0, fill=C["glass_plot"], layout="vertical", alignItems="center", justifyContent="center", gap=6, children=[
                                    text("📈", size=20, fill=C["text3"]),
                                    text("搜索品种并加载回测", size=12, fill=C["text3"]),
                                ]),
                            ],
                        ),
                        panel(
                            "EquityCard",
                            "fill_container",
                            120,
                            r=16,
                            layout="vertical",
                            pad=0,
                            gap=0,
                            children=[
                                box("Head", "fill_container", 32, layout="horizontal", alignItems="center", pad=[10, 14], children=[
                                    text("收益曲线", size=12, weight="600", fill=C["text2"]),
                                ]),
                                inner("Plot", "fill_container", "fill_container", r=0, fill=C["glass_plot"], alignItems="center", justifyContent="center", children=[
                                    text("加载后显示权益走势", size=11, fill=C["text3"]),
                                ]),
                            ],
                        ),
                    ],
                ),
                box(
                    "Right",
                    300,
                    "fill_container",
                    layout="vertical",
                    gap=12,
                    children=[
                        panel(
                            "Summary",
                            "fill_container",
                            "fit_content(120)",
                            r=16,
                            pad=[16, 16],
                            gap=12,
                            alignItems="center",
                            children=[
                                text("—", size=22, weight="700"),
                                box("Stats", "fill_container", 56, layout="horizontal", gap=10, children=[
                                    panel("R", "fill_container", 56, r=10, pad=[10, 12], gap=4, alignItems="center", children=[
                                        text("总收益", size=10, fill=C["text2"]),
                                        text("—", size=18, weight="700"),
                                    ]),
                                    panel("W", "fill_container", 56, r=10, pad=[10, 12], gap=4, alignItems="center", children=[
                                        text("胜率", size=10, fill=C["text2"]),
                                        text("—", size=18, weight="700"),
                                    ]),
                                ]),
                            ],
                        ),
                        panel(
                            "Trades",
                            "fill_container",
                            "fill_container",
                            r=16,
                            layout="vertical",
                            pad=0,
                            gap=0,
                            children=[
                                box("Head", "fill_container", 36, layout="horizontal", alignItems="center", justifyContent="center", gap=8, pad=[10, 14], children=[
                                    text("交易明细", size=12, weight="600", fill=C["text2"]),
                                    btn("导出 CSV", primary=False),
                                ]),
                                box("Empty", "fill_container", 72, layout="vertical", alignItems="center", justifyContent="center", children=[
                                    text("点击 K 线上的买卖点查看该笔交易", size=10, fill=C["text3"]),
                                ]),
                                inner("Bucket", "fill_container", 48, r=0, fill="#08102066", alignItems="center", justifyContent="center", children=[
                                    text("选中一笔交易后显示同桶样本", size=9, fill=C["text3"]),
                                ]),
                                box("Status", "fill_container", 28, alignItems="center", justifyContent="center", children=[
                                    text("就绪", size=10, fill=C["text3"]),
                                ]),
                            ],
                        ),
                    ],
                ),
            ],
        ),
    ]
    return page_shell(f"02 · Backtest · {VERSION_TAG}", "历史回测", body, x=ORIGIN_X, y=ROW_H)


def _pill(label: str) -> dict:
    return inner(label, "fill_container", 40, r=10, pad=[0, 12], alignItems="center", justifyContent="center", children=[text(label, size=13, fill=C["text2"])])


def _scope_btn(label: str, active: bool = False) -> dict:
    if active:
        return box(label, "fill_container", 30, fill="#D4AF3722", r=8, glass=True, gold=True, alignItems="center", justifyContent="center", children=[text(label, size=10, weight="600", fill=C["gold"])])
    return inner(label, "fill_container", 30, r=8, alignItems="center", justifyContent="center", children=[text(label, size=10, weight="600", fill=C["text2"])])


def _bucket_stat(value: str, label: str) -> dict:
    return inner(label, "fill_container", "fill_container", r=8, pad=[5, 4], gap=1, children=[text(value, size=11, weight="700"), text(label, size=8, fill=C["text3"])])


def _trade(ds: str, date: str, pnl: str, active: bool = False) -> dict:
    c = C["green"] if pnl.startswith("+") else C["red"]
    return box(
        date,
        "fill_container",
        44,
        layout="horizontal",
        justifyContent="space_between",
        alignItems="center",
        pad=[8, 4],
        fill="#D4AF3718" if active else "transparent",
        r=10,
        gold=active,
        children=[
            box("L", "fit_content(120)", 24, layout="horizontal", gap=10, children=[text(ds, size=13, weight="600", fill=C["gold"]), text(date, size=13, fill=C["text2"])]),
            text(pnl, size=13, weight="600", fill=c),
        ],
    )


MONITOR_TABLE_COLS = [132, 88, 112, 100, 100, 72, 68, 76, 88]


def _monitor_table_row(cells: list[str], *, header: bool = False, pnl_fill: str | None = None) -> dict:
    h = 36 if header else 48
    return box(
        "HeaderRow" if header else cells[0][:12],
        "fill_container",
        h,
        layout="horizontal",
        alignItems="center",
        justifyContent="space_between",
        pad=[12, 14],
        children=[
            box(
                f"Col{i}",
                w,
                h,
                layout="horizontal",
                alignItems="center",
                justifyContent="center",
                children=[
                    _center_text(
                        cell,
                        size=11 if header else (13 if i == 0 else 12),
                        weight="600",
                        fill=(
                            C["text3"] if header
                            else (pnl_fill if i == 7 and pnl_fill else (C["text"] if i == 0 else C["text2"]))
                        ),
                    ),
                ],
            )
            for i, (cell, w) in enumerate(zip(cells, MONITOR_TABLE_COLS))
        ],
    )


def screen_monitor() -> dict:
    th_labels = ["品种", "开仓定式", "开仓时间", "开仓价格", "目前价格", "信号强弱", "状态", "净盈亏", "操作"]
    empty_row = box(
        "EmptyRow",
        "fill_container",
        72,
        layout="horizontal",
        alignItems="center",
        justifyContent="center",
        children=[
            text("暂无模拟持仓，请从上方添加订阅品种", size=12, fill=C["text3"]),
        ],
    )
    body = [
        box("Head", "fill_container", "fit_content(72)", gap=8, children=[
            text("峰极量化", size=28, weight="600"),
            text("专业订阅 · 最多 50 个自选 · 延迟 准实时 WebSocket", size=15, fill=C["text2"]),
        ]),
        panel(
            "PaperAccount",
            "fill_container",
            "fit_content(140)",
            r=16,
            pad=[16, 16],
            gap=8,
            children=[
                box("PaperHead", "fill_container", 24, layout="horizontal", justifyContent="space_between", alignItems="center", children=[
                    text("观察账户 · 只读模拟", size=13, weight="600"),
                    text("只读模拟", size=10, fill=C["text3"]),
                ]),
                box(
                    "PaperViewTabs",
                    "fill_container",
                    32,
                    layout="horizontal",
                    gap=4,
                    children=[
                        btn("平台参考", primary=True),
                        btn("我的模拟"),
                    ],
                ),
                box("PaperStats", "fill_container", 40, layout="horizontal", gap=12, children=[
                    text("虚拟权益 —", size=12, fill=C["text2"]),
                    text("自选 —", size=12, fill=C["text2"]),
                    text("观察中 —", size=12, fill=C["text2"]),
                    text("相关持仓 —", size=12, fill=C["text2"]),
                ]),
                box(
                    "PaperExecPanel",
                    "fill_container",
                    48,
                    layout="vertical",
                    gap=4,
                    children=[
                        text("我的模拟明细 · 0 持仓 · 0 挂单", size=11, fill=C["text2"]),
                        text("暂无独立模拟持仓或挂单", size=10, fill=C["text3"]),
                    ],
                ),
            ],
        ),
        panel(
            "Ledger",
            "fill_container",
            "fit_content(56)",
            r=16,
            pad=[16, 16],
            children=[
                text("拒单明细 · 0", size=13, weight="600"),
            ],
        ),
        panel(
            "AddBar",
            "fill_container",
            "fit_content(88)",
            r=16,
            pad=[16, 16],
            gap=8,
            children=[
                text("添加品种", size=12, fill=C["text2"]),
                box("AddRow", "fill_container", 40, layout="horizontal", gap=10, children=[
                    _toolbar_control("BTCUSDT · 比特币"),
                    btn("添加", primary=True),
                ]),
                text("全库任选，最多 50 个（与回测共享名额，满额需先移除）", size=10, fill=C["text3"]),
            ],
        ),
        panel(
            "Table",
            "fill_container",
            "fill_container",
            r=18,
            layout="vertical",
            gap=0,
            pad=0,
            children=[
                box(
                    "MarketTabs",
                    "fill_container",
                    44,
                    pad=[12, 16],
                    layout="horizontal",
                    gap=6,
                    alignItems="center",
                    children=[
                        btn("全部", primary=True),
                        btn("期货"),
                        btn("A股"),
                        btn("虚拟币"),
                        btn("美股"),
                    ],
                ),
                divider(),
                _monitor_table_row(th_labels, header=True),
                divider(),
                empty_row,
            ],
        ),
        box("Foot", "fill_container", 20, layout="horizontal", justifyContent="space_between", alignItems="center", children=[
            text("0 / 50 自选 · 0 持仓", size=10, fill=C["text3"]),
            text("WS 连接中…", size=10, fill=C["text3"]),
        ]),
        text("V1 仅模拟观察，不向交易所发单。全站合规文案：模拟实盘、不构成投资建议。", size=10, fill=C["text3"]),
    ]
    return page_shell(f"03 · Monitor · {VERSION_TAG}", "模拟监测", body, x=ORIGIN_X + COL_W, y=0)


def _strategy_animate_card(sid: str, name: str, desc: str = "") -> dict:
    return panel(
        sid,
        "fill_container",
        168,
        r=14,
        pad=[12, 12],
        gap=4,
        layout="vertical",
        children=[
            box("TitleRow", "fill_container", 22, layout="horizontal", alignItems="center", children=[
                box("Id", 40, 22, layout="horizontal", alignItems="center", children=[
                    text(sid, size=10, weight="600", fill=C["gold"]),
                ]),
                box("Name", "fill_container", 22, layout="horizontal", alignItems="center", justifyContent="center", children=[
                    _center_text(name, size=14, weight="600"),
                ]),
                box("Badge", 48, 22, layout="horizontal", alignItems="center", justifyContent="end", children=[
                    text("10s 循环", size=8, weight="600", fill=C["text3"]),
                ]),
            ]),
            box("Desc", "fill_container", 18, alignItems="center", justifyContent="center", children=[
                _center_text(desc[:24] + ("…" if len(desc) > 24 else ""), size=10, fill=C["text2"]),
            ]),
            inner("Animate", "fill_container", 88, r=10, alignItems="center", justifyContent="center", gap=4, children=[
                text("10s Lottie", size=9, fill=C["blue"]),
                text("定式示意动画", size=9, fill=C["text3"]),
            ]),
        ],
    )


def screen_strategies() -> dict:
    items = [
        ("DS01", "挫棍式", "初始挫棍，左30线≤2"),
        ("DS02", "阴阳相吃式", "红阳吃阴 / 蓝阴吃阳"),
        ("DS03", "二四棒式", "合法假峰/假极 + active 结构"),
        ("DS04", "夹棍式", "K1/K2/K3 夹棍结构"),
        ("DS05", "指形式", "K2 可能形成极的位置"),
        ("DS06", "外扩峰式", "转势授权 + 外扩峰启动"),
        ("DS07", "共振式", "同向延续 / 反向并轨"),
        ("DS08", "否认确定式", "五点结构 + 否认/确定"),
        ("DS09", "九重天", "D1 阵营 + M15 二次攻击（A股/LC）"),
        ("TOTAL", "峰极总定式", "DS01–DS08 合一引擎，不反仓"),
    ]
    grid_rows = []
    for ri in range(4):
        row_items = items[ri * 3 : ri * 3 + 3]
        if not row_items:
            break
        grid_rows.append(
            box(
                f"Row{ri}",
                "fill_container",
                168,
                layout="horizontal",
                gap=12,
                alignItems="stretch",
                children=[
                    _strategy_animate_card(sid, name, desc)
                    for sid, name, desc in row_items
                ],
            )
        )
    body = [
        box("Head", "fill_container", "fit_content(56)", gap=4, children=[
            text("峰极定式动画演示", size=26, weight="600"),
            text("九大定式 · Lottie/SVG 约 10 秒循环示意（阵营 · 峰极折线 · 触发 · 止损）", size=14, fill=C["text2"]),
        ]),
        box("Grid", "fill_container", "fit_content(700)", layout="vertical", gap=10, alignItems="stretch", children=grid_rows),
        text("示意动画非真实 K 线回放；规则口径以峰极OS_九大定式规则总纲.md 与 CANONICAL_RULES 为准。", size=10, fill=C["text3"]),
    ]
    return page_shell(f"04 · Strategies · {VERSION_TAG}", "策略学堂", body, x=ORIGIN_X + COL_W, y=ROW_H)


def _pricing_features(items: list[str]) -> dict:
    return box(
        "Features",
        "fill_container",
        "fill_container",
        r=12,
        pad=[12, 12],
        gap=7,
        fill="rgba(8,22,48,0.55)",
        stroke="#1e4a7a",
        strokeWidth=1.5,
        strokeAlignment="inner",
        layout="vertical",
        children=[
            text(f"{i + 1}、{it}", size=10, fill=C["text2"], textGrowth="fixed-width", width="fill_container")
            for i, it in enumerate(items)
        ],
    )


def _pricing_card(
    name: str,
    price: str,
    suffix: str,
    features: list[str],
    *,
    featured: bool = False,
    trial_note: str = "",
    flow_note: str = "",
    cta: str = "了解",
    cta_primary: bool = False,
) -> dict:
    sec_nodes = []
    if trial_note:
        sec_nodes.append(
            box("Trial", "fill_container", "fit_content", r=8, pad=[8, 8], fill="rgba(255,149,0,0.1)", alignItems="stretch", children=[
                text(trial_note, size=9, fill="#ff9500", textGrowth="fixed-width", width="fill_container", align="left"),
            ])
        )
    sec_nodes.append(_pricing_features(features))
    foot_nodes = []
    if flow_note:
        foot_nodes.append(
            text(flow_note, size=9, fill=C["text3"], align="center", textGrowth="fixed-width", width="fill_container", lineHeight=1.4)
        )
    foot_nodes.append(btn(cta, primary=True))
    return panel(
        name,
        "fill_container",
        460,
        r=20,
        pad=[18, 16],
        gap=10,
        layout="vertical",
        alignItems="center",
        stroke=C["border_strong"] if featured else C["gold_border"],
        strokeWidth=2 if featured else 1.5,
        strokeAlignment="inner",
        children=[
            box("Head", "fill_container", "fit_content(56)", gap=4, alignItems="center", children=[
                text(name, size=13, weight="600", fill=C["blue"], align="center"),
                text(price, size=32, weight="700", align="center"),
                text(suffix, size=11, fill=C["text3"], align="center"),
            ]),
            box("Sections", "fill_container", "fill_container", layout="vertical", gap=8, alignItems="center", children=sec_nodes),
            box("Foot", "fill_container", "fit_content(56)" if flow_note else "fit_content(40)", gap=8, alignItems="center", justifyContent="center", layout="vertical", children=foot_nodes),
        ],
    )


def screen_pricing() -> dict:
    cards = [
        _pricing_card(
            "免费",
            "¥0",
            "免费试用 7 天",
            [
                "可用定式 01–03 进行历史回测与模拟监测（不含峰极总定式 TOTAL）",
                "1 年历史回测试用",
                "注册后 7 天有效，期满需升级",
                "模拟监测延迟 15 分钟",
                "回测与监测共享名额，全库任选最多 3 个品种",
            ],
            trial_note="注册后自动开启 7 天试用；期满未订阅将暂停回测与监测权限。",
            cta="注册免费试用",
            cta_primary=True,
        ),
        _pricing_card(
            "标准",
            "¥99",
            "/月",
            [
                "可用定式 01–09 进行历史回测与模拟监测（不含峰极总定式 TOTAL）",
                "1 年、3 年历史回测",
                "模拟监测延迟 1 分钟",
                "回测与监测共享名额，全库任选最多 20 个品种",
                "满额后需先移除已有品种，再添加新品种",
            ],
            featured=True,
            cta="订阅标准档",
        ),
        _pricing_card(
            "专业",
            "¥299",
            "/月",
            [
                "定式 01–09 与峰极总定式 TOTAL 全部可用",
                "1 年、3 年、5 年历史回测",
                "模拟监测 WebSocket 准实时",
                "回测与监测共享名额，全库任选最多 50 个品种",
                "回测支持导出 CSV、查看同类历史成交、按信号强弱筛选",
            ],
            cta="订阅专业档",
            cta_primary=True,
        ),
    ]
    body = [
        box("Head", "fill_container", "fit_content(56)", gap=4, alignItems="center", children=[
            text("峰极量化", size=26, weight="600", align="center"),
            text("按需升级，随时取消。各档权限见下方编号说明。", size=13, fill=C["text2"], align="center"),
        ]),
        box("Row", "fill_container", 460, layout="horizontal", gap=14, alignItems="stretch", children=cards),
        text("订阅与支付模块属 Phase 4；权限以各卡片说明为准。未登录请先注册或登录；答疑请扫码加入交流群。", size=10, fill=C["text3"], align="center"),
    ]
    return page_shell(f"05 · Pricing · {VERSION_TAG}", "订阅", body, x=ORIGIN_X + COL_W * 2, y=ROW_H)


def screen_auth() -> dict:
    body = [
        box("Wrap", "fill_container", "fill_container", layout="vertical", alignItems="center", justifyContent="center", children=[
            panel(
                "AuthCard",
                400,
                420,
                r=18,
                pad=[24, 22],
                gap=14,
                alignItems="stretch",
                children=[
                    box("Head", "fill_container", "fit_content(48)", gap=4, alignItems="center", children=[
                        text("峰极量化", size=22, weight="600", align="center"),
                        text("登录后使用回测、模拟监测与订阅功能", size=12, fill=C["text2"], align="center"),
                    ]),
                    tab_row(["登录", "注册"], "登录"),
                    _toolbar_field("手机号 / 邮箱", _toolbar_control("请输入手机号或邮箱")),
                    _toolbar_field("密码", _toolbar_control("请输入密码")),
                    text("V1：优先连接后端 JWT 登录；API 不可用时回退本地演示态。", size=10, fill=C["text3"], align="center"),
                    box("SubmitRow", "fill_container", "fit_content(40)", layout="horizontal", alignItems="center", justifyContent="center", children=[
                        btn("登录", primary=True),
                    ]),
                    box("FootRow", "fill_container", "fit_content(20)", layout="horizontal", alignItems="center", justifyContent="center", gap=8, children=[
                        text("查看订阅说明", size=10, fill=C["blue"]),
                        text("·", size=10, fill=C["text3"]),
                        text("加入 QQ 群", size=10, fill=C["blue"]),
                        text("·", size=10, fill=C["text3"]),
                        text("先体验回测", size=10, fill=C["blue"]),
                    ]),
                ],
            ),
        ]),
    ]
    return page_shell(f"07 · Auth · {VERSION_TAG}", "", body, x=ORIGIN_X + COL_W * 3, y=0)


def _community_bullets(items: list[str], *, ordered: bool = False) -> dict:
    return box(
        "Bullets",
        "fill_container",
        "fill_container",
        r=12,
        pad=[12, 12],
        gap=6,
        fill="rgba(8,22,48,0.55)",
        stroke="#1e4a7a",
        strokeWidth=1.5,
        strokeAlignment="inner",
        layout="vertical",
        alignItems="stretch",
        children=[
            text(
                f"{i + 1}、{it}" if ordered else f"· {it}",
                size=10,
                fill=C["text2"],
                textGrowth="fixed-width",
                width="fill_container",
                align="left",
            )
            for i, it in enumerate(items)
        ],
    )


def _community_card(
    title: str,
    desc: str,
    qr_caption: str,
    bullets: list[str],
    *,
    featured: bool = False,
    badge: str = "",
    ordered: bool = False,
) -> dict:
    head_nodes = []
    if badge:
        head_nodes.append(
            box("Badge", "fit_content(52)", 22, r=980, pad=[0, 10], fill="rgba(59,130,246,0.18)", stroke="#3b82f666", strokeWidth=1, strokeAlignment="inner", alignItems="center", justifyContent="center", children=[
                text(badge, size=10, weight="600", fill="#93c5fd"),
            ])
        )
    head_nodes.extend([
        text(title, size=15, weight="600", align="center"),
        text(desc, size=11, fill=C["text2"], align="center", textGrowth="fixed-width", width="fill_container"),
    ])
    return panel(
        title,
        "fill_container",
        460,
        r=20,
        pad=[18, 16],
        gap=10,
        layout="vertical",
        alignItems="center",
        stroke=C["border_strong"] if featured else C["gold_border"],
        strokeWidth=2 if featured else 1.5,
        strokeAlignment="inner",
        children=[
            box("Head", "fill_container", "fit_content(72)", gap=6, alignItems="center", children=head_nodes),
            box("QRWrap", 224, 224, r=14, pad=[12, 12], fill="#ffffff", layout="vertical", alignItems="center", justifyContent="center", children=[
                inner("QR", 200, 200, r=10, fill="#f5f5f7", alignItems="center", justifyContent="center", children=[
                    text(qr_caption, size=11, fill=C["text3"], align="center", textGrowth="fixed-width", width=180),
                ]),
            ]),
            _community_bullets(bullets, ordered=ordered),
        ],
    )


def screen_community() -> dict:
    """第 8 屏：交流群 · 只展示 QQ 群二维码。"""
    qq_card = _community_card(
        "官方 QQ 交流群",
        "使用 QQ 扫一扫，加入峰极量化用户群",
        "QQ 群二维码",
        [
            "打开 QQ，点击右上角「+」或扫一扫",
            "扫描上方二维码，申请加入群聊",
            "入群后可咨询回测、监测与订阅相关问题",
        ],
        featured=True,
        badge="推荐",
        ordered=True,
    )
    qq_card["width"] = 420
    body = [
        box("Head", "fill_container", "fit_content(72)", gap=6, alignItems="center", children=[
            text("加入峰极量化交流群", size=26, weight="600", align="center"),
            text(
                "扫码加入官方 QQ 群，获取使用说明、版本更新与策略讨论。",
                size=13,
                fill=C["text2"],
                align="center",
                textGrowth="fixed-width",
                width=560,
            ),
        ]),
        box("Center", "fill_container", "fit_content(520)", layout="horizontal", justifyContent="center", alignItems="stretch", children=[qq_card]),
    ]
    return page_shell(f"08 · Community · {VERSION_TAG}", "交流群", body, x=ORIGIN_X + COL_W * 4, y=0)


def screen_community_pay() -> dict:
    """第 9 屏：订阅付款 · 独立微信收款页（payment.html?pay=standard|pro）。"""
    pay_head = box(
        "Head",
        "fill_container",
        "fit_content(72)",
        gap=6,
        alignItems="center",
        children=[
            box("Badge", "fit_content(52)", 22, r=980, pad=[0, 10], fill="rgba(59,130,246,0.18)", stroke="#3b82f666", strokeWidth=1, strokeAlignment="inner", alignItems="center", justifyContent="center", children=[
                text("标准订阅", size=10, weight="600", fill="#93c5fd"),
            ]),
            text("微信订阅收款", size=15, weight="600", align="center"),
            text("—", size=11, fill=C["text3"], align="center"),
        ],
    )
    pay = panel(
        "微信收款",
        420,
        460,
        r=20,
        pad=[18, 16],
        gap=10,
        layout="vertical",
        alignItems="center",
        stroke=C["border_strong"],
        strokeWidth=2,
        strokeAlignment="inner",
        children=[
            pay_head,
            box("WeChatShell", 224, 260, r=12, layout="vertical", alignItems="stretch", children=[
                box("WeChatHead", "fill_container", 32, fill="#07c160", alignItems="center", justifyContent="center", children=[
                    text("推荐使用微信支付", size=11, weight="600", fill="#ffffff"),
                ]),
                box("WeChatQR", "fill_container", 180, fill="#ffffff", pad=[12, 12], alignItems="center", justifyContent="center", children=[
                    inner("QR", 156, 156, r=8, fill="#f5f5f7", alignItems="center", justifyContent="center", children=[
                        text("微信收款码", size=11, fill=C["text3"], align="center"),
                    ]),
                ]),
                box("WeChatFoot", "fill_container", 28, fill="#ffffff", alignItems="center", justifyContent="center", children=[
                    text("微信支付", size=11, weight="600", fill="#1a1a1a"),
                ]),
            ]),
            _community_bullets(
                ["请使用微信扫一扫完成付款", "付款备注请填写您的登录账号与订阅档位"],
                ordered=False,
            ),
            text("—", size=11, fill=C["text3"], align="center"),
            btn("我已完成付款", primary=True),
            btn("返回订阅页", primary=False),
        ],
    )
    body = [
        box("Head", "fill_container", "fit_content(72)", gap=6, alignItems="center", children=[
            text("订阅付款", size=26, weight="600", align="center"),
            text(
                "请确认订阅档位后，使用微信扫码完成付款。",
                size=13,
                fill=C["text2"],
                align="center",
                textGrowth="fixed-width",
                width=560,
            ),
        ]),
        box("Center", "fill_container", 480, layout="horizontal", justifyContent="center", alignItems="stretch", children=[pay]),
    ]
    return page_shell(f"09 · Payment · {VERSION_TAG}", "订阅", body, x=ORIGIN_X + COL_W * 4, y=ROW_H)


def screen_symbol_chart() -> dict:
    """第 6 屏：模拟监测 · 单品种详情（symbol.html 空闲态）。"""
    detail_cells = [
        "状态", "方向 / 定式", "开仓时间", "开仓价", "现价", "守护止损", "信号强弱", "净盈亏",
    ]
    detail_row = box(
        "DetailGrid",
        "fill_container",
        "fit_content(88)",
        layout="horizontal",
        gap=10,
        children=[
            box(f"D{i}", "fill_container", 72, r=10, pad=[8, 8], fill="rgba(0,0,0,0.28)", stroke=C["gold_border"], strokeWidth=1, strokeAlignment="inner", layout="vertical", gap=4, children=[
                text(lbl, size=9, fill=C["text3"]),
                text("—", size=12, weight="600"),
            ])
            for i, lbl in enumerate(detail_cells)
        ],
    )
    body = [
        box("Head", "fill_container", "fit_content(56)", layout="vertical", gap=8, children=[
            box("Top", "fill_container", 20, layout="horizontal", justifyContent="space_between", alignItems="center", children=[
                text("← 返回模拟监测", size=11, fill=C["blue"]),
                text("—", size=10, fill=C["text3"]),
            ]),
            box("TitleRow", "fill_container", 36, layout="horizontal", gap=12, alignItems="end", children=[
                box("Title", "fit_content(200)", "fit_content(32)", layout="horizontal", gap=0, alignItems="end", children=[
                    text("—", size=28, weight="600"),
                    text(" · 品种详情", size=13, fill=C["text2"]),
                ]),
                symbol_tf_tab_row(["1D", "1H", "15m"], "1D"),
            ]),
            text("—", size=11, fill=C["text3"]),
        ]),
        panel(
            "ChartFull",
            "fill_container",
            240,
            r=20,
            layout="vertical",
            pad=[16, 16],
            gap=8,
            children=[
                box("Toolbar", "fill_container", 24, layout="horizontal", justifyContent="space_between", alignItems="center", children=[
                    text("—", size=10, fill=C["text3"]),
                    btn("刷新", primary=False),
                ]),
                text("K 线 · 峰极线 · 阵营色带 · 守护止损（V1 监测详情以日线为主）。", size=10, fill=C["text2"]),
                inner("Plot", "fill_container", "fill_container", r=12, fill=C["glass_plot"], alignItems="center", justifyContent="center", children=[
                    text("图表加载区", size=12, fill=C["text3"]),
                ]),
            ],
        ),
        detail_row,
        box("Actions", "fill_container", 40, layout="horizontal", gap=12, justifyContent="center", alignItems="center", children=[
            btn("查看历史回测", primary=True),
            btn("移除自选", primary=False),
        ]),
        text("V1 只读模拟监测，不向交易所发单。数据延迟取决于订阅档与 paper_state 同步。", size=10, fill=C["text3"], align="center"),
    ]
    return page_shell(f"06 · Symbol Chart · {VERSION_TAG}", "模拟监测", body, x=ORIGIN_X + COL_W * 3, y=ROW_H)


def build_frames() -> list[dict]:
    return [
        screen_dashboard(),
        screen_backtest(),
        screen_monitor(),
        screen_strategies(),
        screen_pricing(),
        screen_symbol_chart(),
        screen_auth(),
        screen_community(),
        screen_community_pay(),
    ]


def main() -> int:
    data = json.loads(PEN.read_text(encoding="utf-8"))
    data["children"] = [
        c
        for c in data["children"]
        if c.get("id") not in {"QGYHK", "6LMCW"}
        and c.get("name") not in ("dashboard-football", "设计说明", "审阅说明")
        and not str(c.get("name", "")).startswith("FengJi")
        and "Glass Gold" not in str(c.get("name", ""))
        and "Apple V" not in str(c.get("name", ""))
        and "审阅说明" not in str(c.get("name", ""))
    ]
    seen = set()
    kept = []
    for c in data["children"]:
        if c.get("id") in seen:
            continue
        seen.add(c.get("id"))
        kept.append(c)
    data["children"] = kept
    data["children"].extend(build_frames())
    data["children"].append(
        panel(
            f"📐 {VERSION_TAG} · 审阅说明",
            780,
            240,
            fill="#D4AF3718",
            r=18,
            pad=[20, 24],
            gap=8,
            x=ORIGIN_X,
            y=-260,
            layout="vertical",
            children=[
                text(f"峰极量化 Web · {VERSION_TAG}", size=18, weight="600"),
                text("深色径向底 · 毛玻璃 · 细金边 · 2026-06-03 设计定稿", size=13, fill=C["text2"]),
                text(
                    "9 屏：01首页 02回测 03监测 04策略学堂 05订阅 06品种详情 07登录 08交流群 08Pay付款态",
                    size=12,
                    fill=C["text2"],
                ),
                text(
                    "Web 对照：index / backtest / monitor / strategies / pricing / symbol / login / community",
                    size=11,
                    fill=C["text3"],
                ),
            ],
        )
    )
    PEN.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Updated {PEN} · {len(build_frames())} glass-gold screens · {VERSION_TAG}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
