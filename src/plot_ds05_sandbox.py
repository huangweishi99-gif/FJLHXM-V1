from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.patches import Rectangle

from backtest_ds05 import DS05BacktestConfig, run_ds05_backtest
from quant.data import load_ohlcv_for_engine
from quant.futures_specs import get_futures_spec
from quant.os_engine import IdentityNode, build_identity_line


def set_chinese_font() -> None:
    plt.rcParams["font.sans-serif"] = [
        "Microsoft YaHei",
        "SimHei",
        "Noto Sans CJK SC",
        "Arial Unicode MS",
        "DejaVu Sans",
    ]
    plt.rcParams["axes.unicode_minus"] = False


def draw_candles(ax, df: pd.DataFrame, width: float = 0.62) -> None:
    x_values = mdates.date2num(pd.to_datetime(df["date"]).dt.to_pydatetime())
    for x, (_, row) in zip(x_values, df.iterrows()):
        open_ = float(row["open"])
        high = float(row["high"])
        low = float(row["low"])
        close = float(row["close"])
        color = "#d62728" if close >= open_ else "#1f77b4"
        body_low = min(open_, close)
        body_height = max(abs(close - open_), 1e-9)
        ax.vlines(x, low, high, color=color, linewidth=0.9, alpha=0.9)
        ax.add_patch(
            Rectangle(
                (x - width / 2, body_low),
                width,
                body_height,
                facecolor=color,
                edgecolor=color,
                linewidth=0.8,
                alpha=0.75,
            )
        )


def draw_camp_background(ax, df: pd.DataFrame) -> None:
    dates = mdates.date2num(pd.to_datetime(df["date"]).dt.to_pydatetime())
    for idx, (_, row) in enumerate(df.iterrows()):
        camp = int(row.get("camp", 0))
        if camp == 0:
            continue
        left = dates[idx] - 0.5
        right = dates[idx] + 0.5
        color = "#ffdddd" if camp == 1 else "#dde8ff"
        ax.axvspan(left, right, facecolor=color, alpha=0.25, linewidth=0)


def nodes_from_frame(identity_nodes: pd.DataFrame) -> list[IdentityNode]:
    nodes: list[IdentityNode] = []
    if identity_nodes.empty:
        return nodes
    for row in identity_nodes.to_dict("records"):
        nodes.append(
            IdentityNode(
                point_idx=int(row["point_idx"]),
                confirm_idx=int(row["confirm_idx"]),
                price=float(row["price"]),
                raw_type=str(row["raw_type"]),
                identity=str(row["identity"]),
                camp=int(row["camp"]),
                note=str(row.get("note", "")),
                source=str(row.get("source", "")),
            )
        )
    return nodes


def draw_identity_line(ax, df: pd.DataFrame, identity_nodes: pd.DataFrame, start: int, end: int) -> None:
    line = build_identity_line(nodes_from_frame(identity_nodes))
    points = [node for node in line if start <= node.point_idx <= end]
    if len(points) < 2:
        return
    xs = [mdates.date2num(pd.to_datetime(df.iloc[node.point_idx]["date"])) for node in points]
    ys = [node.price for node in points]
    ax.plot(xs, ys, color="#111111", linewidth=1.8, marker="o", markersize=4, label="identity_line")
    for node, x, y in zip(points, xs, ys):
        color = "#d62728" if node.camp == 1 else "#1f77b4"
        ax.text(x, y, node.identity.replace("_", "\n"), color=color, fontsize=7, ha="center", va="bottom")


def draw_hardened_line(ax, df: pd.DataFrame, hardened_nodes: list, start: int, end: int) -> None:
    """Draw the physical FengJi line: hardened alternating HIGH/LOW nodes."""
    points = [node for node in hardened_nodes if start <= node.point_idx <= end]
    points = sorted(points, key=lambda node: (node.point_idx, node.confirm_idx))
    if len(points) < 2:
        return

    xs = [mdates.date2num(pd.to_datetime(df.iloc[node.point_idx]["date"])) for node in points]
    ys = [node.price for node in points]
    ax.plot(xs, ys, color="#6f35b5", linewidth=2.2, marker="o", markersize=4, label="hardened_fengji_line")


def draw_tagged_line(ax, df: pd.DataFrame, identity_nodes: pd.DataFrame, start: int, end: int) -> None:
    """Draw the older common-version physical line: sorted adjacent tagged nodes."""
    nodes = [
        node
        for node in nodes_from_frame(identity_nodes)
        if node.identity not in {"FAILED_HIGH", "FAILED_LOW"} and start <= node.point_idx <= end
    ]
    nodes = sorted(nodes, key=lambda node: (node.point_idx, node.confirm_idx, node.identity))
    deduped: list[IdentityNode] = []
    seen: set[int] = set()
    for node in nodes:
        if node.point_idx in seen:
            continue
        seen.add(node.point_idx)
        deduped.append(node)

    if len(deduped) < 2:
        return

    xs = [mdates.date2num(pd.to_datetime(df.iloc[node.point_idx]["date"])) for node in deduped]
    ys = [node.price for node in deduped]
    ax.plot(xs, ys, color="#777777", linewidth=1.0, linestyle="--", marker=".", markersize=3, label="tagged_line_check")


def draw_trade_marks(ax, df: pd.DataFrame, trade: pd.Series, start: int, end: int) -> None:
    side = 1 if trade["direction"] == "long" else -1
    entry_idx = int(trade["entry_idx"])
    exit_idx = int(trade["exit_idx"])
    k1 = int(trade["k1"])
    k2 = int(trade["k2"])
    k3 = int(trade["k3"])

    for idx, label in [(k1, "K1"), (k2, "K2"), (k3, "K3")]:
        if start <= idx <= end:
            x = mdates.date2num(pd.to_datetime(df.iloc[idx]["date"]))
            if label == "K2":
                y = float(df.iloc[idx]["low"]) if side == 1 else float(df.iloc[idx]["high"])
                va = "top" if side == 1 else "bottom"
            else:
                y = float(df.iloc[idx]["high"]) if side == 1 else float(df.iloc[idx]["low"])
                va = "bottom" if side == 1 else "top"
            ax.text(x, y, label, fontsize=10, fontweight="bold", ha="center", va=va, color="#6a00a8")

    entry_x = mdates.date2num(pd.to_datetime(df.iloc[entry_idx]["date"]))
    exit_x = mdates.date2num(pd.to_datetime(df.iloc[exit_idx]["date"]))
    entry_marker = "^" if side == 1 else "v"
    exit_marker = "v" if side == 1 else "^"
    ax.scatter(entry_x, float(trade["entry_price"]), marker=entry_marker, s=100, color="#00a152", zorder=6, label="entry")
    ax.scatter(exit_x, float(trade["exit_price"]), marker=exit_marker, s=100, color="#f57c00", zorder=6, label="exit")
    ax.axhline(float(trade["initial_stop"]), color="#8e24aa", linestyle="--", linewidth=1.1, label="K2 initial stop")
    k2_extreme = trade.get("k2_possible_extreme", trade.get("initial_stop"))
    defense_identity = "K2 possible RED_EXT" if side == 1 else "K2 possible BLUE_EXT"
    ax.axhline(float(k2_extreme), color="#455a64", linestyle=":", linewidth=1.1, label=defense_identity)


def draw_stop_path(ax, df: pd.DataFrame, trade: pd.Series) -> None:
    side = 1 if trade["direction"] == "long" else -1
    stop = float(trade["initial_stop"])
    rows = []
    for idx in range(int(trade["entry_idx"]), int(trade["exit_idx"]) + 1):
        row = df.iloc[idx]
        if side == 1 and float(row["close"]) > float(row["open"]):
            stop = max(stop, float(row["low"]))
        elif side == -1 and float(row["close"]) < float(row["open"]):
            stop = min(stop, float(row["high"]))
        rows.append((pd.to_datetime(row["date"]), stop))

    if rows:
        xs = [mdates.date2num(date) for date, _ in rows]
        ys = [value for _, value in rows]
        ax.step(xs, ys, where="post", color="#8e24aa", linewidth=1.5, label="dynamic stop")


def plot_trade(
    csv_path: Path,
    trade_no: int,
    out_path: Path,
    before: int,
    after: int,
    config: DS05BacktestConfig,
    line_mode: str,
) -> Path:
    df = load_ohlcv_for_engine(csv_path, config.atr_window)
    result = run_ds05_backtest(df, config)
    trades = result["trades"]
    if trades.empty:
        raise ValueError(f"No DS05 trades found in {csv_path}")

    trade_rows = trades[trades["trade_no"] == trade_no]
    if trade_rows.empty:
        available = ", ".join(str(x) for x in trades["trade_no"].tolist()[:20])
        raise ValueError(f"trade_no {trade_no} not found. Available starts with: {available}")

    trade = trade_rows.iloc[0]
    start = max(0, int(trade["k1"]) - before)
    end = min(len(df) - 1, int(trade["exit_idx"]) + after)
    window = result["df"].iloc[start : end + 1].copy()

    set_chinese_font()
    fig, ax = plt.subplots(figsize=(16, 8), dpi=140)
    draw_camp_background(ax, window)
    draw_candles(ax, window)
    if line_mode in {"hardened", "all"}:
        draw_hardened_line(ax, result["df"], result["engine"].hardened_nodes, start, end)
    if line_mode in {"identity", "both", "all"}:
        draw_identity_line(ax, result["df"], result["identity_nodes"], start, end)
    if line_mode in {"tagged", "both", "all"}:
        draw_tagged_line(ax, result["df"], result["identity_nodes"], start, end)
    draw_trade_marks(ax, result["df"], trade, start, end)
    draw_stop_path(ax, result["df"], trade)

    title = (
        f"{csv_path.stem} DS05 sandbox trade {trade_no} | {trade['direction']} | "
        f"PnL {float(trade['net_pnl']):.2f} | camp K1/K2/K3="
        f"{int(trade['camp_k1'])}/{int(trade['camp_k2'])}/{int(trade['camp_k3'])} | "
        f"defense={'RED_EXT' if trade['direction'] == 'long' else 'BLUE_EXT'}"
    )
    ax.set_title(title, fontsize=12)
    ax.set_ylabel("Price")
    ax.grid(True, linestyle=":", alpha=0.28)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m-%d"))
    ax.legend(loc="best", fontsize=8)
    fig.autofmt_xdate()
    fig.tight_layout()

    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path)
    plt.close(fig)
    return out_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Plot a physical sandbox chart for one DS05 trade.")
    parser.add_argument("--csv", required=True, help="Source OHLCV CSV.")
    parser.add_argument("--trade-no", type=int, default=1)
    parser.add_argument("--out", default="", help="Output PNG path.")
    parser.add_argument("--before", type=int, default=30)
    parser.add_argument("--after", type=int, default=15)
    parser.add_argument("--line-mode", choices=["hardened", "identity", "tagged", "both", "all"], default="hardened")
    parser.add_argument("--initial-cash", type=float, default=100_000.0)
    parser.add_argument("--lots", type=int, default=1)
    parser.add_argument("--commission-rate", type=float, default=0.0001)
    parser.add_argument("--slippage-ticks", type=float, default=1.0)
    parser.add_argument("--atr-window", type=int, default=14)
    parser.add_argument("--extreme-atr-tol", type=float, default=0.80)
    parser.add_argument("--gap", type=int, default=3)
    parser.add_argument("--futures-mode", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    csv_path = Path(args.csv)
    out_path = Path(args.out) if args.out else Path("results") / "sandbox" / f"{csv_path.stem}_trade_{args.trade_no}.png"
    config = DS05BacktestConfig(
        initial_cash=args.initial_cash,
        lots=args.lots,
        commission_rate=args.commission_rate,
        slippage_ticks=args.slippage_ticks,
        atr_window=args.atr_window,
        extreme_atr_tol=args.extreme_atr_tol,
        gap=args.gap,
        futures_mode=args.futures_mode,
        spec=get_futures_spec(csv_path) if args.futures_mode else None,
    )
    saved = plot_trade(csv_path, args.trade_no, out_path, args.before, args.after, config, args.line_mode)
    print(f"Saved sandbox chart to {saved}")


if __name__ == "__main__":
    main()
