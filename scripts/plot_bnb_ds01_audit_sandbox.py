#!/usr/bin/env python3
"""BNBUSDT 2026-06-07 DS01 审计沙盒 — 对齐 峰极总定式规则版/N字突破03.png、N字突破04.png、峰极图02.png。

裁定要点（图02 / 图03 / 图04 / 真峰假峰，已对齐修复后的 os_engine）：
- 底色读 camp（破极即转势，影线刺破/平级都算）；紫线=hardened_fengji_line 连至窗口内最新 K。
- 红阵营：红峰向上进攻、红极向下防守；蓝阵营：蓝峰向下进攻、蓝极向上防守。
- N字突破04：C 类/整根脱离蓝→红且无假蓝峰可重定义时，启动前蓝峰直接充当新红极（防守极不得为空）。
- BNB：5/28 红转蓝(短暂)、5/31 蓝转红创新高 → 5/28 蓝峰 628.22 重定义为红极；
  6/3 影线/收盘跌破 628.22 → 红转蓝，6/3 起为蓝营 → 6/7 DS01 做多属蓝营逆势（audit_invalid: wrong_direction）。
- 身份标注唯一：被重定义的失败点只显示重定义身份，不再叠加裸假峰标签。
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
if str(ROOT / "packages" / "fengji_core") not in sys.path:
    sys.path.insert(0, str(ROOT / "packages" / "fengji_core"))

from backtest_ds07 import build_os_detail_frame
from plot_fengji_structure import (
    add_camp_legend,
    draw_camp_background,
    draw_candles,
    draw_hardened_line,
    draw_turn_marks,
    identity_display,
    set_chinese_font,
)


def _identity_rank(node) -> int:
    """重定义身份 > 确认的真峰/真极 > 裸失败点。"""
    source = str(getattr(node, "source", "") or "")
    if source == "redefined":
        return 3
    if str(node.identity) in ("FAILED_HIGH", "FAILED_LOW"):
        return 1
    return 2


def draw_all_hardened_labels(ax, df, hardened_nodes, identity_nodes, start, end) -> None:
    """给每个硬化拐点标唯一 OS 身份（重定义优先），保证紫线每个角都有正确标签。"""
    best: dict[int, object] = {}
    for node in identity_nodes:
        idx = int(node.point_idx)
        if best.get(idx) is None or _identity_rank(node) > _identity_rank(best[idx]):
            best[idx] = node
    for node in hardened_nodes:
        idx = int(node.point_idx)
        if not (start <= idx <= end):
            continue
        ident = best.get(idx)
        if ident is None:
            continue
        label, color = identity_display(ident)
        x = mdates.date2num(pd.to_datetime(df.iloc[idx]["date"]))
        y = float(node.price)
        va = "bottom" if str(node.raw_type) == "HIGH" else "top"
        ax.scatter([x], [y], s=66, color=color, edgecolors="white", linewidths=0.7, zorder=6)
        ax.annotate(
            label,
            (x, y),
            textcoords="offset points",
            xytext=(0, 13 if va == "bottom" else -15),
            ha="center",
            va=va,
            color=color,
            fontsize=8.5,
            fontweight="bold",
            bbox={"boxstyle": "round,pad=0.25", "facecolor": "white", "edgecolor": color, "alpha": 0.92},
        )


def load_csv(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    df.columns = [str(c).strip().lower() for c in df.columns]
    if "date" not in df.columns and "timestamp" in df.columns:
        df = df.rename(columns={"timestamp": "date"})
    df["date"] = pd.to_datetime(df["date"])
    for col in ("open", "high", "low", "close", "volume"):
        if col in df.columns:
            df = df.assign(**{col: pd.to_numeric(df[col], errors="coerce")})
    return df.dropna(subset=["date", "open", "high", "low", "close"]).sort_values("date").reset_index(drop=True)


def draw_hardened_line_to_latest(ax, df: pd.DataFrame, hardened_nodes: list, start: int, end: int) -> None:
    """紫线连至最新 K；纳入窗口前最近一颗节点，保证入窗线段不断裂。"""
    lo = start
    for node in hardened_nodes:
        if start - 6 <= node.point_idx < start:
            lo = min(lo, node.point_idx)
    draw_hardened_line(ax, df, hardened_nodes, lo, end)


def red_ext_at(os_df: pd.DataFrame, day: str) -> float | None:
    """读某日的 red_ext_price（已修复引擎下，5/31~6/2 应为 628.22）。"""
    matches = os_df.index[pd.to_datetime(os_df["date"]).dt.normalize() == pd.Timestamp(day).normalize()]
    if not len(matches):
        return None
    val = os_df.iloc[int(matches[-1])].get("red_ext_price")
    try:
        return None if pd.isna(val) else float(val)
    except (TypeError, ValueError):
        return None


def plot_bnb_audit(csv: Path, out: Path, start: str, end: str) -> Path:
    raw = load_csv(csv)
    os_df, engine = build_os_detail_frame(raw, gap=3)
    start_ts = pd.to_datetime(start)
    end_ts = pd.to_datetime(end)
    mask = (pd.to_datetime(os_df["date"]) >= start_ts) & (pd.to_datetime(os_df["date"]) <= end_ts)
    window = os_df[mask].copy()
    if window.empty:
        raise ValueError(f"empty window {start} .. {end}")
    start_idx = int(window.index.min())
    end_idx = int(window.index.max())

    entry_day = pd.Timestamp("2026-06-07")
    entry_matches = os_df.index[pd.to_datetime(os_df["date"]).dt.normalize() == entry_day.normalize()]
    entry_i = int(entry_matches[-1]) if len(entry_matches) else end_idx
    signal_i = entry_i - 1 if entry_i > 0 else entry_i
    signal_row = os_df.iloc[signal_i]
    entry_row = os_df.iloc[entry_i]

    set_chinese_font()
    fig, ax = plt.subplots(figsize=(20, 10), dpi=150)
    draw_camp_background(ax, window)
    draw_candles(ax, window)
    draw_hardened_line_to_latest(ax, os_df, engine.hardened_nodes, start_idx, end_idx)
    draw_all_hardened_labels(ax, os_df, engine.hardened_nodes, engine.identity_nodes, start_idx, end_idx)
    draw_turn_marks(ax, os_df, engine.turns, start_idx, end_idx)
    add_camp_legend(ax)

    red_ext_531 = red_ext_at(os_df, "2026-06-01")
    entry_camp = int(entry_row.get("camp", 0) or 0)

    # 5/31 蓝→红（C类/整根脱离，N04）：启动前 5/28 蓝峰重定义为红极
    for turn in engine.turns:
        if turn.turn == "BLUE_TO_RED" and start_idx <= turn.idx <= end_idx:
            tx = mdates.date2num(pd.to_datetime(os_df.iloc[turn.idx]["date"]))
            re_txt = f"{red_ext_531:.2f}" if red_ext_531 is not None else "(5/28蓝峰)"
            ax.annotate(
                f"C类/整根脱离 蓝→红 (N04)\n创新高破蓝极673 → 切红\n5/28蓝峰 {re_txt} 重定义为红极\n→ 红极防守 {re_txt}",
                (tx, float(os_df.iloc[turn.idx]["high"])),
                xytext=(tx - 4.5, float(os_df.iloc[turn.idx]["high"]) + 40),
                fontsize=8,
                color="#6a1b9a",
                fontweight="bold",
                arrowprops={"arrowstyle": "->", "color": "#6a1b9a", "lw": 1.2},
                bbox={"boxstyle": "round,pad=0.35", "facecolor": "#f3e5f5", "edgecolor": "#6a1b9a", "alpha": 0.95},
            )
        if turn.turn == "RED_TO_BLUE" and start_idx <= turn.idx <= end_idx:
            tx = mdates.date2num(pd.to_datetime(os_df.iloc[turn.idx]["date"]))
            bp = float(getattr(turn, "broken_price", float("nan")))
            bp_txt = f"{bp:.2f}" if bp == bp else "红极"
            ax.annotate(
                f"红→蓝 {str(os_df.iloc[turn.idx]['date'])[:10]}\n影线/收盘跌破红极 {bp_txt}\n→ 转蓝营（防守极上移）",
                (tx, float(os_df.iloc[turn.idx]["low"])),
                xytext=(tx + 0.6, float(os_df.iloc[turn.idx]["low"]) - 46),
                fontsize=8,
                color="#1565c0",
                fontweight="bold",
                arrowprops={"arrowstyle": "->", "color": "#1565c0", "lw": 1.2},
                bbox={"boxstyle": "round,pad=0.35", "facecolor": "#e3f2fd", "edgecolor": "#1565c0", "alpha": 0.95},
            )

    ax.text(
        0.01, 0.74,
        "已对齐修复后的 os_engine：5/31 蓝峰 628.22 → 红极；6/3 破 628.22 红转蓝（影线/平级都算）",
        transform=ax.transAxes, color="#4a148c", fontsize=9, fontweight="bold", va="top",
        bbox={"boxstyle": "round,pad=0.3", "facecolor": "#ede7f6", "edgecolor": "#4a148c", "alpha": 0.95},
    )
    ax.text(
        0.01, 0.68,
        "裁定依据：峰极总定式规则版/N字突破03.png · N字突破04.png · 峰极图02.png · 真峰假峰.png",
        transform=ax.transAxes, color="#4a148c", fontsize=8.5, va="top",
    )

    ex = mdates.date2num(pd.to_datetime(entry_row["date"]))
    trigger = float(signal_row["high"])
    stop_y = float(signal_row["low"])
    ax.axhline(trigger, color="#00695c", linestyle="--", linewidth=1.0, label=f"trigger {trigger:.2f}（几何价，非 OS 授权）")
    ax.axhline(stop_y, color="#c62828", linestyle=":", linewidth=1.0, label=f"stop=昨低 {stop_y:.2f}")
    ax.scatter([ex], [584.66], marker="^", s=200, color="#c62828", edgecolors="white", linewidths=1.2, zorder=9, label="误触发 fill 584.66")
    camp_txt = "蓝营" if entry_camp == -1 else ("红营" if entry_camp == 1 else "中性")
    ax.annotate(
        f"X audit_invalid\n6/7 已是{camp_txt}（6/3 红转蓝）\nDS01 做多=逆势 wrong_direction",
        xy=(ex, 584.66),
        xytext=(ex + 2.6, 690),
        arrowprops={"arrowstyle": "->", "color": "#c62828", "lw": 1.4},
        color="#b71c1c", fontsize=10, fontweight="bold",
        bbox={"boxstyle": "round,pad=0.35", "facecolor": "#ffebee", "edgecolor": "#c62828"},
    )

    ax.set_title(
        "BNBUSDT D1 峰极 OS 审计沙盒（对齐 N字突破03/04 / 峰极图02，引擎已修复）| DS01 ebfd3882 误触发\n"
        "5/25假红峰转蓝极→5/28红转蓝(短暂)→5/31蓝转红创新高(628.22成红极)→6/3破628.22红转蓝→6/7逆势做多无效",
        fontsize=11,
    )
    ax.set_ylabel("Price")
    ax.grid(True, linestyle=":", alpha=0.25)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m-%d"))
    ax.legend(loc="upper right", fontsize=8)
    fig.autofmt_xdate()
    fig.tight_layout()
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out)
    plt.close(fig)
    print(f"saved={out} entry_camp={entry_camp} red_ext_5_31={red_ext_531}")
    return out


def main() -> int:
    p = argparse.ArgumentParser(description="BNB DS01 audit sandbox aligned with N字突破03/峰极图02.")
    p.add_argument("--csv", default=str(ROOT / "data" / "1d" / "BNBUSDT.csv"))
    p.add_argument("--start", default="2026-05-10")
    p.add_argument("--end", default="2026-06-10")
    p.add_argument("--out", default=str(ROOT / "results" / "m5_samples" / "BNBUSDT_ds01_audit_20260607.png"))
    args = p.parse_args()
    plot_bnb_audit(Path(args.csv), Path(args.out), args.start, args.end)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
