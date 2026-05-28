from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.patches import Rectangle

from quant.ds03 import resolve_ds03_attack
from quant.os_engine import BLUE, RED, FengJiOSIdentityEngine


def load_ohlcv(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    if "date" not in df.columns:
        if "timestamp" in df.columns:
            df = df.rename(columns={"timestamp": "date"})
        else:
            raise ValueError(f"{path} must contain date or timestamp")
    df["date"] = pd.to_datetime(df["date"])
    for column in ["open", "high", "low", "close"]:
        df[column] = pd.to_numeric(df[column], errors="coerce")
    return df.dropna(subset=["date", "open", "high", "low", "close"]).reset_index(drop=True)


def draw_candles(ax, window: pd.DataFrame) -> None:
    dates = mdates.date2num(window["date"])
    width = 0.64
    for x, row in zip(dates, window.itertuples(index=False)):
        open_ = float(row.open)
        close = float(row.close)
        high = float(row.high)
        low = float(row.low)
        color = "#d62728" if close >= open_ else "#1f77b4"
        ax.vlines(x, low, high, color=color, linewidth=0.9, alpha=0.9)
        lower = min(open_, close)
        height = max(abs(close - open_), 1e-10)
        ax.add_patch(
            Rectangle(
                (x - width / 2, lower),
                width,
                height,
                facecolor=color,
                edgecolor=color,
                linewidth=0.8,
                alpha=0.72,
            )
        )


def draw_camp_background(ax, os_df: pd.DataFrame, start: int, end: int) -> None:
    dates = mdates.date2num(os_df["date"])
    for idx in range(start, end + 1):
        camp = int(os_df.iloc[idx].get("camp", 0) or 0)
        color = "#ffdddd" if camp == RED else "#dde8ff" if camp == BLUE else "#eeeeee"
        ax.axvspan(dates[idx] - 0.5, dates[idx] + 0.5, facecolor=color, alpha=0.22, linewidth=0)


def draw_hardened_line(ax, df: pd.DataFrame, nodes: list, start: int, end: int) -> None:
    visible = sorted([node for node in nodes if start <= node.point_idx <= end], key=lambda item: item.point_idx)
    if not visible:
        return
    xs = [mdates.date2num(df.iloc[node.point_idx]["date"]) for node in visible]
    ys = [float(node.price) for node in visible]
    ax.plot(xs, ys, color="#6f35b5", linewidth=2.1, marker="o", markersize=4.5, label="FengJi peak-extreme line")
    for node, x, y in zip(visible, xs, ys):
        label = "PEAK" if node.raw_type == "HIGH" else "EXT"
        va = "bottom" if node.raw_type == "HIGH" else "top"
        ax.text(x, y, label, fontsize=7, color="#4a148c", ha="center", va=va)


def draw_failed_nodes(ax, df: pd.DataFrame, engine: FengJiOSIdentityEngine, start: int, end: int) -> None:
    for node in engine.identity_nodes:
        if not str(node.identity).startswith("FAILED"):
            continue
        if not (start <= int(node.point_idx) <= end):
            continue
        x = mdates.date2num(df.iloc[int(node.point_idx)]["date"])
        y = float(node.price)
        ax.scatter(x, y, marker="x", s=90, color="#ff6d00", zorder=8, label="failed peak/low")
        ax.text(x, y, str(node.identity), fontsize=7, color="#e65100", ha="center", va="bottom")


def draw_trigger(ax, df: pd.DataFrame, idx: int, side: str, trigger: float, fill: float, stop: float, ref_idx: int | None, ref: float, source: str) -> None:
    entry_x = mdates.date2num(df.iloc[idx]["date"])
    marker = "^" if side == "long" else "v"
    entry_color = "#00897b" if side == "long" else "#c62828"
    ax.scatter(entry_x, fill, marker=marker, s=140, color=entry_color, edgecolor="white", linewidth=0.8, zorder=9, label="live fill")
    ax.text(entry_x, fill, f"DS03 {side.upper()} fill\n{fill:.8g}", color=entry_color, fontsize=8, ha="center", va="bottom" if side == "long" else "top")
    ax.axhline(trigger, color="#7b1fa2", linestyle="--", linewidth=1.15, label=f"trigger {trigger:.8g}")
    ax.axhline(stop, color="#8e24aa", linestyle=":", linewidth=1.15, label=f"initial stop {stop:.8g}")
    if ref_idx is not None and 0 <= ref_idx < len(df):
        ref_x = mdates.date2num(df.iloc[ref_idx]["date"])
        ax.scatter(ref_x, ref, marker="D", s=80, color="#6a00a8", zorder=8, label=source)
        ax.text(ref_x, ref, f"{source}\n{ref:.8g}", color="#6a00a8", fontsize=8, ha="center", va="bottom")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Plot a live DS03 FengJi sandbox chart.")
    parser.add_argument("--data-dir", default="data")
    parser.add_argument("--symbol", required=True)
    parser.add_argument("--timeframe", default="1d")
    parser.add_argument("--date", required=True)
    parser.add_argument("--side", choices=["long", "short"], required=True)
    parser.add_argument("--fill-price", type=float, required=True)
    parser.add_argument("--trigger-price", type=float, required=True)
    parser.add_argument("--stop-price", type=float, required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--before", type=int, default=90)
    parser.add_argument("--after", type=int, default=6)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    csv_path = Path(args.data_dir) / args.timeframe / f"{args.symbol.upper()}.csv"
    df = load_ohlcv(csv_path)
    engine = FengJiOSIdentityEngine().run(df)
    os_df = engine.to_frame(df)

    target = pd.to_datetime(args.date)
    matches = os_df.index[os_df["date"] == target].tolist()
    if not matches:
        matches = os_df.index[os_df["date"].dt.date == target.date()].tolist()
    if not matches:
        raise ValueError(f"date not found: {args.date}")
    idx = int(matches[-1])

    attack = resolve_ds03_attack(os_df, idx)
    ref_idx = int(attack.ref_idx) if attack is not None and attack.ref_idx is not None else None
    ref = float(attack.entry_ref) if attack is not None else float(args.trigger_price)
    source = str(attack.trigger_source) if attack is not None else "trigger_ref"

    start = max(0, idx - int(args.before))
    end = min(len(df) - 1, idx + int(args.after))
    window = os_df.iloc[start : end + 1].copy()

    fig, ax = plt.subplots(figsize=(15, 8))
    draw_camp_background(ax, os_df, start, end)
    draw_candles(ax, window)
    draw_hardened_line(ax, os_df, engine.hardened_nodes, start, end)
    draw_failed_nodes(ax, os_df, engine, start, end)
    draw_trigger(ax, os_df, idx, args.side, float(args.trigger_price), float(args.fill_price), float(args.stop_price), ref_idx, ref, source)

    row = os_df.iloc[idx]
    camp = "red" if int(row.get("camp", 0) or 0) == RED else "blue" if int(row.get("camp", 0) or 0) == BLUE else "neutral"
    ax.set_title(f"{args.symbol.upper()} DS03 {args.side.upper()} sandbox | {target.date()} | camp={camp} | source={source}")
    ax.set_ylabel("Price")
    ax.grid(True, linestyle=":", alpha=0.28)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m-%d"))
    ax.legend(loc="best", fontsize=8)
    fig.autofmt_xdate()
    fig.tight_layout()

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=180)
    print(f"Saved: {out}")


if __name__ == "__main__":
    main()
