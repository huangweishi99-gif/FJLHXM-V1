#!/usr/bin/env python3
"""Generic DS01 audit sandbox — camp background + hardened line + fill annotation."""
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
from fengji_core.data import load_tq_futures_kline_csv, valid_futures_price_mask
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
    source = str(getattr(node, "source", "") or "")
    if source == "redefined":
        return 3
    if str(node.identity) in ("FAILED_HIGH", "FAILED_LOW"):
        return 1
    return 2


def draw_all_hardened_labels(ax, df, hardened_nodes, identity_nodes, start, end) -> None:
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
            label, (x, y), textcoords="offset points",
            xytext=(0, 13 if va == "bottom" else -15), ha="center", va=va,
            color=color, fontsize=8.5, fontweight="bold",
            bbox={"boxstyle": "round,pad=0.25", "facecolor": "white", "edgecolor": color, "alpha": 0.92},
        )


def load_ohlcv(path: Path, *, market: str) -> pd.DataFrame:
    if market == "futures":
        df = load_tq_futures_kline_csv(path)
        df = df[(df["date"] >= pd.Timestamp("2020-01-01")) & valid_futures_price_mask(df)]
    else:
        df = pd.read_csv(path)
        df.columns = [str(c).strip().lower() for c in df.columns]
        if "date" not in df.columns and "timestamp" in df.columns:
            df = df.rename(columns={"timestamp": "date"})
        df["date"] = pd.to_datetime(df["date"])
        for col in ("open", "high", "low", "close", "volume"):
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")
    return df.dropna(subset=["date", "open", "high", "low", "close"]).sort_values("date").reset_index(drop=True)


def plot_audit(args: argparse.Namespace) -> Path:
    raw = load_ohlcv(Path(args.csv), market=args.market)
    os_df, engine = build_os_detail_frame(raw, gap=int(args.gap))
    start_ts = pd.to_datetime(args.start)
    end_ts = pd.to_datetime(args.end)
    mask = (pd.to_datetime(os_df["date"]) >= start_ts) & (pd.to_datetime(os_df["date"]) <= end_ts)
    window = os_df[mask].copy()
    if window.empty:
        raise ValueError(f"empty window {args.start} .. {args.end}")
    start_idx = int(window.index.min())
    end_idx = int(window.index.max())

    entry_day = pd.Timestamp(args.entry_date).normalize()
    entry_matches = os_df.index[pd.to_datetime(os_df["date"]).dt.normalize() == entry_day]
    if not len(entry_matches):
        raise ValueError(f"entry date not found: {args.entry_date}")
    entry_i = int(entry_matches[-1])
    signal_i = entry_i - 1 if entry_i > 0 else entry_i
    signal_row = os_df.iloc[signal_i]
    entry_row = os_df.iloc[entry_i]
    side = -1 if str(args.side).lower() in {"short", "-1"} else 1

    set_chinese_font()
    fig, ax = plt.subplots(figsize=(18, 9), dpi=150)
    draw_camp_background(ax, window)
    draw_candles(ax, window)
    lo = start_idx
    for node in engine.hardened_nodes:
        if start_idx - 20 <= node.point_idx < start_idx:
            lo = min(lo, node.point_idx)
    draw_hardened_line(ax, os_df, engine.hardened_nodes, lo, end_idx)
    draw_all_hardened_labels(ax, os_df, engine.hardened_nodes, engine.identity_nodes, start_idx, end_idx)
    draw_turn_marks(ax, os_df, engine.turns, start_idx, end_idx)
    add_camp_legend(ax)

    trigger = float(signal_row["low"] if side == -1 else signal_row["high"])
    stop_y = float(signal_row["high"] if side == -1 else signal_row["low"])
    fill_price = float(args.fill_price)
    ex = mdates.date2num(pd.to_datetime(entry_row["date"]))
    signal_camp = int(signal_row.get("camp", 0) or 0)
    entry_camp = int(entry_row.get("camp", 0) or 0)
    expected = -1 if side == -1 else 1
    camp_name = {1: "红营", -1: "蓝营", 0: "中性"}

    ax.axhline(trigger, color="#00695c", linestyle="--", linewidth=1.0, label=f"trigger {trigger:.4g}")
    ax.axhline(stop_y, color="#c62828", linestyle=":", linewidth=1.0, label=f"stop {stop_y:.4g}")
    marker = "v" if side == -1 else "^"
    ax.scatter([ex], [fill_price], marker=marker, s=180, color="#c62828", edgecolors="white", linewidths=1.2, zorder=9)

    verdict = args.verdict or (
        f"signal_camp={signal_camp} expected={expected} → audit_invalid"
        if signal_camp != expected else "camp OK"
    )
    camp_ok = signal_camp == expected
    if camp_ok:
        status_line = "PASS camp_OK"
        ann_color = "#1b5e20"
        bbox_face = "#e8f5e9"
        bbox_edge = "#2e7d32"
        arrow_color = "#2e7d32"
    else:
        status_line = "FAIL audit_invalid"
        ann_color = "#b71c1c"
        bbox_face = "#ffebee"
        bbox_edge = "#c62828"
        arrow_color = "#c62828"
    ax.annotate(
        f"{status_line}\n{verdict}",
        xy=(ex, fill_price),
        xytext=(ex + (pd.Timedelta(days=3).total_seconds() / 86400), fill_price * (1.03 if side == 1 else 0.97)),
        arrowprops={"arrowstyle": "->", "color": arrow_color, "lw": 1.3},
        color=ann_color, fontsize=9, fontweight="bold",
        bbox={"boxstyle": "round,pad=0.35", "facecolor": bbox_face, "edgecolor": bbox_edge},
    )

    sig_x = mdates.date2num(pd.to_datetime(signal_row["date"]))
    ax.axvspan(sig_x - 0.45, sig_x + 0.45, facecolor="#ffecb3", alpha=0.35, linewidth=0)
    ax.text(
        sig_x, trigger, f"信号棍\n{camp_name.get(signal_camp, signal_camp)}",
        ha="center", va="bottom", fontsize=8, color="#6d4c41",
    )

    title = (
        f"{args.symbol} D1 {args.order_tag} 审计沙盒\n"
        f"入场 {args.entry_date} camp={camp_name.get(entry_camp, entry_camp)} | 信号棍 {str(signal_row['date'])[:10]} camp={camp_name.get(signal_camp, signal_camp)}"
    )
    ax.set_title(title, fontsize=11)
    ax.set_ylabel("Price")
    ax.grid(True, linestyle=":", alpha=0.25)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m-%d"))
    ax.legend(loc="upper right", fontsize=8)
    fig.autofmt_xdate()
    fig.tight_layout()

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out)
    plt.close(fig)
    print(f"saved={out} signal_camp={signal_camp} entry_camp={entry_camp}")
    return out


def main() -> int:
    p = argparse.ArgumentParser(description="DS01 audit sandbox with OS camp + fill mark.")
    p.add_argument("--csv", required=True)
    p.add_argument("--market", choices=("futures", "crypto"), default="futures")
    p.add_argument("--symbol", required=True)
    p.add_argument("--side", required=True, choices=("long", "short"))
    p.add_argument("--entry-date", required=True)
    p.add_argument("--fill-price", type=float, required=True)
    p.add_argument("--start", default="2026-05-01")
    p.add_argument("--end", default="2026-06-15")
    p.add_argument("--order-tag", default="DS01")
    p.add_argument("--verdict", default="")
    p.add_argument("--out", required=True)
    p.add_argument("--gap", type=int, default=3)
    plot_audit(p.parse_args())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
