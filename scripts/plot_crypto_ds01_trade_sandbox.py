from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path
from typing import Any

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.patches import Rectangle

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))
if str(ROOT / "packages" / "fengji_core") not in sys.path:
    sys.path.insert(0, str(ROOT / "packages" / "fengji_core"))

from backtest_ds07 import build_os_detail_frame
from quant.ds01 import ds01_left_filter_pass, entry_fill


def set_font() -> None:
    plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "Noto Sans CJK SC", "Arial Unicode MS", "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False


def load_ohlcv(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path)
    frame.columns = [str(column).strip().lower() for column in frame.columns]
    if "date" not in frame.columns:
        for candidate in ["timestamp", "datetime", "time"]:
            if candidate in frame.columns:
                frame = frame.rename(columns={candidate: "date"})
                break
    required = ["date", "open", "high", "low", "close", "volume"]
    missing = [column for column in required if column not in frame.columns]
    if missing:
        raise ValueError(f"{path} missing columns: {missing}")
    frame = frame[required].copy()
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
    for column in ["open", "high", "low", "close", "volume"]:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    return frame.dropna(subset=["date", "open", "high", "low", "close"]).sort_values("date").drop_duplicates("date", keep="last").reset_index(drop=True)


def draw_candles(ax: Any, df: pd.DataFrame, width: float = 0.62) -> None:
    xs = mdates.date2num(pd.to_datetime(df["date"]).dt.to_pydatetime())
    for x, (_, row) in zip(xs, df.iterrows()):
        open_ = float(row["open"])
        high = float(row["high"])
        low = float(row["low"])
        close = float(row["close"])
        color = "#d62728" if close >= open_ else "#1f77b4"
        ax.vlines(x, low, high, color=color, linewidth=0.9, alpha=0.95)
        ax.add_patch(
            Rectangle(
                (x - width / 2, min(open_, close)),
                width,
                max(abs(close - open_), 1e-10),
                facecolor=color,
                edgecolor=color,
                linewidth=0.8,
                alpha=0.72,
            )
        )


def draw_camp_background(ax: Any, df: pd.DataFrame) -> None:
    xs = mdates.date2num(pd.to_datetime(df["date"]).dt.to_pydatetime())
    for idx, (_, row) in enumerate(df.iterrows()):
        camp = int(row.get("camp", 0) or 0)
        if camp == 1:
            ax.axvspan(xs[idx] - 0.5, xs[idx] + 0.5, facecolor="#ffdddd", alpha=0.28, linewidth=0)
        elif camp == -1:
            ax.axvspan(xs[idx] - 0.5, xs[idx] + 0.5, facecolor="#dde8ff", alpha=0.30, linewidth=0)


def draw_visible_hardened_line(ax: Any, os_df: pd.DataFrame, nodes: list[Any], start: int, end: int) -> None:
    points = sorted([node for node in nodes if start <= int(node.point_idx) <= end], key=lambda node: (node.point_idx, node.confirm_idx))
    if len(points) < 2:
        return
    xs = [mdates.date2num(pd.to_datetime(os_df.iloc[int(node.point_idx)]["date"])) for node in points]
    ys = [float(node.price) for node in points]
    ax.plot(xs, ys, color="#6f35b5", linewidth=2.0, marker="o", markersize=4.2, label="入场前可见峰极连线")
    for node, x, y in zip(points, xs, ys):
        label = "峰" if str(node.raw_type) == "HIGH" else "极"
        va = "bottom" if str(node.raw_type) == "HIGH" else "top"
        ax.text(x, y, label, color="#4a148c", fontsize=9, fontweight="bold", ha="center", va=va)


def draw_identity_nodes(ax: Any, os_df: pd.DataFrame, identity_nodes: list[Any], start: int, end: int) -> None:
    colors = {
        "RED_EXT": "#c62828",
        "RED_PEAK": "#ef6c00",
        "BLUE_EXT": "#1565c0",
        "BLUE_PEAK": "#00838f",
    }
    for node in identity_nodes:
        idx = int(node.point_idx)
        if idx < start or idx > end:
            continue
        identity = str(node.identity)
        if identity not in colors:
            continue
        x = mdates.date2num(pd.to_datetime(os_df.iloc[idx]["date"]))
        y = float(node.price)
        marker = "s" if identity.endswith("EXT") else "D"
        ax.scatter(x, y, marker=marker, s=62, color=colors[identity], edgecolor="white", linewidth=0.8, zorder=7)
        va = "bottom" if "PEAK" in identity or "EXT" in identity and str(node.raw_type) == "HIGH" else "top"
        ax.text(x, y, identity, color=colors[identity], fontsize=7.5, ha="center", va=va)


def draw_turns(ax: Any, os_df: pd.DataFrame, turns: list[Any], start: int, end: int) -> None:
    for turn in turns:
        idx = int(turn.idx)
        if idx < start or idx > end:
            continue
        x = mdates.date2num(pd.to_datetime(os_df.iloc[idx]["date"]))
        color = "#1565c0" if str(turn.turn) == "RED_TO_BLUE" else "#c62828"
        ax.axvline(x, color=color, linestyle="-.", linewidth=1.0, alpha=0.85)
        broken = float(turn.broken_price)
        ax.hlines(broken, x - 2.5, x + 2.5, color=color, linestyle="-.", linewidth=1.0)
        ax.text(x, broken, f"{turn.turn}\n破{turn.broken_identity} {broken:.8g}", color=color, fontsize=8, ha="center", va="bottom")


def pct(value: float) -> str:
    return "nan" if math.isnan(value) else f"{value:.4%}"


def plot(args: argparse.Namespace) -> Path:
    raw = load_ohlcv(Path(args.csv))
    os_df, engine = build_os_detail_frame(raw, gap=int(args.gap))
    entry_day = pd.to_datetime(args.entry_date).normalize()
    matches = os_df.index[pd.to_datetime(os_df["date"]).dt.normalize() == entry_day]
    if len(matches) == 0:
        raise ValueError(f"entry date not found: {args.entry_date}")
    i = int(matches[-1])
    if i < 1:
        raise ValueError("entry date has no previous signal bar")

    side = -1 if str(args.side).lower() in {"short", "-1"} else 1
    cur = os_df.iloc[i]
    prev = os_df.iloc[i - 1]
    trigger = float(prev["low"] if side == -1 else prev["high"])
    stop = float(prev["high"] if side == -1 else prev["low"])
    fill = entry_fill(cur, side, trigger)
    visible_idx = max(0, i - 1)
    visible_nodes = engine.hardened_by_bar[visible_idx] if engine.hardened_by_bar else []
    left_check_price = float(cur["low"] if side == -1 else cur["high"]) if fill is not None else trigger
    left_ok, left_count = ds01_left_filter_pass(visible_nodes, i, left_check_price, False, 30)
    max_confirm_idx = max((int(node.confirm_idx) for node in visible_nodes), default=-1)

    start = max(0, i - int(args.before))
    end = min(len(os_df) - 1, i + int(args.after))
    window = os_df.iloc[start : end + 1].copy()

    set_font()
    fig, ax = plt.subplots(figsize=(17, 8.5), dpi=150)
    draw_camp_background(ax, window)
    draw_candles(ax, window)
    draw_visible_hardened_line(ax, os_df, visible_nodes, start, end)
    draw_identity_nodes(ax, os_df, engine.identity_nodes, start, end)
    draw_turns(ax, os_df, engine.turns, start, end)

    entry_x = mdates.date2num(pd.to_datetime(cur["date"]))
    signal_x = mdates.date2num(pd.to_datetime(prev["date"]))
    marker = "v" if side == -1 else "^"
    entry_color = "#00897b"
    stop_color = "#c62828"
    trigger_color = "#00695c"

    ax.axvspan(signal_x - 0.45, signal_x + 0.45, facecolor="#ffecb3", alpha=0.35, linewidth=0, label="DS01信号棍")
    ax.axhline(trigger, color=trigger_color, linestyle="--", linewidth=1.1, label=f"触发价 {trigger:.8g}")
    ax.axhline(stop, color=stop_color, linestyle=":", linewidth=1.2, label=f"初始止损 {stop:.8g}")
    ax.scatter(entry_x, float(args.entry_price), marker=marker, s=150, color=entry_color, edgecolor="white", linewidth=1.0, zorder=8, label="买/卖点")

    action = "开空" if side == -1 else "开多"
    ax.annotate(
        f"DS01 {action}\n入场 {float(args.entry_price):.8g}\nleft30={left_count}",
        xy=(entry_x, float(args.entry_price)),
        xytext=(entry_x + 3, float(args.entry_price) * (1.012 if side == -1 else 0.988)),
        arrowprops={"arrowstyle": "->", "color": entry_color, "linewidth": 1.2},
        color=entry_color,
        fontsize=10,
        ha="left",
        va="center",
    )
    ax.text(signal_x, stop if side == -1 else trigger, "信号棍\n昨日阴棍" if side == -1 else "信号棍\n昨日阳棍", color="#6d4c41", fontsize=9, ha="center", va="bottom")

    audit = (
        f"camp_today={int(cur.get('camp', 0))} | camp_signal={int(prev.get('camp', 0))} | "
        f"break={fill is not None} | left_ok={left_ok} left_count={left_count} | "
        f"visible_idx={visible_idx} max_confirm_idx={max_confirm_idx}"
    )
    title = (
        f"{args.symbol} DS01 沙盒图 | {action} | entry={float(args.entry_price):.8g} stop={float(args.stop_price):.8g}\n"
        f"{audit}"
    )
    ax.set_title(title, fontsize=12)
    ax.set_ylabel("Price")
    ax.grid(True, linestyle=":", alpha=0.24)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m-%d"))
    ax.legend(loc="best", fontsize=8)
    ax.text(0.01, 0.03, "红/蓝背景=阵营；紫线=原始硬化峰极连线；RED_EXT/BLUE_EXT=阵营防守极身份", transform=ax.transAxes, fontsize=9, color="#37474f")
    fig.autofmt_xdate()
    fig.tight_layout()

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out)
    plt.close(fig)
    print(
        f"saved={out}\n"
        f"symbol={args.symbol} trigger={trigger:.10g} stop={stop:.10g} fill={fill} "
        f"left_ok={left_ok} left_count={left_count} future_violation={max_confirm_idx > visible_idx}"
    )
    return out


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Plot current crypto DS01 trade sandbox chart.")
    parser.add_argument("--csv", required=True)
    parser.add_argument("--symbol", required=True)
    parser.add_argument("--side", required=True, choices=["long", "short", "1", "-1"])
    parser.add_argument("--entry-date", required=True)
    parser.add_argument("--entry-price", type=float, required=True)
    parser.add_argument("--stop-price", type=float, required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--before", type=int, default=90)
    parser.add_argument("--after", type=int, default=8)
    parser.add_argument("--gap", type=int, default=3)
    return parser.parse_args()


if __name__ == "__main__":
    plot(parse_args())
