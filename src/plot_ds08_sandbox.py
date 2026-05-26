from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.patches import Rectangle

from backtest_ds08 import DS08BacktestConfig, load_frame, run_ds08_backtest
from quant.futures_specs import get_futures_spec


def set_chinese_font() -> None:
    plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "Noto Sans CJK SC", "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False


def draw_candles(ax, df: pd.DataFrame, width: float = 0.028) -> None:
    xs = mdates.date2num(pd.to_datetime(df["date"]).dt.to_pydatetime())
    for x, (_, row) in zip(xs, df.iterrows()):
        open_ = float(row["open"])
        high = float(row["high"])
        low = float(row["low"])
        close = float(row["close"])
        color = "#d62728" if close >= open_ else "#1f77b4"
        ax.vlines(x, low, high, color=color, linewidth=0.8, alpha=0.9)
        ax.add_patch(
            Rectangle(
                (x - width / 2, min(open_, close)),
                width,
                max(abs(close - open_), 1e-9),
                facecolor=color,
                edgecolor=color,
                linewidth=0.6,
                alpha=0.76,
            )
        )


def draw_camp_background(ax, df: pd.DataFrame) -> None:
    xs = mdates.date2num(pd.to_datetime(df["date"]).dt.to_pydatetime())
    for idx, (_, row) in enumerate(df.iterrows()):
        camp = int(row.get("camp", 0))
        if camp == 0:
            continue
        color = "#ffdddd" if camp == 1 else "#dde8ff"
        ax.axvspan(xs[idx] - 0.02, xs[idx] + 0.02, facecolor=color, alpha=0.20, linewidth=0)


def draw_hardened_line(ax, df: pd.DataFrame, hardened_nodes: list, start: int, end: int) -> None:
    nodes = sorted([node for node in hardened_nodes if start <= node.point_idx <= end], key=lambda node: (node.point_idx, node.confirm_idx))
    if len(nodes) < 2:
        return
    xs = [mdates.date2num(pd.to_datetime(df.iloc[node.point_idx]["date"])) for node in nodes]
    ys = [node.price for node in nodes]
    ax.plot(xs, ys, color="#6f35b5", linewidth=1.9, marker="o", markersize=3.5, label="hardened_fengji_line")


def draw_stop_path(ax, df: pd.DataFrame, stop_history: pd.DataFrame, trade_no: int) -> None:
    if stop_history.empty:
        return
    rows = stop_history[stop_history["trade_no"] == trade_no].copy()
    if rows.empty:
        return
    xs = [mdates.date2num(pd.to_datetime(df.iloc[int(idx)]["date"])) for idx in rows["idx"]]
    ax.step(xs, rows["stop"].astype(float), where="post", color="#8e24aa", linewidth=1.5, label="step guard-extreme stop")


def mark(ax, df: pd.DataFrame, idx: int, price: float, label: str, color: str, va: str, marker: str = "o", size: int = 82) -> None:
    x = mdates.date2num(pd.to_datetime(df.iloc[idx]["date"]))
    ax.scatter(x, price, marker=marker, s=size, color=color, zorder=8)
    ax.text(x, price, label, color=color, fontsize=8, ha="center", va=va)


def draw_trade_marks(ax, df: pd.DataFrame, trade: pd.Series, start: int, end: int) -> None:
    side = 1 if trade["direction"] == "long" else -1
    labels = ["V1", "P1", "V2", "P2", "V3"] if side == 1 else ["P1", "V1", "P2", "V2", "P3"]
    for number, label in enumerate(labels, start=1):
        idx = int(trade[f"n{number}_idx"])
        price = float(trade[f"n{number}_price"])
        node_type = str(trade[f"n{number}_type"])
        if start <= idx <= end:
            va = "bottom" if node_type == "P" else "top"
            color = "#6a00a8" if number in {2, 4} else "#455a64"
            mark(ax, df, idx, price, label, color, va)

    n5_confirm = int(trade["n5_confirm_idx"])
    if start <= n5_confirm <= end:
        confirm_y = float(df.iloc[n5_confirm]["high"] if side == 1 else df.iloc[n5_confirm]["low"])
        mark(ax, df, n5_confirm, confirm_y, "T+3确认", "#00897b", "bottom" if side == 1 else "top", marker="s", size=90)

    entry_idx = int(trade["entry_idx"])
    exit_idx = int(trade["exit_idx"])
    if start <= entry_idx <= end:
        mark(ax, df, entry_idx, float(trade["entry_price"]), "真启动棍", "#00a152", "bottom" if side == 1 else "top", marker="^" if side == 1 else "v", size=120)
    if start <= exit_idx <= end:
        mark(ax, df, exit_idx, float(trade["exit_price"]), "EXIT", "#f57c00", "top" if side == 1 else "bottom", marker="v" if side == 1 else "^", size=120)

    ax.axhline(float(trade["attack_price"]), color="#7b1fa2", linestyle="--", linewidth=1.0, label="P2/V2 attack ref")
    ax.axhline(float(trade["defense_price"]), color="#455a64", linestyle=":", linewidth=1.0, label="V3/P3 initial defense")


def plot_trade(csv_path: Path, trade_no: int, out_path: Path, before: int, after: int, config: DS08BacktestConfig, symbol: str) -> Path:
    df = load_frame(csv_path, config.atr_window)
    result = run_ds08_backtest(df, config, symbol=symbol)
    trades = result["trades"]
    if trades.empty:
        raise ValueError(f"No DS08 trades found in {csv_path}")
    trade_row = trades[trades["trade_no"] == trade_no]
    if trade_row.empty:
        available = ", ".join(str(x) for x in trades["trade_no"].tolist()[:20])
        raise ValueError(f"trade_no {trade_no} not found. Available starts with: {available}")
    trade = trade_row.iloc[0]

    start = max(0, int(trade["n1_idx"]) - before)
    end = min(len(result["df"]) - 1, int(trade["exit_idx"]) + after)
    window = result["df"].iloc[start : end + 1].copy()

    set_chinese_font()
    fig, ax = plt.subplots(figsize=(17, 8), dpi=140)
    draw_camp_background(ax, window)
    draw_candles(ax, window)
    draw_hardened_line(ax, result["df"], result["engine"].hardened_nodes, start, end)
    draw_trade_marks(ax, result["df"], trade, start, end)
    draw_stop_path(ax, result["df"], result["stop_history"], trade_no)

    title = (
        f"{symbol} DS08 sandbox trade {trade_no} | {trade['direction']} | "
        f"PnL {float(trade['net_pnl']):.2f} | attack={float(trade['attack_price']):.2f} "
        f"defense={float(trade['defense_price']):.2f}"
    )
    ax.set_title(title, fontsize=12)
    ax.set_ylabel("Price")
    ax.grid(True, linestyle=":", alpha=0.25)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m-%d %H:%M"))
    ax.legend(loc="best", fontsize=8)
    fig.autofmt_xdate()
    fig.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path)
    plt.close(fig)
    return out_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Plot DS08 power-seizure sandbox chart.")
    parser.add_argument("--csv", required=True)
    parser.add_argument("--trade-no", type=int, required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--symbol", default="")
    parser.add_argument("--before", type=int, default=80)
    parser.add_argument("--after", type=int, default=40)
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
    config = DS08BacktestConfig(
        initial_cash=args.initial_cash,
        lots=args.lots,
        commission_rate=args.commission_rate,
        slippage_ticks=args.slippage_ticks,
        atr_window=args.atr_window,
        gap=args.gap,
        futures_mode=True,
        spec=get_futures_spec(csv_path),
    )
    symbol = args.symbol or csv_path.stem.replace("_60m", "")
    saved = plot_trade(csv_path, args.trade_no, Path(args.out), args.before, args.after, config, symbol)
    print(f"Saved DS08 sandbox chart to {saved}")


if __name__ == "__main__":
    main()
