from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.patches import Rectangle

from backtest_ds01 import DS01BacktestConfig, run_ds01_backtest
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
                alpha=0.72,
            )
        )


def draw_camp_background(ax, df: pd.DataFrame) -> None:
    xs = mdates.date2num(pd.to_datetime(df["date"]).dt.to_pydatetime())
    for idx, (_, row) in enumerate(df.iterrows()):
        camp = int(row.get("camp", 0))
        if camp == 0:
            continue
        color = "#ffdddd" if camp == 1 else "#dde8ff"
        ax.axvspan(xs[idx] - 0.5, xs[idx] + 0.5, facecolor=color, alpha=0.30, linewidth=0)


def draw_hardened_line(ax, df: pd.DataFrame, hardened_nodes: list, start: int, end: int) -> None:
    nodes = sorted(
        [node for node in hardened_nodes if start <= node.point_idx <= end],
        key=lambda node: (node.point_idx, node.confirm_idx),
    )
    if len(nodes) < 2:
        return
    xs = [mdates.date2num(pd.to_datetime(df.iloc[node.point_idx]["date"])) for node in nodes]
    ys = [node.price for node in nodes]
    ax.plot(xs, ys, color="#6f35b5", linewidth=2.0, marker="o", markersize=4, label="hardened_fengji_line")


def draw_stop_path(ax, df: pd.DataFrame, trade: pd.Series, stop_mode: str) -> None:
    if stop_mode == "trigger":
        entry_x = mdates.date2num(pd.to_datetime(df.iloc[int(trade["entry_idx"])]["date"]))
        exit_x = mdates.date2num(pd.to_datetime(df.iloc[int(trade["exit_idx"])]["date"]))
        ax.hlines(
            float(trade["final_stop"]),
            entry_x,
            exit_x,
            color="#8e24aa",
            linewidth=1.4,
            label="trigger stop",
        )
        return

    side = 1 if trade["direction"] == "long" else -1
    rows = []
    current_stop = float(trade["initial_stop"])
    for idx in range(int(trade["entry_idx"]), int(trade["exit_idx"]) + 1):
        row = df.iloc[idx]
        rows.append((pd.to_datetime(row["date"]), current_stop))
        current_stop = float(row["low"]) if side == 1 else float(row["high"])
    if rows:
        ax.step(
            [mdates.date2num(date) for date, _ in rows],
            [value for _, value in rows],
            where="post",
            color="#8e24aa",
            linewidth=1.4,
            label="one-bar stop",
        )


def plot_trade(csv_path: Path, trade_no: int, out_path: Path, before: int, after: int, config: DS01BacktestConfig) -> Path:
    df = load_ohlcv_for_engine(csv_path, config.atr_window)
    result = run_ds01_backtest(df, config)
    trades = result["trades"]
    orders = result["orders"]
    if trades.empty:
        raise ValueError(f"No DS01 trades found in {csv_path}")
    trade_row = trades[trades["trade_no"] == trade_no]
    if trade_row.empty:
        raise ValueError(f"trade_no {trade_no} not found.")
    trade = trade_row.iloc[0]
    order_rows = orders[orders["trade_no"] == trade_no] if "trade_no" in orders.columns else pd.DataFrame()

    start = max(0, int(trade["entry_idx"]) - before)
    end = min(len(df) - 1, int(trade["exit_idx"]) + after)
    window = result["df"].iloc[start : end + 1].copy()

    set_chinese_font()
    fig, ax = plt.subplots(figsize=(16, 8), dpi=140)
    draw_camp_background(ax, window)
    draw_candles(ax, window)
    draw_hardened_line(ax, result["df"], result["engine"].hardened_nodes, start, end)

    side = 1 if trade["direction"] == "long" else -1
    entry_x = mdates.date2num(pd.to_datetime(result["df"].iloc[int(trade["entry_idx"])]["date"]))
    exit_x = mdates.date2num(pd.to_datetime(result["df"].iloc[int(trade["exit_idx"])]["date"]))
    ax.scatter(entry_x, float(trade["avg_entry_price"]), marker="^" if side == 1 else "v", s=95, color="#00a152", zorder=6, label="entry")
    ax.scatter(exit_x, float(trade["exit_price"]), marker="v" if side == 1 else "^", s=95, color="#f57c00", zorder=6, label="exit")

    if not order_rows.empty:
        for _, order in order_rows.iterrows():
            sig_idx = int(order["signal_idx"])
            trig_idx = int(order["entry_idx"])
            if start <= sig_idx <= end:
                sx = mdates.date2num(pd.to_datetime(result["df"].iloc[sig_idx]["date"]))
                sy = float(result["df"].iloc[sig_idx]["high"] if side == 1 else result["df"].iloc[sig_idx]["low"])
                ax.text(sx, sy, "信号棍", color="#6a00a8", fontsize=9, ha="center", va="bottom" if side == 1 else "top")
            if start <= trig_idx <= end:
                tx = mdates.date2num(pd.to_datetime(result["df"].iloc[trig_idx]["date"]))
                ax.text(tx, float(order["trigger_price"]), f"突破触发\nleft={int(order['left_count'])}", color="#00695c", fontsize=8, ha="center")
                ax.axhline(float(order["trigger_price"]), color="#00695c", linestyle=":", linewidth=0.9)

    draw_stop_path(ax, result["df"], trade, config.stop_mode)

    title = (
        f"{csv_path.stem} DS01 sandbox trade {trade_no} | {trade['direction']} | "
        f"PnL {float(trade['net_pnl']):.2f} | entries={int(trade['entries'])} | "
        f"camp={int(trade['camp_signal'])} | stop={config.stop_mode}"
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
    parser = argparse.ArgumentParser(description="Plot DS01 physical sandbox chart.")
    parser.add_argument("--csv", required=True)
    parser.add_argument("--trade-no", type=int, required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--before", type=int, default=30)
    parser.add_argument("--after", type=int, default=15)
    parser.add_argument("--initial-cash", type=float, default=100_000.0)
    parser.add_argument("--lots", type=int, default=1)
    parser.add_argument("--max-entries", type=int, default=3)
    parser.add_argument("--commission-rate", type=float, default=0.0001)
    parser.add_argument("--slippage-ticks", type=float, default=1.0)
    parser.add_argument("--left-lookback", type=int, default=30)
    parser.add_argument("--atr-window", type=int, default=14)
    parser.add_argument("--gap", type=int, default=3)
    parser.add_argument("--stop-mode", choices=["one_bar", "trigger"], default="one_bar")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    csv_path = Path(args.csv)
    config = DS01BacktestConfig(
        initial_cash=args.initial_cash,
        lots=args.lots,
        max_entries=args.max_entries,
        commission_rate=args.commission_rate,
        slippage_ticks=args.slippage_ticks,
        left_lookback=args.left_lookback,
        atr_window=args.atr_window,
        gap=args.gap,
        stop_mode=args.stop_mode,
        futures_mode=True,
        spec=get_futures_spec(csv_path),
    )
    saved = plot_trade(csv_path, args.trade_no, Path(args.out), args.before, args.after, config)
    print(f"Saved DS01 sandbox chart to {saved}")


if __name__ == "__main__":
    main()
