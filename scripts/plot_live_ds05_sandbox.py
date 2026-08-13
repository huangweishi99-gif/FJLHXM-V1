#!/usr/bin/env python3
"""Plot a live/open DS05 sandbox chart from runtime fill metadata."""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Any

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.patches import Rectangle

ROOT = Path(__file__).resolve().parents[1]
for search_path in (ROOT / "src", ROOT / "packages" / "fengji_core"):
    if str(search_path) not in sys.path:
        sys.path.insert(0, str(search_path))

from backtest_ds05 import DS05BacktestConfig, build_os_frame
from fengji_core.ds05 import make_ds05_signal
from quant.data import load_ohlcv_for_engine
from quant.futures_specs import get_futures_spec


def set_font() -> None:
    plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "Noto Sans CJK SC", "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False


def parse_setup_dates(setup_key: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for key, raw in re.findall(r"(k[1-3])=(\d{14})", setup_key, flags=re.IGNORECASE):
        values[key.lower()] = f"{raw[:4]}-{raw[4:6]}-{raw[6:8]} {raw[8:10]}:{raw[10:12]}:{raw[12:14]}"
    return values


def find_idx_by_date(df: pd.DataFrame, when: str) -> int:
    target = pd.to_datetime(when)
    dates = pd.to_datetime(df["date"])
    hits = df.index[dates == target].tolist()
    if not hits:
        hits = df.index[dates.dt.normalize() == target.normalize()].tolist()
    if not hits:
        raise ValueError(f"date not found: {when}")
    return int(hits[-1])


def draw_candles(ax: Any, df: pd.DataFrame, width: float = 0.62) -> None:
    xs = mdates.date2num(pd.to_datetime(df["date"]).dt.to_pydatetime())
    for x, (_, row) in zip(xs, df.iterrows()):
        open_ = float(row["open"])
        high = float(row["high"])
        low = float(row["low"])
        close = float(row["close"])
        color = "#d62728" if close >= open_ else "#1f77b4"
        ax.vlines(x, low, high, color=color, linewidth=0.9, alpha=0.92)
        ax.add_patch(
            Rectangle((x - width / 2, min(open_, close)), width, max(abs(close - open_), 1e-9), facecolor=color, edgecolor=color, linewidth=0.8, alpha=0.74)
        )


def draw_camp_background(ax: Any, df: pd.DataFrame) -> None:
    xs = mdates.date2num(pd.to_datetime(df["date"]).dt.to_pydatetime())
    for idx, (_, row) in enumerate(df.iterrows()):
        camp = int(row.get("camp", 0) or 0)
        if camp:
            ax.axvspan(xs[idx] - 0.5, xs[idx] + 0.5, facecolor="#ffdddd" if camp == 1 else "#dde8ff", alpha=0.26, linewidth=0)


def draw_hardened_line(ax: Any, df: pd.DataFrame, nodes: list[Any], start: int, end: int) -> None:
    visible = sorted([node for node in nodes if start <= int(node.point_idx) <= end], key=lambda node: (node.point_idx, node.confirm_idx))
    if len(visible) < 2:
        return
    xs = [mdates.date2num(pd.to_datetime(df.iloc[int(node.point_idx)]["date"])) for node in visible]
    ys = [float(node.price) for node in visible]
    ax.plot(xs, ys, color="#6f35b5", linewidth=2.0, marker="o", markersize=4, label="hardened_fengji_line")


def plot(args: argparse.Namespace) -> Path:
    csv_path = Path(args.csv)
    config = DS05BacktestConfig(futures_mode=True, spec=get_futures_spec(csv_path))
    raw = load_ohlcv_for_engine(csv_path, config.atr_window)
    os_df, engine = build_os_frame(raw, config.gap)
    dates = parse_setup_dates(args.setup_key)
    if "k3" not in dates:
        raise ValueError("setup_key must include k3 timestamp")
    k3_idx = find_idx_by_date(os_df, dates["k3"])
    signal = make_ds05_signal(os_df, k3_idx, config.extreme_atr_tol)
    if signal is None:
        raise ValueError(f"DS05 signal not replayable at k3={dates['k3']}")
    side = 1 if str(args.side).lower() == "long" else -1
    if int(signal.side) != side:
        raise ValueError(f"side mismatch: signal={signal.side} requested={side}")

    start = max(0, int(signal.k1) - int(args.before))
    end = min(len(os_df) - 1, int(signal.activate_idx) + int(args.after))
    window = os_df.iloc[start : end + 1].copy()
    hardened = engine.hardened_by_bar[int(signal.activate_idx)] if int(signal.activate_idx) < len(engine.hardened_by_bar) else engine.hardened_nodes

    set_font()
    fig, ax = plt.subplots(figsize=(16, 8), dpi=150)
    draw_camp_background(ax, window)
    draw_candles(ax, window)
    draw_hardened_line(ax, os_df, hardened, start, end)

    for idx, label in [(signal.k1, "K1"), (signal.k2, "K2"), (signal.k3, "K3 entry")]:
        row = os_df.iloc[int(idx)]
        x = mdates.date2num(pd.to_datetime(row["date"]))
        y = float(row["low"]) if side == 1 and label == "K2" else float(row["high"]) if side == -1 and label == "K2" else float(row["high"] if side == 1 else row["low"])
        ax.text(x, y, label, color="#6a00a8", fontsize=9, fontweight="bold", ha="center", va="bottom" if side == 1 else "top")

    entry_x = mdates.date2num(pd.to_datetime(os_df.iloc[int(signal.activate_idx)]["date"]))
    ax.scatter(entry_x, float(args.fill_price), marker="^" if side == 1 else "v", s=140, color="#00a152", edgecolor="white", linewidth=1.0, zorder=8, label="fill/open")
    ax.annotate(
        f"DS05 {args.side}\nfill {float(args.fill_price):.8g}",
        xy=(entry_x, float(args.fill_price)),
        xytext=(entry_x + 2.5, float(args.fill_price)),
        arrowprops={"arrowstyle": "->", "color": "#00695c", "linewidth": 1.1},
        color="#00695c",
        fontsize=9,
        va="center",
    )
    ax.axhline(float(signal.entry_price), color="#7b1fa2", linestyle="--", linewidth=1.1, label=f"entry ref {signal.entry_price:.8g}")
    ax.axhline(float(args.stop_price), color="#8e24aa", linestyle=":", linewidth=1.1, label=f"initial stop {float(args.stop_price):.8g}")
    ax.set_title(f"{args.symbol} DS05 live sandbox | {args.side} | {dates['k3']} | {signal.pattern} | camp={signal.signal_camp}", fontsize=12)
    ax.set_ylabel("Price")
    ax.grid(True, linestyle=":", alpha=0.25)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m-%d"))
    ax.legend(loc="best", fontsize=8)
    fig.autofmt_xdate()
    fig.tight_layout()
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out)
    plt.close(fig)
    print(f"saved={out} signal={signal.to_dict()}")
    return out


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Plot live/open DS05 sandbox chart.")
    parser.add_argument("--csv", required=True)
    parser.add_argument("--symbol", required=True)
    parser.add_argument("--side", choices=("long", "short"), required=True)
    parser.add_argument("--setup-key", required=True)
    parser.add_argument("--fill-price", type=float, required=True)
    parser.add_argument("--stop-price", type=float, required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--before", type=int, default=45)
    parser.add_argument("--after", type=int, default=20)
    return parser.parse_args()


if __name__ == "__main__":
    plot(parse_args())
