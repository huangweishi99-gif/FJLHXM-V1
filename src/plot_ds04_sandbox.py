from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.patches import Rectangle

from backtest_ds04 import DS04BacktestConfig, run_ds04_backtest
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
    nodes = sorted(
        [node for node in hardened_nodes if start <= node.point_idx <= end],
        key=lambda node: (node.point_idx, node.confirm_idx),
    )
    if len(nodes) < 2:
        return
    xs = [mdates.date2num(pd.to_datetime(df.iloc[node.point_idx]["date"])) for node in nodes]
    ys = [node.price for node in nodes]
    ax.plot(xs, ys, color="#6f35b5", linewidth=2.0, marker="o", markersize=4, label="hardened_fengji_line")


def draw_stop_path(ax, df: pd.DataFrame, stop_history: pd.DataFrame, trade_no: int) -> None:
    if stop_history.empty:
        return
    rows = stop_history[stop_history["trade_no"] == trade_no].copy()
    if rows.empty:
        return
    xs = [mdates.date2num(pd.to_datetime(df.iloc[int(idx)]["date"])) for idx in rows["idx"]]
    ax.step(xs, rows["stop"].astype(float), where="post", color="#8e24aa", linewidth=1.5, label="DS04 defense stop")


def draw_trade_marks(ax, df: pd.DataFrame, trade: pd.Series, start: int, end: int) -> None:
    side = 1 if trade["direction"] == "long" else -1
    for idx, label in [(int(trade["k1"]), "K1"), (int(trade["k2"]), "K2"), (int(trade["k3"]), "K3")]:
        if start <= idx <= end:
            x = mdates.date2num(pd.to_datetime(df.iloc[idx]["date"]))
            y = float(df.iloc[idx]["high"]) if side == 1 else float(df.iloc[idx]["low"])
            ax.text(x, y, label, color="#6a00a8", fontsize=10, fontweight="bold", ha="center", va="bottom" if side == 1 else "top")

    if start <= int(trade["entry_idx"]) <= end:
        entry_x = mdates.date2num(pd.to_datetime(df.iloc[int(trade["entry_idx"])]["date"]))
        ax.scatter(entry_x, float(trade["entry_price"]), marker="^" if side == 1 else "v", s=110, color="#00a152", zorder=7, label="K4 entry")
        ax.text(entry_x, float(trade["entry_price"]), "K4开盘", color="#00695c", fontsize=8, ha="center", va="bottom" if side == 1 else "top")

    if start <= int(trade["exit_idx"]) <= end:
        exit_x = mdates.date2num(pd.to_datetime(df.iloc[int(trade["exit_idx"])]["date"]))
        ax.scatter(exit_x, float(trade["exit_price"]), marker="v" if side == 1 else "^", s=110, color="#f57c00", zorder=7, label="exit")

    ax.axhline(float(trade["reclaim_price"]), color="#7b1fa2", linestyle="--", linewidth=1.0, label="K1 reclaim boundary")
    ax.axhline(float(trade["initial_stop"]), color="#8e24aa", linestyle=":", linewidth=1.0, label="initial 3K defense")


def plot_trade(csv_path: Path, trade_no: int, out_path: Path, before: int, after: int, config: DS04BacktestConfig) -> Path:
    df = load_ohlcv_for_engine(csv_path, config.atr_window)
    result = run_ds04_backtest(df, config)
    trades = result["trades"]
    if trades.empty:
        raise ValueError(f"No DS04 trades found in {csv_path}")
    trade_row = trades[trades["trade_no"] == trade_no]
    if trade_row.empty:
        raise ValueError(f"trade_no {trade_no} not found.")
    trade = trade_row.iloc[0]

    start = max(0, int(trade["k1"]) - before)
    end = min(len(df) - 1, int(trade["exit_idx"]) + after)
    window = result["df"].iloc[start : end + 1].copy()
    hardened = result["engine"].hardened_by_bar[end] if end < len(result["engine"].hardened_by_bar) else result["engine"].hardened_nodes

    set_chinese_font()
    fig, ax = plt.subplots(figsize=(16, 8), dpi=140)
    draw_camp_background(ax, window)
    draw_candles(ax, window)
    draw_hardened_line(ax, result["df"], hardened, start, end)
    draw_trade_marks(ax, result["df"], trade, start, end)
    draw_stop_path(ax, result["df"], result["stop_history"], trade_no)

    title = (
        f"{csv_path.stem} DS04 sandbox trade {trade_no} | {trade['direction']} | "
        f"PnL {float(trade['net_pnl']):.2f} | K3 camp={int(trade['k3_camp'])} | {trade['pattern']}"
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
    parser = argparse.ArgumentParser(description="Plot DS04 physical sandbox chart.")
    parser.add_argument("--csv", required=True)
    parser.add_argument("--trade-no", type=int, required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--before", type=int, default=45)
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
    config = DS04BacktestConfig(
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
    print(f"Saved DS04 sandbox chart to {saved}")


if __name__ == "__main__":
    main()
