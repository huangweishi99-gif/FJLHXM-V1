from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.patches import Rectangle

from backtest_ds07 import DS07BacktestConfig, load_frame, run_ds07_backtest
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


def draw_camp_background(ax, df: pd.DataFrame, span_width: float) -> None:
    xs = mdates.date2num(pd.to_datetime(df["date"]).dt.to_pydatetime())
    for idx, (_, row) in enumerate(df.iterrows()):
        camp = int(row.get("camp", 0))
        if camp == 0:
            continue
        color = "#ffdddd" if camp == 1 else "#dde8ff"
        ax.axvspan(xs[idx] - span_width, xs[idx] + span_width, facecolor=color, alpha=0.24, linewidth=0)


def draw_h1_background(ax, df: pd.DataFrame) -> None:
    draw_camp_background(ax, df, 0.02)


def draw_d1_alignment_band(ax, df: pd.DataFrame) -> None:
    xs = mdates.date2num(pd.to_datetime(df["date"]).dt.to_pydatetime())
    y0, y1 = ax.get_ylim()
    height = (y1 - y0) * 0.018
    for idx, (_, row) in enumerate(df.iterrows()):
        d1_camp = int(row.get("d1_camp", 0))
        h1_camp = int(row.get("camp", 0))
        if d1_camp == 0:
            continue
        color = "#c62828" if d1_camp == 1 else "#1565c0"
        alpha = 0.75 if d1_camp == h1_camp else 0.22
        ax.add_patch(Rectangle((xs[idx] - 0.02, y1 - height), 0.04, height, facecolor=color, edgecolor=color, alpha=alpha, linewidth=0))


def draw_hardened_line(ax, df: pd.DataFrame, hardened_nodes: list, start: int, end: int) -> None:
    nodes = sorted([node for node in hardened_nodes if start <= node.point_idx <= end], key=lambda node: (node.point_idx, node.confirm_idx))
    if len(nodes) < 2:
        return
    xs = [mdates.date2num(pd.to_datetime(df.iloc[node.point_idx]["date"])) for node in nodes]
    ys = [node.price for node in nodes]
    ax.plot(xs, ys, color="#6f35b5", linewidth=1.8, marker="o", markersize=3, label="H1 hardened_fengji_line")


def draw_d1_hardened_line(ax, df: pd.DataFrame, hardened_nodes: list, start_date: pd.Timestamp, end_date: pd.Timestamp) -> None:
    nodes = [
        node
        for node in hardened_nodes
        if start_date <= pd.to_datetime(df.iloc[node.point_idx]["date"]) <= end_date
    ]
    nodes = sorted(nodes, key=lambda node: (node.point_idx, node.confirm_idx))
    if len(nodes) < 2:
        return
    xs = [mdates.date2num(pd.to_datetime(df.iloc[node.point_idx]["date"])) for node in nodes]
    ys = [node.price for node in nodes]
    ax.plot(xs, ys, color="#6f35b5", linewidth=1.9, marker="o", markersize=3.5, label="D1 hardened_fengji_line")


def draw_stop_path(ax, df: pd.DataFrame, stop_history: pd.DataFrame, trade_no: int) -> None:
    if stop_history.empty:
        return
    rows = stop_history[stop_history["trade_no"] == trade_no].copy()
    if rows.empty:
        return
    xs = [mdates.date2num(pd.to_datetime(df.iloc[int(idx)]["date"])) for idx in rows["idx"]]
    ax.step(xs, rows["stop"].astype(float), where="post", color="#8e24aa", linewidth=1.5, label="H1 guard-extreme stop")


def draw_trade_marks(ax, df: pd.DataFrame, trade: pd.Series, start: int, end: int) -> None:
    side = 1 if trade["direction"] == "long" else -1
    attack_idx = int(trade["attack_idx"])
    defense_idx = int(trade["defense_idx"])
    entry_idx = int(trade["entry_idx"])
    exit_idx = int(trade["exit_idx"])

    if start <= attack_idx <= end:
        x = mdates.date2num(pd.to_datetime(df.iloc[attack_idx]["date"]))
        ax.scatter(x, float(trade["attack_price"]), marker="o", s=90, color="#6a00a8", zorder=7, label="H1 attack peak")
        ax.text(x, float(trade["attack_price"]), "H1进攻峰", color="#6a00a8", fontsize=8, ha="center", va="bottom" if side == 1 else "top")

    if start <= defense_idx <= end:
        x = mdates.date2num(pd.to_datetime(df.iloc[defense_idx]["date"]))
        ax.scatter(x, float(trade["defense_price"]), marker="o", s=90, color="#455a64", zorder=7, label="H1 defense extreme")
        ax.text(x, float(trade["defense_price"]), "H1防守极", color="#455a64", fontsize=8, ha="center", va="top" if side == 1 else "bottom")

    if start <= entry_idx <= end:
        x = mdates.date2num(pd.to_datetime(df.iloc[entry_idx]["date"]))
        ax.scatter(x, float(trade["entry_price"]), marker="^" if side == 1 else "v", s=120, color="#00a152", zorder=8, label="entry")
        ax.text(x, float(trade["entry_price"]), "共振启动棍", color="#00695c", fontsize=8, ha="center", va="bottom" if side == 1 else "top")

    if start <= exit_idx <= end:
        x = mdates.date2num(pd.to_datetime(df.iloc[exit_idx]["date"]))
        ax.scatter(x, float(trade["exit_price"]), marker="v" if side == 1 else "^", s=120, color="#f57c00", zorder=8, label="exit")

    ax.axhline(float(trade["attack_price"]), color="#7b1fa2", linestyle="--", linewidth=1.0, label="attack ref")
    ax.axhline(float(trade["defense_price"]), color="#455a64", linestyle=":", linewidth=1.0, label="initial defense")


def draw_d1_authorization(ax, d1_df: pd.DataFrame, trade: pd.Series) -> None:
    session_date = pd.to_datetime(trade["session_date"]).normalize()
    safe_source = session_date - pd.Timedelta(days=1)
    d1_dates = pd.to_datetime(d1_df["date"]).dt.normalize()
    prior_dates = d1_dates[d1_dates < session_date]
    if not prior_dates.empty:
        safe_source = prior_dates.max()

    ax.axvline(safe_source, color="#263238", linestyle="--", linewidth=1.1, label="safe D1 close")
    ax.axvline(session_date, color="#00a152", linestyle="-.", linewidth=1.1, label="H1 session")
    y0, y1 = ax.get_ylim()
    y = y1 - (y1 - y0) * 0.07
    camp_text = "D1红授权" if int(trade["d1_camp"]) == 1 else "D1蓝授权"
    ax.text(mdates.date2num(safe_source), y, camp_text, color="#263238", fontsize=9, ha="center", va="top")


def plot_trade(d1_csv: Path, h1_csv: Path, trade_no: int, out_path: Path, before: int, after: int, config: DS07BacktestConfig, symbol: str) -> Path:
    d1_df = load_frame(d1_csv, config.atr_window)
    h1_df = load_frame(h1_csv, config.atr_window)
    result = run_ds07_backtest(d1_df, h1_df, config, symbol=symbol)
    trades = result["trades"]
    if trades.empty:
        raise ValueError(f"No DS07 trades found in {h1_csv}")
    trade_row = trades[trades["trade_no"] == trade_no]
    if trade_row.empty:
        available = ", ".join(str(x) for x in trades["trade_no"].tolist()[:20])
        raise ValueError(f"trade_no {trade_no} not found. Available starts with: {available}")
    trade = trade_row.iloc[0]
    start = max(0, int(trade["entry_idx"]) - before)
    end = min(len(result["h1_df"]) - 1, int(trade["exit_idx"]) + after)
    window = result["h1_df"].iloc[start : end + 1].copy()
    start_date = pd.to_datetime(window["date"].iloc[0]).normalize() - pd.Timedelta(days=3)
    end_date = pd.to_datetime(window["date"].iloc[-1]).normalize() + pd.Timedelta(days=3)
    d1_window = result["d1_df"][
        (pd.to_datetime(result["d1_df"]["date"]) >= start_date)
        & (pd.to_datetime(result["d1_df"]["date"]) <= end_date)
    ].copy()

    set_chinese_font()
    fig, (ax_d1, ax_h1) = plt.subplots(
        2,
        1,
        figsize=(17, 10),
        dpi=140,
        sharex=False,
        gridspec_kw={"height_ratios": [1.0, 2.2]},
    )

    if not d1_window.empty:
        draw_camp_background(ax_d1, d1_window, 0.42)
        draw_candles(ax_d1, d1_window, width=0.55)
        draw_d1_hardened_line(ax_d1, result["d1_df"], result["d1_engine"].hardened_nodes, start_date, end_date)
        draw_d1_authorization(ax_d1, result["d1_df"], trade)
    ax_d1.set_title("D1 strategic OS: previous closed daily camp is bridged into H1", fontsize=10)
    ax_d1.set_ylabel("D1 Price")
    ax_d1.grid(True, linestyle=":", alpha=0.23)
    ax_d1.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m-%d"))
    ax_d1.legend(loc="best", fontsize=8)

    draw_h1_background(ax_h1, window)
    draw_candles(ax_h1, window)
    draw_hardened_line(ax_h1, result["h1_df"], result["h1_engine"].hardened_nodes, start, end)
    draw_trade_marks(ax_h1, result["h1_df"], trade, start, end)
    draw_stop_path(ax_h1, result["h1_df"], result["stop_history"], trade_no)
    draw_d1_alignment_band(ax_h1, window)

    title = (
        f"{symbol} DS07 sandbox trade {trade_no} | {trade['direction']} | "
        f"PnL {float(trade['net_pnl']):.2f} | D1/H1={int(trade['d1_camp'])}/{int(trade['h1_camp'])} | "
        f"{trade.get('trigger_type', '')} | attack={float(trade['attack_price']):.2f} defense={float(trade['defense_price']):.2f}"
    )
    ax_h1.set_title(title, fontsize=12)
    ax_h1.set_ylabel("H1 Price")
    ax_h1.grid(True, linestyle=":", alpha=0.25)
    ax_h1.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m-%d %H:%M"))
    ax_h1.legend(loc="best", fontsize=8)
    fig.autofmt_xdate()
    fig.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path)
    plt.close(fig)
    return out_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Plot DS07 D1/H1 resonance sandbox chart.")
    parser.add_argument("--d1-csv", required=True)
    parser.add_argument("--h1-csv", required=True)
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
    d1_csv = Path(args.d1_csv)
    h1_csv = Path(args.h1_csv)
    config = DS07BacktestConfig(
        initial_cash=args.initial_cash,
        lots=args.lots,
        commission_rate=args.commission_rate,
        slippage_ticks=args.slippage_ticks,
        atr_window=args.atr_window,
        gap=args.gap,
        futures_mode=True,
        spec=get_futures_spec(d1_csv),
    )
    symbol = args.symbol or h1_csv.stem.replace("_60m", "")
    saved = plot_trade(d1_csv, h1_csv, args.trade_no, Path(args.out), args.before, args.after, config, symbol)
    print(f"Saved DS07 sandbox chart to {saved}")


if __name__ == "__main__":
    main()
