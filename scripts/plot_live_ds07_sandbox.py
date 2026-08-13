"""Plot DS07 D1+H1 physical sandbox for a live pending-order trigger."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.patches import Rectangle

ROOT = Path(__file__).resolve().parents[1]
for p in (ROOT / "src", ROOT / "packages" / "fengji_core"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from backtest_ds07 import DS07BacktestConfig, build_os_detail_frame, load_frame, run_ds07_backtest
from quant.ds07 import entry_fill, make_ds07_signal


def set_font() -> None:
    plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "Noto Sans CJK SC", "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False


def resolve_csv(data_dir: Path, symbol: str, tf: str) -> Path:
    sym = symbol.upper().replace("-", "")
    candidates = [
        data_dir / tf / f"{sym}.csv",
        data_dir / "crypto_okx" / f"{symbol.upper().replace('USDT', '-USDT')}_{'1D' if tf == '1d' else '1H'}_1825d.csv",
        data_dir / "crypto_okx" / f"{sym.replace('USDT', '-USDT')}_{'1D' if tf == '1d' else '1H'}_1825d.csv",
    ]
    for path in candidates:
        if path.exists():
            return path
    raise FileNotFoundError(f"No {tf} csv for {symbol}: tried {candidates}")


def draw_candles(ax, df: pd.DataFrame, width: float) -> None:
    xs = mdates.date2num(pd.to_datetime(df["date"]).dt.to_pydatetime())
    for x, (_, row) in zip(xs, df.iterrows()):
        o, h, l, c = float(row["open"]), float(row["high"]), float(row["low"]), float(row["close"])
        color = "#d62728" if c >= o else "#1f77b4"
        ax.vlines(x, l, h, color=color, linewidth=0.8, alpha=0.9)
        ax.add_patch(
            Rectangle((x - width / 2, min(o, c)), width, max(abs(c - o), 1e-12), facecolor=color, edgecolor=color, alpha=0.76)
        )


def draw_camp(ax, df: pd.DataFrame, span: float) -> None:
    xs = mdates.date2num(pd.to_datetime(df["date"]).dt.to_pydatetime())
    for idx, (_, row) in enumerate(df.iterrows()):
        camp = int(row.get("camp", 0) or 0)
        if camp == 1:
            ax.axvspan(xs[idx] - span, xs[idx] + span, facecolor="#ffdddd", alpha=0.24, linewidth=0)
        elif camp == -1:
            ax.axvspan(xs[idx] - span, xs[idx] + span, facecolor="#dde8ff", alpha=0.24, linewidth=0)


def draw_hardened(ax, full_df: pd.DataFrame, nodes: list, start: int, end: int, width: float = 1.8) -> None:
    pts = sorted([n for n in nodes if start <= n.point_idx <= end], key=lambda n: (n.point_idx, n.confirm_idx))
    if len(pts) < 2:
        return
    xs = [mdates.date2num(pd.to_datetime(full_df.iloc[n.point_idx]["date"])) for n in pts]
    ys = [float(n.price) for n in pts]
    ax.plot(xs, ys, color="#6f35b5", linewidth=width, marker="o", markersize=3.5, label="hardened_fengji_line")


def draw_d1_band(ax, df: pd.DataFrame) -> None:
    xs = mdates.date2num(pd.to_datetime(df["date"]).dt.to_pydatetime())
    y0, y1 = ax.get_ylim()
    h = (y1 - y0) * 0.018
    for idx, (_, row) in enumerate(df.iterrows()):
        d1 = int(row.get("d1_camp", 0) or 0)
        h1 = int(row.get("camp", 0) or 0)
        if not d1:
            continue
        color = "#c62828" if d1 == 1 else "#1565c0"
        alpha = 0.75 if d1 == h1 else 0.22
        ax.add_patch(Rectangle((xs[idx] - 0.02, y1 - h), 0.04, h, facecolor=color, edgecolor=color, alpha=alpha, linewidth=0))


def find_bar_index(h1: pd.DataFrame, when: pd.Timestamp) -> int:
    dates = pd.to_datetime(h1["date"])
    hits = h1.index[dates <= when]
    if len(hits) == 0:
        raise ValueError(f"No H1 bar at or before {when}")
    return int(hits[-1])


def plot_live(args: argparse.Namespace) -> Path:
    data_dir = Path(args.data_dir)
    d1_path = resolve_csv(data_dir, args.symbol, "1d")
    h1_path = resolve_csv(data_dir, args.symbol, "1h")
    cfg = DS07BacktestConfig(gap=int(args.gap), futures_mode=False)
    result = run_ds07_backtest(load_frame(d1_path, cfg.atr_window), load_frame(h1_path, cfg.atr_window), cfg, symbol=args.symbol)
    h1 = result["h1_df"]
    d1 = result["d1_df"]
    when = pd.to_datetime(args.trigger_time)
    i = find_bar_index(h1, when)
    row = h1.iloc[i]
    prev = h1.iloc[i - 1] if i > 0 else None
    sig = make_ds07_signal(row, i, set(), symbol=args.symbol, prev_row=prev, df=h1) if prev is not None else None

    start = max(0, i - int(args.before))
    end = min(len(h1) - 1, i + int(args.after))
    win = h1.iloc[start : end + 1].copy()
    d1_start = pd.to_datetime(win["date"].iloc[0]).normalize() - pd.Timedelta(days=5)
    d1_end = pd.to_datetime(win["date"].iloc[-1]).normalize() + pd.Timedelta(days=2)
    d1_win = d1[(pd.to_datetime(d1["date"]) >= d1_start) & (pd.to_datetime(d1["date"]) <= d1_end)].copy()

    trigger = float(args.trigger_price)
    stop = float(args.stop_price)
    fill = float(args.fill_price) if args.fill_price else (entry_fill(row, sig) if sig else trigger)
    attack_idx = int(sig.attack_idx) if sig else -1
    defense_idx = int(sig.defense_idx) if sig else -1
    pattern = sig.pattern if sig else args.pattern

    set_font()
    fig, (ax_d1, ax_h1) = plt.subplots(2, 1, figsize=(17, 10), dpi=150, gridspec_kw={"height_ratios": [1.0, 2.2]})

    if not d1_win.empty:
        draw_camp(ax_d1, d1_win, 0.42)
        draw_candles(ax_d1, d1_win, 0.55)
        draw_hardened(ax_d1, d1, result["d1_engine"].hardened_nodes, int(d1_win.index[0]), int(d1_win.index[-1]))
        session = pd.to_datetime(row.get("session_date", when)).normalize()
        ax_d1.axvline(session - pd.Timedelta(days=1), color="#263238", linestyle="--", linewidth=1.0, label="safe D1")
        ax_d1.axvline(session, color="#00a152", linestyle="-.", linewidth=1.0, label="H1 session")
    ax_d1.set_title(f"D1 OS | D1 camp={int(row.get('d1_camp', 0))}", fontsize=10)
    ax_d1.set_ylabel("D1")
    ax_d1.grid(True, linestyle=":", alpha=0.22)
    ax_d1.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m-%d"))
    ax_d1.legend(loc="best", fontsize=8)

    draw_camp(ax_h1, win, 0.02)
    draw_candles(ax_h1, win, 0.028)
    draw_hardened(ax_h1, h1, result["h1_engine"].hardened_nodes, start, end)
    draw_d1_band(ax_h1, win)

    entry_x = mdates.date2num(pd.to_datetime(row["date"]))
    side = str(args.side).lower()
    entry_marker = "^" if side == "long" else "v"
    entry_color = "#00a152" if side == "long" else "#c62828"
    ax_h1.scatter(entry_x, fill, marker=entry_marker, s=140, color=entry_color, zorder=9, label="trigger/fill")
    ax_h1.axhline(trigger, color="#7b1fa2", linestyle="--", linewidth=1.1, label=f"trigger {trigger:g}")
    ax_h1.axhline(stop, color="#8e24aa", linestyle=":", linewidth=1.1, label=f"stop {stop:g}")
    if attack_idx >= start:
        ax_h1.scatter(
            mdates.date2num(pd.to_datetime(h1.iloc[attack_idx]["date"])),
            float(sig.attack_price) if sig else trigger,
            marker="o",
            s=90,
            color="#6a00a8",
            zorder=8,
            label="H1 attack ref",
        )
    if defense_idx >= start:
        ax_h1.scatter(
            mdates.date2num(pd.to_datetime(h1.iloc[defense_idx]["date"])),
            float(sig.defense_price) if sig else stop,
            marker="o",
            s=90,
            color="#455a64",
            zorder=8,
            label="H1 defense ref",
        )
    ax_h1.axvline(entry_x, color="#ff9800", linestyle="-.", linewidth=1.0, alpha=0.8, label="trigger bar")

    audit = "signal_ok" if sig else "signal_missing"
    if sig:
        audit += f" | type={sig.trigger_type} | attack={sig.attack_price:.6g} defense={sig.defense_price:.6g}"
    title = (
        f"{args.symbol} DS07 live sandbox | {side} | {when} | H1 camp={int(row.get('camp', 0))} "
        f"prev_h1={int(prev.get('camp', 0)) if prev is not None else 0}\n{pattern} | {audit}"
    )
    ax_h1.set_title(title, fontsize=11)
    ax_h1.set_ylabel("H1")
    ax_h1.grid(True, linestyle=":", alpha=0.24)
    ax_h1.xaxis.set_major_formatter(mdates.DateFormatter("%m-%d %H:%M"))
    ax_h1.legend(loc="best", fontsize=8)
    fig.autofmt_xdate()
    fig.tight_layout()

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out)
    plt.close(fig)
    print(f"saved={out}\nidx={i} bar={row['date']} audit={audit}")
    return out


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Plot DS07 D1+H1 live trigger sandbox.")
    p.add_argument("--symbol", required=True)
    p.add_argument("--trigger-time", required=True, help="Asia/Shanghai local time of Feishu message")
    p.add_argument("--side", default="long", choices=("long", "short"))
    p.add_argument("--trigger-price", type=float, required=True)
    p.add_argument("--stop-price", type=float, required=True)
    p.add_argument("--fill-price", type=float, default=0.0)
    p.add_argument("--pattern", default="")
    p.add_argument("--data-dir", default="data")
    p.add_argument("--out", required=True)
    p.add_argument("--before", type=int, default=48)
    p.add_argument("--after", type=int, default=12)
    p.add_argument("--gap", type=int, default=3)
    return p.parse_args()


if __name__ == "__main__":
    plot_live(parse_args())
