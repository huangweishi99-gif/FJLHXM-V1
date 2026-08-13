#!/usr/bin/env python3
"""Plot DS08 H1 physical sandbox: hardened 峰极连线 + five-point short/long markers."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
for p in (ROOT / "src", ROOT / "packages" / "fengji_core"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from fengji_core.ds08 import node_role
from fengji_core.ds08_pending_fill import load_ds08_h1_os_frame
from backtest_ds07 import build_os_detail_frame
from plot_fengji_structure import draw_camp_background, draw_candles, set_chinese_font


def load_h1_os_frame(symbol: str, data_dir: Path, os_state_dir: Path | None, *, gap: int) -> tuple[pd.DataFrame, object]:
    os_df, engine = load_ds08_h1_os_frame(symbol, data_dir, os_state_dir, gap=gap)
    if not os_df.empty and engine is not None:
        return os_df, engine
    csv_path = resolve_h1_csv(data_dir, symbol)
    raw = pd.read_csv(csv_path)
    if "timestamp" in raw.columns and "date" not in raw.columns:
        raw = raw.rename(columns={"timestamp": "date"})
    raw["date"] = pd.to_datetime(raw["date"])
    raw = raw.sort_values("date").reset_index(drop=True)
    tail = 2400
    if len(raw) > tail:
        raw = raw.tail(tail).reset_index(drop=True)
    return build_os_detail_frame(raw, gap=gap)


def resolve_h1_csv(data_dir: Path, symbol: str) -> Path:
    sym = symbol.upper().replace("-", "")
    for folder in ("1h", "h1"):
        for name in (f"{sym}.csv", f"{sym.replace('USDT', '')}USDT.csv"):
            path = data_dir / folder / name
            if path.is_file():
                return path
    raise FileNotFoundError(f"no 1h csv for {symbol} under {data_dir}")


def find_bar_index(df: pd.DataFrame, when: str) -> int:
    ts = pd.to_datetime(when)
    hits = df.index[pd.to_datetime(df["date"]) <= ts]
    if len(hits) == 0:
        return len(df) - 1
    return int(hits[-1])


def plot_ds08_sandbox(args: argparse.Namespace) -> Path:
    data_dir = Path(args.data_dir)
    os_state = Path(args.os_state_dir) if args.os_state_dir else None
    os_df, engine = load_h1_os_frame(args.symbol, data_dir, os_state, gap=int(args.gap))
    if os_df.empty or engine is None:
        raise RuntimeError("empty H1 OS frame")

    i = find_bar_index(os_df, args.setup_time) if args.setup_time else len(os_df) - 1
    row = os_df.iloc[i]
    hardened = getattr(engine, "hardened_by_bar", None) or []
    skeleton = hardened[i] if i < len(hardened) else []
    if len(skeleton) < 5:
        raise RuntimeError(f"skeleton < 5 at bar {i}")

    tail5 = sorted(skeleton[-5:], key=lambda n: (n.point_idx, n.confirm_idx))
    roles = [node_role(n) for n in tail5]
    side = str(args.side).lower()
    if side == "short":
        if roles != ["P", "V", "P", "V", "P"]:
            raise RuntimeError(f"expected PVPVP short, got {roles}")
        p1, v1, p2, v2, p3 = tail5
        labels = ["P1", "V1", "P2", "V2", "P3"]
        attack_node, defense_node = v2, p3
        pattern = args.pattern or "DS08 Short Power Seizure"
    else:
        if roles != ["V", "P", "V", "P", "V"]:
            raise RuntimeError(f"expected VPVPV long, got {roles}")
        v1, p1, v2, p2, v3 = tail5
        labels = ["V1", "P1", "V2", "P2", "V3"]
        attack_node, defense_node = p2, v3
        pattern = args.pattern or "DS08 Long Power Seizure"

    trigger = float(args.trigger_price) if args.trigger_price else float(attack_node.price)
    stop = float(args.stop_price) if args.stop_price else float(defense_node.price)

    start = max(0, i - int(args.before))
    end = min(len(os_df) - 1, i + int(args.after))
    win = os_df.iloc[start : end + 1].copy()

    set_chinese_font()
    fig, ax = plt.subplots(figsize=(16, 8), dpi=150)
    draw_camp_background(ax, win)
    draw_candles(ax, win)

    # hardened line in window
    pts = sorted([n for n in skeleton if start <= n.point_idx <= end], key=lambda n: (n.point_idx, n.confirm_idx))
    if len(pts) >= 2:
        xs = [mdates.date2num(pd.to_datetime(os_df.iloc[n.point_idx]["date"])) for n in pts]
        ys = [float(n.price) for n in pts]
        ax.plot(xs, ys, color="#6f35b5", linewidth=2.0, marker="o", markersize=4, label="hardened_fengji_line", zorder=5)

    colors = {"P": "#c62828", "V": "#1565c0"}
    for lab, n in zip(labels, tail5):
        role = node_role(n)
        x = mdates.date2num(pd.to_datetime(os_df.iloc[int(n.point_idx)]["date"]))
        y = float(n.price)
        ax.scatter([x], [y], s=120, color=colors[role], edgecolors="white", linewidths=1.2, zorder=7)
        ax.annotate(
            f"{lab}\n{y:.3g}",
            (x, y),
            textcoords="offset points",
            xytext=(0, 14 if role == "P" else -16),
            ha="center",
            fontsize=9,
            fontweight="bold",
            color=colors[role],
            bbox={"boxstyle": "round,pad=0.25", "facecolor": "white", "edgecolor": colors[role], "alpha": 0.9},
        )

    setup_x = mdates.date2num(pd.to_datetime(row["date"]))
    ax.axvline(setup_x, color="#ff9800", linestyle="-.", linewidth=1.2, alpha=0.85, label="setup bar")
    ax.axhline(trigger, color="#7b1fa2", linestyle="--", linewidth=1.3, label=f"trigger V2/P2 {trigger:g}")
    ax.axhline(stop, color="#8e24aa", linestyle=":", linewidth=1.3, label=f"stop P3/V3 {stop:g}")

    camp = int(row.get("camp", 0) or 0)
    camp_txt = "red" if camp == 1 else "blue" if camp == -1 else "neutral"
    title = (
        f"{args.symbol} DS08 H1 sandbox | {side} | {row['date']} | H1 camp={camp_txt}\n"
        f"{pattern} | trigger={trigger:g} stop={stop:g} | roles={''.join(roles)}"
    )
    ax.set_title(title, fontsize=11)
    ax.set_ylabel("H1")
    ax.grid(True, linestyle=":", alpha=0.25)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%m-%d %H:%M"))
    ax.legend(loc="upper left", fontsize=8)
    fig.autofmt_xdate()
    fig.tight_layout()

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out)
    plt.close(fig)
    print(f"saved={out} setup_i={i} roles={roles}")
    return out


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Plot DS08 H1 sandbox with OS hardened line.")
    p.add_argument("--symbol", required=True)
    p.add_argument("--side", default="short", choices=("short", "long"))
    p.add_argument("--setup-time", default="", help="setup bar time (default: last bar)")
    p.add_argument("--trigger-price", type=float, default=0.0)
    p.add_argument("--stop-price", type=float, default=0.0)
    p.add_argument("--pattern", default="five-point short power seizure")
    p.add_argument("--data-dir", default="data")
    p.add_argument("--os-state-dir", default="runtime/fengji_os_state")
    p.add_argument("--out", required=True)
    p.add_argument("--before", type=int, default=72)
    p.add_argument("--after", type=int, default=12)
    p.add_argument("--gap", type=int, default=3)
    return p.parse_args()


if __name__ == "__main__":
    plot_ds08_sandbox(parse_args())
