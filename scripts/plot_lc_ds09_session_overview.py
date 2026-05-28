"""LC 九重天：无成交日也可展示 D1 边界 + M15 夜盘 session 映射（天勤 01:00 口径）。"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.patches import Rectangle

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
os.environ.setdefault("FENGJI_MARKET", "futures")

from backtest_ds09 import build_os_detail_frame, load_frame, load_m15_frame
from fengji_core.ds09 import assign_session_date, build_prev_day_boundary_map


def draw_candles(ax, df: pd.DataFrame, width: float) -> None:
    xs = mdates.date2num(pd.to_datetime(df["date"]))
    for x, (_, row) in zip(xs, df.iterrows()):
        o, h, l, c = float(row["open"]), float(row["high"]), float(row["low"]), float(row["close"])
        color = "#d62728" if c >= o else "#1f77b4"
        ax.vlines(x, l, h, color=color, linewidth=0.8)
        ax.add_patch(Rectangle((x - width / 2, min(o, c)), width, max(abs(c - o), 1e-9), facecolor=color, edgecolor=color, alpha=0.75))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--d1-csv", default=str(ROOT / "data/futures_lc/1d/LC.csv"))
    parser.add_argument("--m15-csv", default=str(ROOT / "data/futures_lc/15m/LC.csv"))
    parser.add_argument("--session-date", default="2026-05-26")
    parser.add_argument("--out", default=str(ROOT / "results/sandbox/lc_ds09/LC_DS09_session_overview.png"))
    args = parser.parse_args()

    d1_raw = load_frame(args.d1_csv, 14)
    m15_raw = load_m15_frame(args.m15_csv, 14)
    d1_os, _ = build_os_detail_frame(d1_raw, 3)
    m15_os, _ = build_os_detail_frame(m15_raw, 3)
    bm = build_prev_day_boundary_map(d1_os)
    m15s = assign_session_date(m15_os, d1_raw, futures=True)

    session = pd.Timestamp(args.session_date).normalize()
    if session not in bm:
        raise SystemExit(f"session {session} not in boundary map")
    info = bm[session]
    day = m15s[pd.to_datetime(m15s["session_date"]).dt.normalize() == session].copy()
    if day.empty:
        raise SystemExit(f"no M15 bars for session {session}")

    d1 = d1_os.copy()
    d1["d"] = pd.to_datetime(d1["date"]).dt.normalize()
    d1_win = d1[(d1["d"] >= session - pd.Timedelta(days=3)) & (d1["d"] <= session + pd.Timedelta(days=1))]

    plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False
    fig, (ax_d1, ax_m15) = plt.subplots(2, 1, figsize=(14, 8), dpi=140, gridspec_kw={"height_ratios": [1, 2]})
    if not d1_win.empty:
        d1_plot = d1_win.copy()
        d1_plot["date"] = pd.to_datetime(d1_plot["d"])
        draw_candles(ax_d1, d1_plot[["date", "open", "high", "low", "close"]], 0.5)
    ax_d1.axhline(float(info["boundary"]), color="#7b1fa2", linestyle="-.", label=f"D1 boundary ({info['mode']})")
    ax_d1.set_title(f"LC D1 | session={session.date()} | prev yin/yang + camp -> {info['mode']}")
    ax_d1.legend(loc="best", fontsize=8)
    ax_d1.grid(True, linestyle=":", alpha=0.3)

    draw_candles(ax_m15, day, 0.003)
    ax_m15.axhline(float(info["boundary"]), color="#7b1fa2", linestyle="-.", label="strategic boundary")
    ax_m15.set_title(
        f"LC M15 session | bars={len(day)} | max_high={day['high'].max():.0f} "
        f"(pierce={'yes' if float(day['high'].max()) > float(info['boundary']) else 'no'}) | "
        f"TQ night bars ~01:00-06:00"
    )
    ax_m15.xaxis.set_major_formatter(mdates.DateFormatter("%m-%d %H:%M"))
    ax_m15.legend(loc="best", fontsize=8)
    ax_m15.grid(True, linestyle=":", alpha=0.3)
    fig.autofmt_xdate()
    fig.tight_layout()
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out)
    plt.close(fig)
    print(f"Saved {out}")


if __name__ == "__main__":
    main()
