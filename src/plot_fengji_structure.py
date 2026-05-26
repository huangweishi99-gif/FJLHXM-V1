from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.patches import Rectangle

from backtest_ds05 import DS05BacktestConfig, build_os_frame
from quant.data import load_ohlcv_for_engine


def set_chinese_font() -> None:
    plt.rcParams["font.sans-serif"] = [
        "Microsoft YaHei",
        "SimHei",
        "Noto Sans CJK SC",
        "Arial Unicode MS",
        "DejaVu Sans",
    ]
    plt.rcParams["axes.unicode_minus"] = False


def draw_candles(ax, df: pd.DataFrame, width: float = 0.62) -> None:
    dates = mdates.date2num(pd.to_datetime(df["date"]).dt.to_pydatetime())
    for x, (_, row) in zip(dates, df.iterrows()):
        open_ = float(row["open"])
        high = float(row["high"])
        low = float(row["low"])
        close = float(row["close"])
        color = "#d62728" if close >= open_ else "#1f77b4"
        body_low = min(open_, close)
        body_height = max(abs(close - open_), 1e-9)
        ax.vlines(x, low, high, color=color, linewidth=0.9, alpha=0.9)
        ax.add_patch(
            Rectangle(
                (x - width / 2, body_low),
                width,
                body_height,
                facecolor=color,
                edgecolor=color,
                linewidth=0.8,
                alpha=0.72,
            )
        )


def draw_camp_background(ax, df: pd.DataFrame) -> None:
    dates = mdates.date2num(pd.to_datetime(df["date"]).dt.to_pydatetime())
    for idx, (_, row) in enumerate(df.iterrows()):
        camp = int(row.get("camp", 0))
        if camp == 0:
            continue
        color = "#ffdddd" if camp == 1 else "#dde8ff"
        ax.axvspan(dates[idx] - 0.5, dates[idx] + 0.5, facecolor=color, alpha=0.32, linewidth=0)


def draw_hardened_line(ax, df: pd.DataFrame, hardened_nodes: list, start: int, end: int) -> None:
    points = [node for node in hardened_nodes if start <= node.point_idx <= end]
    points = sorted(points, key=lambda node: (node.point_idx, node.confirm_idx))
    if len(points) < 2:
        return
    xs = [mdates.date2num(pd.to_datetime(df.iloc[node.point_idx]["date"])) for node in points]
    ys = [node.price for node in points]
    ax.plot(xs, ys, color="#6f35b5", linewidth=2.2, marker="o", markersize=4, label="hardened_fengji_line")
    for node, x, y in zip(points, xs, ys):
        label = "峰" if node.raw_type == "HIGH" else "极"
        va = "bottom" if node.raw_type == "HIGH" else "top"
        ax.text(x, y, label, color="#4a148c", fontsize=9, fontweight="bold", ha="center", va=va)


def add_camp_legend(ax) -> None:
    ax.text(0.01, 0.97, "红色背景 = 红阵营", transform=ax.transAxes, color="#b71c1c", fontsize=10, va="top")
    ax.text(0.01, 0.92, "蓝色背景 = 蓝阵营", transform=ax.transAxes, color="#0d47a1", fontsize=10, va="top")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Plot FengJi hardened line and red/blue camp background.")
    parser.add_argument("--csv", required=True)
    parser.add_argument("--months", type=int, default=6)
    parser.add_argument("--start", default="")
    parser.add_argument("--end", default="")
    parser.add_argument("--out", default="")
    parser.add_argument("--atr-window", type=int, default=14)
    parser.add_argument("--gap", type=int, default=3)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    csv_path = Path(args.csv)
    config = DS05BacktestConfig(atr_window=args.atr_window, gap=args.gap)
    df = load_ohlcv_for_engine(csv_path, config.atr_window)
    os_df, engine = build_os_frame(df, config.gap)

    end_date = pd.to_datetime(args.end) if args.end else pd.to_datetime(os_df["date"].max())
    start_date = pd.to_datetime(args.start) if args.start else end_date - pd.DateOffset(months=args.months)
    mask = (pd.to_datetime(os_df["date"]) >= start_date) & (pd.to_datetime(os_df["date"]) <= end_date)
    window = os_df[mask].copy()
    if window.empty:
        raise ValueError("Selected date window has no rows.")
    start_idx = int(window.index.min())
    end_idx = int(window.index.max())

    set_chinese_font()
    fig, ax = plt.subplots(figsize=(16, 8), dpi=140)
    draw_camp_background(ax, window)
    draw_candles(ax, window)
    draw_hardened_line(ax, os_df, engine.hardened_nodes, start_idx, end_idx)
    add_camp_legend(ax)

    ax.set_title(f"{csv_path.stem} 峰极线与红蓝阵营 | {start_date.date()} 至 {end_date.date()}", fontsize=13)
    ax.set_ylabel("Price")
    ax.grid(True, linestyle=":", alpha=0.28)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m-%d"))
    ax.legend(loc="best", fontsize=8)
    fig.autofmt_xdate()
    fig.tight_layout()

    out_path = Path(args.out) if args.out else Path("results") / "structure" / f"{csv_path.stem}_last_{args.months}m.png"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path)
    plt.close(fig)
    print(f"Saved structure chart to {out_path}")


if __name__ == "__main__":
    main()
