from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.patches import Rectangle

from backtest_ds06 import DS06BacktestConfig, run_ds06_backtest
from quant.data import load_ohlcv_for_engine
from quant.futures_specs import get_futures_spec


def set_chinese_font() -> None:
    plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "Noto Sans CJK SC", "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False


def draw_candles(ax, df: pd.DataFrame, width: float = 0.62) -> None:
    xs = mdates.date2num(pd.to_datetime(df["date"]).dt.to_pydatetime())
    for x, (_, row) in zip(xs, df.iterrows()):
        open_ = float(row["open"])
        high = float(row["high"])
        low = float(row["low"])
        close = float(row["close"])
        color = "#d62728" if close >= open_ else "#1f77b4"
        ax.vlines(x, low, high, color=color, linewidth=0.9, alpha=0.9)
        ax.add_patch(
            Rectangle(
                (x - width / 2, min(open_, close)),
                width,
                max(abs(close - open_), 1e-9),
                facecolor=color,
                edgecolor=color,
                linewidth=0.8,
                alpha=0.74,
            )
        )


def draw_camp_background(ax, df: pd.DataFrame) -> None:
    xs = mdates.date2num(pd.to_datetime(df["date"]).dt.to_pydatetime())
    for idx, (_, row) in enumerate(df.iterrows()):
        camp = int(row.get("camp", 0))
        if camp == 0:
            continue
        color = "#ffdddd" if camp == 1 else "#dde8ff"
        ax.axvspan(xs[idx] - 0.5, xs[idx] + 0.5, facecolor=color, alpha=0.28, linewidth=0)


def draw_hardened_line(ax, df: pd.DataFrame, hardened_nodes: list, start: int, end: int) -> None:
    nodes = sorted([node for node in hardened_nodes if start <= node.point_idx <= end], key=lambda node: (node.point_idx, node.confirm_idx))
    if len(nodes) < 2:
        return
    xs = [mdates.date2num(pd.to_datetime(df.iloc[node.point_idx]["date"])) for node in nodes]
    ys = [node.price for node in nodes]
    ax.plot(xs, ys, color="#6f35b5", linewidth=2.1, marker="o", markersize=4, label="hardened_fengji_line")


def draw_stop_path(ax, df: pd.DataFrame, stop_history: pd.DataFrame, trade_no: int) -> None:
    if stop_history.empty:
        return
    rows = stop_history[stop_history["trade_no"] == trade_no].copy()
    if rows.empty:
        return
    xs = [mdates.date2num(pd.to_datetime(df.iloc[int(idx)]["date"])) for idx in rows["idx"]]
    ax.step(xs, rows["stop"].astype(float), where="post", color="#8e24aa", linewidth=1.5, label="DS03 shou4 stop")


def mark_point(ax, df: pd.DataFrame, idx: int, price: float, label: str, color: str, va: str) -> None:
    x = mdates.date2num(pd.to_datetime(df.iloc[idx]["date"]))
    ax.scatter(x, price, marker="o", s=82, color=color, zorder=7)
    ax.text(x, price, label, color=color, fontsize=8, ha="center", va=va)


def mark_bar(ax, df: pd.DataFrame, idx: int, price: float, label: str, marker: str, color: str, va: str) -> None:
    x = mdates.date2num(pd.to_datetime(df.iloc[idx]["date"]))
    ax.scatter(x, price, marker=marker, s=115, color=color, zorder=8, label=label)
    ax.text(x, price, label, color=color, fontsize=8, ha="center", va=va)


def draw_trade_marks(ax, df: pd.DataFrame, trade: pd.Series, start: int, end: int) -> None:
    side = 1 if trade["direction"] == "long" else -1
    turn_idx = int(trade["turn_idx"])
    d_idx = int(trade["d_idx"])
    d_confirm_idx = int(trade["d_confirm_idx"])
    e_idx = int(trade["e_idx"])
    e_confirm_idx = int(trade["e_confirm_idx"])
    entry_idx = int(trade["entry_idx"])
    exit_idx = int(trade["exit_idx"])

    if start <= turn_idx <= end:
        turn_price = float(df.iloc[turn_idx]["high"] if side == 1 else df.iloc[turn_idx]["low"])
        mark_bar(ax, df, turn_idx, turn_price, "TURN", "X", "#263238", "bottom" if side == 1 else "top")

    if start <= d_idx <= end:
        mark_point(ax, df, d_idx, float(trade["d_price"]), "D/d", "#6a00a8", "bottom" if side == 1 else "top")
    if start <= d_confirm_idx <= end:
        y = float(df.iloc[d_confirm_idx]["high"] if side == 1 else df.iloc[d_confirm_idx]["low"])
        mark_bar(ax, df, d_confirm_idx, y, "D_CONFIRM", "s", "#6a00a8", "bottom" if side == 1 else "top")

    if start <= e_idx <= end:
        mark_point(ax, df, e_idx, float(trade["e_price"]), "E/e", "#00897b", "top" if side == 1 else "bottom")
    if start <= e_confirm_idx <= end:
        y = float(df.iloc[e_confirm_idx]["low"] if side == 1 else df.iloc[e_confirm_idx]["high"])
        mark_bar(ax, df, e_confirm_idx, y, "E_CONFIRM", "s", "#00897b", "top" if side == 1 else "bottom")

    if start <= entry_idx <= end:
        mark_bar(ax, df, entry_idx, float(trade["entry_price"]), "F/f_ENTRY", "^" if side == 1 else "v", "#00a152", "bottom" if side == 1 else "top")
    if start <= exit_idx <= end:
        mark_bar(ax, df, exit_idx, float(trade["exit_price"]), "EXIT", "v" if side == 1 else "^", "#f57c00", "top" if side == 1 else "bottom")

    ax.axhline(float(trade["old_extreme_price"]), color="#455a64", linestyle=":", linewidth=1.0, label="old defense extreme")
    ax.axhline(float(trade["entry_ref"]), color="#7b1fa2", linestyle="--", linewidth=1.0, label="D/d external-break ref")
    ax.axhline(float(trade["initial_stop"]), color="#8e24aa", linestyle=":", linewidth=1.0, label="K1/K2 initial stop")


def plot_trade(csv_path: Path, trade_no: int, out_path: Path, before: int, after: int, config: DS06BacktestConfig) -> Path:
    df = load_ohlcv_for_engine(csv_path, config.atr_window)
    result = run_ds06_backtest(df, config)
    trades = result["trades"]
    if trades.empty:
        raise ValueError(f"No DS06 trades found in {csv_path}")
    trade_row = trades[trades["trade_no"] == trade_no]
    if trade_row.empty:
        available = ", ".join(str(x) for x in trades["trade_no"].tolist()[:20])
        raise ValueError(f"trade_no {trade_no} not found. Available starts with: {available}")
    trade = trade_row.iloc[0]

    start = max(0, int(trade["turn_idx"]) - before)
    end = min(len(df) - 1, int(trade["exit_idx"]) + after)
    window = result["df"].iloc[start : end + 1].copy()

    set_chinese_font()
    fig, ax = plt.subplots(figsize=(16, 8), dpi=140)
    draw_camp_background(ax, window)
    draw_candles(ax, window)
    draw_hardened_line(ax, result["df"], result["engine"].hardened_nodes, start, end)
    draw_trade_marks(ax, result["df"], trade, start, end)
    draw_stop_path(ax, result["df"], result["stop_history"], trade_no)

    title = (
        f"{csv_path.stem} DS06 sandbox trade {trade_no} | {trade['direction']} | "
        f"PnL {float(trade['net_pnl']):.2f} | {trade['turn_type']} | "
        f"D/E={float(trade['d_price']):.2f}/{float(trade['e_price']):.2f}"
    )
    ax.set_title(title, fontsize=12)
    ax.set_ylabel("Price")
    ax.grid(True, linestyle=":", alpha=0.25)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m-%d"))
    ax.legend(loc="best", fontsize=8)
    fig.autofmt_xdate()
    fig.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path)
    plt.close(fig)
    return out_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Plot DS06 physical sandbox chart.")
    parser.add_argument("--csv", required=True)
    parser.add_argument("--trade-no", type=int, required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--before", type=int, default=50)
    parser.add_argument("--after", type=int, default=20)
    parser.add_argument("--initial-cash", type=float, default=100_000.0)
    parser.add_argument("--lots", type=int, default=1)
    parser.add_argument("--commission-rate", type=float, default=0.0001)
    parser.add_argument("--slippage-ticks", type=float, default=1.0)
    parser.add_argument("--atr-window", type=int, default=14)
    parser.add_argument("--gap", type=int, default=3)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    csv_path = Path(args.csv)
    config = DS06BacktestConfig(
        initial_cash=args.initial_cash,
        lots=args.lots,
        commission_rate=args.commission_rate,
        slippage_ticks=args.slippage_ticks,
        atr_window=args.atr_window,
        gap=args.gap,
        futures_mode=True,
        spec=get_futures_spec(csv_path),
    )
    saved = plot_trade(csv_path, args.trade_no, Path(args.out), args.before, args.after, config)
    print(f"Saved DS06 sandbox chart to {saved}")


if __name__ == "__main__":
    main()
