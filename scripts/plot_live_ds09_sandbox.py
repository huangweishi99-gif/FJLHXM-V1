#!/usr/bin/env python3
"""Plot a live/open DS09 D1/M15 sandbox chart from runtime fill metadata."""
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

from backtest_ds09 import DS09BacktestConfig, load_frame, load_m15_frame, run_ds09_backtest
from quant.futures_specs import get_futures_spec


def set_font() -> None:
    plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "Noto Sans CJK SC", "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False


def parse_first_int(text: str, name: str) -> int | None:
    match = re.search(rf"{name}(?:_idx)?=([0-9]+)", text, flags=re.IGNORECASE)
    if match:
        return int(match.group(1))
    return None


def parse_ds09_metadata(setup_key: str, reason: str) -> dict[str, Any]:
    text = f"{setup_key} {reason}"
    parts = setup_key.split("|")
    out: dict[str, Any] = {"session": ""}
    if len(parts) >= 4:
        out["session"] = parts[3]
    out["lock_idx"] = parse_first_int(text, "lock")
    out["attack_idx"] = parse_first_int(text, "attack")
    out["defense_idx"] = parse_first_int(text, "defense") or parse_first_int(text, "def")
    return out


def row_contains_price(row: pd.Series, price: float) -> bool:
    return float(row["low"]) <= price <= float(row["high"])


def nearest_price_idx(df: pd.DataFrame, *, price: float, entry_idx: int, lookback: int) -> int | None:
    if price == 0:
        return None
    start = max(0, entry_idx - lookback)
    end = min(len(df) - 1, entry_idx)
    containing: list[int] = []
    scored: list[tuple[float, int]] = []
    for idx in range(start, end + 1):
        row = df.iloc[idx]
        if row_contains_price(row, price):
            containing.append(idx)
        nearest_ohlc = min(
            abs(float(row["open"]) - price),
            abs(float(row["high"]) - price),
            abs(float(row["low"]) - price),
            abs(float(row["close"]) - price),
        )
        recency_penalty = (entry_idx - idx) * 1e-6
        scored.append((nearest_ohlc / max(abs(price), 1.0) + recency_penalty, idx))
    if containing:
        return containing[-1]
    if not scored:
        return None
    scored.sort(key=lambda item: item[0])
    return int(scored[0][1])


def needs_relocation(idx: int | None, *, entry_idx: int, window: int, length: int) -> bool:
    if idx is None:
        return True
    if idx < 0 or idx >= length:
        return True
    return abs(entry_idx - idx) > window


def normalize_indices(
    df: pd.DataFrame,
    metadata: dict[str, Any],
    *,
    entry_idx: int,
    trigger_price: float,
    stop_price: float,
    boundary: float,
    before: int,
) -> dict[str, Any]:
    lookback = max(before * 2, 320)
    relocation_window = max(before + 80, 260)
    out = dict(metadata)
    relocations: dict[str, dict[str, Any]] = {}
    specs = [
        ("lock_idx", boundary),
        ("attack_idx", trigger_price),
        ("defense_idx", stop_price),
    ]
    for key, price in specs:
        original = out.get(key)
        if needs_relocation(original, entry_idx=entry_idx, window=relocation_window, length=len(df)):
            relocated = nearest_price_idx(df, price=float(price), entry_idx=entry_idx, lookback=lookback)
            if relocated is not None:
                out[key] = relocated
                relocations[key] = {"from": original, "to": relocated, "price": float(price)}
    out["relocations"] = relocations
    return out


def draw_candles(ax: Any, df: pd.DataFrame, width: float) -> None:
    xs = mdates.date2num(pd.to_datetime(df["date"]).dt.to_pydatetime())
    for x, (_, row) in zip(xs, df.iterrows()):
        open_ = float(row["open"])
        high = float(row["high"])
        low = float(row["low"])
        close = float(row["close"])
        color = "#d62728" if close >= open_ else "#1f77b4"
        ax.vlines(x, low, high, color=color, linewidth=0.8, alpha=0.9)
        ax.add_patch(Rectangle((x - width / 2, min(open_, close)), width, max(abs(close - open_), 1e-9), facecolor=color, edgecolor=color, linewidth=0.6, alpha=0.76))


def draw_camp_background(ax: Any, df: pd.DataFrame, span: float) -> None:
    xs = mdates.date2num(pd.to_datetime(df["date"]).dt.to_pydatetime())
    for idx, (_, row) in enumerate(df.iterrows()):
        camp = int(row.get("camp", 0) or 0)
        if camp:
            ax.axvspan(xs[idx] - span, xs[idx] + span, facecolor="#ffdddd" if camp == 1 else "#dde8ff", alpha=0.20, linewidth=0)


def draw_hardened_line(ax: Any, df: pd.DataFrame, nodes: list[Any], start: int, end: int) -> None:
    visible = sorted([node for node in nodes if start <= int(node.point_idx) <= end], key=lambda node: (node.point_idx, node.confirm_idx))
    if len(visible) < 2:
        return
    xs = [mdates.date2num(pd.to_datetime(df.iloc[int(node.point_idx)]["date"])) for node in visible]
    ys = [float(node.price) for node in visible]
    ax.plot(xs, ys, color="#6f35b5", linewidth=1.7, marker="o", markersize=2.8, label="M15 hardened_fengji_line")


def mark(ax: Any, df: pd.DataFrame, idx: int | None, price: float | None, label: str, color: str, marker: str, va: str) -> None:
    if idx is None or idx < 0 or idx >= len(df) or price is None:
        return
    x = mdates.date2num(pd.to_datetime(df.iloc[idx]["date"]))
    ax.scatter(x, price, marker=marker, s=105, color=color, zorder=8)
    ax.text(x, price, label, color=color, fontsize=8, ha="center", va=va)


def plot(args: argparse.Namespace) -> Path:
    d1_csv = Path(args.d1_csv)
    m15_csv = Path(args.m15_csv)
    spec = get_futures_spec(d1_csv) or get_futures_spec(m15_csv)
    config = DS09BacktestConfig(futures_mode=True, spec=spec)
    result = run_ds09_backtest(load_frame(d1_csv, config.atr_window), load_m15_frame(m15_csv, config.atr_window), config, symbol=args.symbol)
    d1_df = result["d1_df"]
    m15_df = result["m5_df"]
    metadata = parse_ds09_metadata(args.setup_key, args.reason)
    side = 1 if args.side == "long" else -1
    entry_time = pd.to_datetime(args.entry_time) if args.entry_time else None
    if entry_time is not None:
        hits = m15_df.index[pd.to_datetime(m15_df["date"]) <= entry_time]
        entry_idx = int(hits[-1]) if len(hits) else len(m15_df) - 1
    else:
        entry_idx = int(metadata.get("attack_idx") or 0)
    lock_idx = metadata.get("lock_idx")
    attack_idx = metadata.get("attack_idx")
    defense_idx = metadata.get("defense_idx")
    if not args.no_normalize_indices:
        metadata = normalize_indices(
            m15_df,
            metadata,
            entry_idx=entry_idx,
            trigger_price=float(args.trigger_price),
            stop_price=float(args.stop_price),
            boundary=float(args.boundary or 0.0),
            before=int(args.before),
        )
        lock_idx = metadata.get("lock_idx")
        attack_idx = metadata.get("attack_idx")
        defense_idx = metadata.get("defense_idx")

    start_seed = min([idx for idx in [lock_idx, attack_idx, defense_idx, entry_idx] if idx is not None], default=entry_idx)
    start = max(0, int(start_seed) - int(args.before))
    end = min(len(m15_df) - 1, entry_idx + int(args.after))
    win = m15_df.iloc[start : end + 1].copy()
    session = pd.to_datetime(metadata.get("session") or m15_df.iloc[entry_idx].get("session_date")).normalize()
    d1_plot = d1_df.copy()
    d1_plot["d"] = pd.to_datetime(d1_plot["date"]).dt.normalize()
    d1_win = d1_plot[(d1_plot["d"] >= session - pd.Timedelta(days=5)) & (d1_plot["d"] <= session + pd.Timedelta(days=2))].copy()

    set_font()
    fig, (ax_d1, ax_m15) = plt.subplots(2, 1, figsize=(17, 10), dpi=150, gridspec_kw={"height_ratios": [1.0, 2.2]})
    if not d1_win.empty:
        d1_candles = d1_win[["d", "open", "high", "low", "close"]].rename(columns={"d": "date"})
        draw_candles(ax_d1, d1_candles, width=0.55)
    ax_d1.axvline(session, color="#00a152", linestyle="--", linewidth=1.0, label="M15 session")
    ax_d1.set_title(f"D1 boundary context | session={session.date()}")
    ax_d1.grid(True, linestyle=":", alpha=0.25)
    ax_d1.legend(loc="best", fontsize=8)

    draw_camp_background(ax_m15, win, span=0.004)
    draw_candles(ax_m15, win, width=0.0032)
    draw_hardened_line(ax_m15, m15_df, result["m5_engine"].hardened_nodes, start, end)
    mark(ax_m15, m15_df, lock_idx, float(args.boundary) if args.boundary else None, "lock", "#263238", "X", "bottom" if side == 1 else "top")
    mark(ax_m15, m15_df, attack_idx, float(args.trigger_price), "attack", "#6a00a8", "o", "bottom" if side == 1 else "top")
    mark(ax_m15, m15_df, defense_idx, float(args.stop_price), "defense", "#455a64", "o", "top" if side == 1 else "bottom")
    mark(ax_m15, m15_df, entry_idx, float(args.fill_price), "fill/open", "#00a152", "^" if side == 1 else "v", "bottom" if side == 1 else "top")
    ax_m15.axhline(float(args.trigger_price), color="#6a00a8", linestyle="--", linewidth=1.0, label=f"attack {float(args.trigger_price):.8g}")
    ax_m15.axhline(float(args.stop_price), color="#455a64", linestyle=":", linewidth=1.0, label=f"initial stop {float(args.stop_price):.8g}")
    if args.boundary:
        ax_m15.axhline(float(args.boundary), color="#7b1fa2", linestyle="-.", linewidth=1.0, label=f"D1 boundary {float(args.boundary):.8g}")
    ax_m15.set_title(f"{args.symbol} DS09 live sandbox | {args.side} | {args.entry_time} | {args.pattern}")
    ax_m15.grid(True, linestyle=":", alpha=0.25)
    ax_m15.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m-%d %H:%M"))
    ax_m15.legend(loc="best", fontsize=8)
    fig.autofmt_xdate()
    fig.tight_layout()
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out)
    plt.close(fig)
    print(f"saved={out} metadata={metadata} entry_idx={entry_idx}")
    return out


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Plot live/open DS09 sandbox chart.")
    parser.add_argument("--d1-csv", required=True)
    parser.add_argument("--m15-csv", required=True)
    parser.add_argument("--symbol", required=True)
    parser.add_argument("--side", choices=("long", "short"), required=True)
    parser.add_argument("--setup-key", required=True)
    parser.add_argument("--reason", default="")
    parser.add_argument("--entry-time", default="")
    parser.add_argument("--fill-price", type=float, required=True)
    parser.add_argument("--trigger-price", type=float, required=True)
    parser.add_argument("--stop-price", type=float, required=True)
    parser.add_argument("--boundary", type=float, default=0.0)
    parser.add_argument("--pattern", default="")
    parser.add_argument("--out", required=True)
    parser.add_argument("--before", type=int, default=160)
    parser.add_argument("--after", type=int, default=100)
    parser.add_argument("--no-normalize-indices", action="store_true", help="use raw lock/attack/defense indexes from the event")
    return parser.parse_args()


if __name__ == "__main__":
    plot(parse_args())
