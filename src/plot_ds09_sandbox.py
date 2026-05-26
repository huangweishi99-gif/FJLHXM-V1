from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.patches import Rectangle

from backtest_ds09 import DS09BacktestConfig, load_frame, load_m15_frame, run_ds09_backtest
from quant.futures_specs import get_futures_spec


def set_chinese_font() -> None:
    plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "Noto Sans CJK SC", "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False


def draw_candles(ax, df: pd.DataFrame, width: float) -> None:
    xs = mdates.date2num(pd.to_datetime(df["date"]).dt.to_pydatetime())
    for x, (_, row) in zip(xs, df.iterrows()):
        open_ = float(row["open"])
        high = float(row["high"])
        low = float(row["low"])
        close = float(row["close"])
        color = "#d62728" if close >= open_ else "#1f77b4"
        ax.vlines(x, low, high, color=color, linewidth=0.8, alpha=0.9)
        ax.add_patch(Rectangle((x - width / 2, min(open_, close)), width, max(abs(close - open_), 1e-9), facecolor=color, edgecolor=color, linewidth=0.6, alpha=0.76))


def draw_camp_background(ax, df: pd.DataFrame) -> None:
    xs = mdates.date2num(pd.to_datetime(df["date"]).dt.to_pydatetime())
    for idx, (_, row) in enumerate(df.iterrows()):
        camp = int(row.get("camp", 0))
        if camp == 0:
            continue
        color = "#ffdddd" if camp == 1 else "#dde8ff"
        ax.axvspan(xs[idx] - 0.004, xs[idx] + 0.004, facecolor=color, alpha=0.20, linewidth=0)


def draw_hardened_line(ax, df: pd.DataFrame, hardened_nodes: list, start: int, end: int) -> None:
    nodes = sorted([node for node in hardened_nodes if start <= node.point_idx <= end], key=lambda node: (node.point_idx, node.confirm_idx))
    if len(nodes) < 2:
        return
    xs = [mdates.date2num(pd.to_datetime(df.iloc[node.point_idx]["date"])) for node in nodes]
    ys = [node.price for node in nodes]
    ax.plot(xs, ys, color="#6f35b5", linewidth=1.7, marker="o", markersize=2.8, label="M15 hardened_fengji_line")


def draw_stop_path(ax, df: pd.DataFrame, stop_history: pd.DataFrame, trade_no: int) -> None:
    if stop_history.empty:
        return
    rows = stop_history[stop_history["trade_no"] == trade_no]
    if rows.empty:
        return
    xs = [mdates.date2num(pd.to_datetime(df.iloc[int(idx)]["date"])) for idx in rows["idx"]]
    ax.step(xs, rows["stop"].astype(float), where="post", color="#8e24aa", linewidth=1.5, label="M15 guard-extreme stop")


def mark(ax, df: pd.DataFrame, idx: int, price: float, label: str, color: str, marker: str, va: str) -> None:
    x = mdates.date2num(pd.to_datetime(df.iloc[idx]["date"]))
    ax.scatter(x, price, marker=marker, s=105, color=color, zorder=8)
    ax.text(x, price, label, color=color, fontsize=8, ha="center", va=va)


def plot_trade(d1_csv: Path, m15_csv: Path, trade_no: int, out_path: Path, before: int, after: int, config: DS09BacktestConfig, symbol: str) -> Path:
    d1_df = load_frame(d1_csv, config.atr_window)
    m15_df = load_m15_frame(m15_csv, config.atr_window)
    result = run_ds09_backtest(d1_df, m15_df, config, symbol=symbol)
    trades = result["trades"]
    if trades.empty:
        raise ValueError(f"No DS09 trades found in {m15_csv}")
    trade_row = trades[trades["trade_no"] == trade_no]
    if trade_row.empty:
        available = ", ".join(str(x) for x in trades["trade_no"].tolist()[:20])
        raise ValueError(f"trade_no {trade_no} not found. Available starts with: {available}")
    trade = trade_row.iloc[0]
    start = max(0, int(trade["lock_idx"]) - before)
    end = min(len(result["m5_df"]) - 1, int(trade["exit_idx"]) + after)
    window = result["m5_df"].iloc[start : end + 1].copy()

    session_date = pd.to_datetime(trade["session_date"]).normalize()
    d1 = result["d1_df"].copy()
    d1["d"] = pd.to_datetime(d1["date"]).dt.normalize()
    d1_window = d1[(d1["d"] >= session_date - pd.Timedelta(days=5)) & (d1["d"] <= session_date + pd.Timedelta(days=2))]

    set_chinese_font()
    fig, (ax_d1, ax_m5) = plt.subplots(2, 1, figsize=(17, 10), dpi=140, gridspec_kw={"height_ratios": [1.0, 2.2]})

    if not d1_window.empty:
        d1_plot = d1_window.copy()
        d1_plot["date"] = d1_plot["d"]
        draw_candles(ax_d1, d1_plot[["date", "open", "high", "low", "close"]], width=0.55)
    ax_d1.axhline(float(trade["d1_boundary"]), color="#7b1fa2", linestyle="-.", linewidth=1.2, label="D1 yesterday boundary")
    ax_d1.axvline(session_date, color="#00a152", linestyle="--", linewidth=1.0, label="M15 session")
    ax_d1.set_title(f"D1 strategic boundary | prev {'bearish' if trade['mode'] == 'LONG' else 'bullish'} candle -> {trade['mode']}")
    ax_d1.grid(True, linestyle=":", alpha=0.25)
    ax_d1.legend(loc="best", fontsize=8)

    draw_camp_background(ax_m5, window)
    draw_candles(ax_m5, window, width=0.0032)
    draw_hardened_line(ax_m5, result["m5_df"], result["m5_engine"].hardened_nodes, start, end)
    draw_stop_path(ax_m5, result["m5_df"], result["stop_history"], trade_no)

    side = 1 if trade["direction"] == "long" else -1
    lock_price = float(trade["d1_boundary"])
    mark(ax_m5, result["m5_df"], int(trade["lock_idx"]), lock_price, "首次刺穿锁定", "#263238", "X", "bottom" if side == 1 else "top")
    mark(ax_m5, result["m5_df"], int(trade["attack_idx"]), float(trade["attack_price"]), "第一进攻峰", "#6a00a8", "o", "bottom" if side == 1 else "top")
    mark(ax_m5, result["m5_df"], int(trade["defense_idx"]), float(trade["defense_price"]), "第一防守极", "#455a64", "o", "top" if side == 1 else "bottom")
    mark(ax_m5, result["m5_df"], int(trade["entry_idx"]), float(trade["entry_price"]), "二次攻击入场", "#00a152", "^" if side == 1 else "v", "bottom" if side == 1 else "top")
    mark(ax_m5, result["m5_df"], int(trade["exit_idx"]), float(trade["exit_price"]), "EXIT", "#f57c00", "v" if side == 1 else "^", "top" if side == 1 else "bottom")
    ax_m5.axhline(float(trade["d1_boundary"]), color="#7b1fa2", linestyle="-.", linewidth=1.0, label="D1 boundary")
    ax_m5.axhline(float(trade["attack_price"]), color="#6a00a8", linestyle="--", linewidth=1.0, label="M15 attack ref")
    ax_m5.axhline(float(trade["defense_price"]), color="#455a64", linestyle=":", linewidth=1.0, label="M15 initial defense")

    title = (
        f"{symbol} DS09 sandbox trade {trade_no} | {trade['direction']} | "
        f"PnL {float(trade['net_pnl']):.2f} | mode={trade['mode']} | "
        f"boundary={float(trade['d1_boundary']):.2f}"
    )
    ax_m5.set_title(title)
    ax_m5.grid(True, linestyle=":", alpha=0.25)
    ax_m5.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m-%d %H:%M"))
    ax_m5.legend(loc="best", fontsize=8)
    fig.autofmt_xdate()
    fig.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path)
    plt.close(fig)
    return out_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Plot DS09 D1/M15 sandbox chart.")
    parser.add_argument("--d1-csv", required=True)
    parser.add_argument("--m15-csv", required=False)
    parser.add_argument("--m5-csv", required=False, help="Deprecated alias for --m15-csv.")
    parser.add_argument("--trade-no", type=int, required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--symbol", default="")
    parser.add_argument("--before", type=int, default=160)
    parser.add_argument("--after", type=int, default=100)
    parser.add_argument("--initial-cash", type=float, default=100_000.0)
    parser.add_argument("--lots", type=int, default=1)
    parser.add_argument("--commission-rate", type=float, default=0.0001)
    parser.add_argument("--slippage-ticks", type=float, default=1.0)
    parser.add_argument("--atr-window", type=int, default=14)
    parser.add_argument("--gap", type=int, default=3)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    d1_csv = Path(args.d1_csv)
    intraday_arg = args.m15_csv or args.m5_csv
    if not intraday_arg:
        raise ValueError("DS09 sandbox requires --m15-csv.")
    m15_csv = Path(intraday_arg)
    config = DS09BacktestConfig(
        initial_cash=args.initial_cash,
        lots=args.lots,
        commission_rate=args.commission_rate,
        slippage_ticks=args.slippage_ticks,
        atr_window=args.atr_window,
        gap=args.gap,
        futures_mode=True,
        spec=get_futures_spec(d1_csv) or get_futures_spec(m15_csv),
    )
    symbol = args.symbol or m15_csv.stem.replace("_15m_latest", "").replace("_5m_latest", "")
    saved = plot_trade(d1_csv, m15_csv, args.trade_no, Path(args.out), args.before, args.after, config, symbol)
    print(f"Saved DS09 sandbox chart to {saved}")


if __name__ == "__main__":
    main()
