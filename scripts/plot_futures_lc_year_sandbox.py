"""碳酸锂(LC) 近一年日线峰极连线沙盒 + 近期各定式触发扫描。"""
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

from backtest_ds07 import build_os_detail_frame  # noqa: E402
from quant.ds01 import ds01_left_filter_pass, entry_fill  # noqa: E402
from quant.ds03 import make_ds03_signal  # noqa: E402


def set_font() -> None:
    plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "Noto Sans CJK SC", "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False


def load_futures_csv(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path)
    frame.columns = [str(c).strip().lower() for c in frame.columns]
    if "date" not in frame.columns:
        for c in ["datetime", "timestamp", "time"]:
            if c in frame.columns:
                frame = frame.rename(columns={c: "date"})
                break
    if "date" not in frame.columns and len(frame.columns) >= 6:
        frame = frame.rename(
            columns={
                frame.columns[0]: "skip0",
                frame.columns[1]: "skip1",
                frame.columns[2]: "skip2",
                frame.columns[3]: "skip3",
                frame.columns[4]: "open",
                frame.columns[5]: "high",
                frame.columns[6]: "low",
                frame.columns[7]: "close",
            }
        )
        if "datetime" in frame.columns:
            frame["date"] = frame["datetime"]
    if "volume" not in frame.columns:
        frame["volume"] = 0.0
    need = ["date", "open", "high", "low", "close", "volume"]
    missing = [c for c in need if c not in frame.columns]
    if missing:
        raise ValueError(f"{path} missing {missing}, cols={list(frame.columns)}")
    frame = frame[need].copy()
    if "date" in frame.columns:
        frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
    elif "datetime" in frame.columns:
        raw_dt = frame["datetime"]
        if pd.to_numeric(raw_dt, errors="coerce").notna().all():
            frame["date"] = pd.to_datetime(pd.to_numeric(raw_dt), unit="ns", errors="coerce")
        else:
            frame["date"] = pd.to_datetime(raw_dt, errors="coerce")
    else:
        raise ValueError("no date/datetime column")
    for c in ["open", "high", "low", "close", "volume"]:
        frame[c] = pd.to_numeric(frame[c], errors="coerce")
    frame = frame.dropna(subset=["date", "open", "high", "low", "close"])
    frame = frame[(frame["date"] >= pd.Timestamp("2020-01-01")) & (frame["date"] <= pd.Timestamp("2030-12-31"))]
    frame = frame[(frame["high"] > frame["low"]) & (frame["close"] >= 1000.0)]
    return frame.sort_values("date").drop_duplicates("date", keep="last").reset_index(drop=True)


def draw_candles(ax, df: pd.DataFrame) -> None:
    xs = mdates.date2num(pd.to_datetime(df["date"]).dt.to_pydatetime())
    for x, row in zip(xs, df.itertuples(index=False)):
        o, h, l, c = float(row.open), float(row.high), float(row.low), float(row.close)
        color = "#d62728" if c >= o else "#1f77b4"
        ax.vlines(x, l, h, color=color, linewidth=0.85, alpha=0.92)
        ax.add_patch(
            Rectangle(
                (x - 0.31, min(o, c)),
                0.62,
                max(abs(c - o), 1e-10),
                facecolor=color,
                edgecolor=color,
                alpha=0.72,
            )
        )


def draw_camp(ax, df: pd.DataFrame) -> None:
    xs = mdates.date2num(pd.to_datetime(df["date"]).dt.to_pydatetime())
    for x, camp in zip(xs, df["camp"].astype(int)):
        if camp == 1:
            ax.axvspan(x - 0.5, x + 0.5, facecolor="#ffdddd", alpha=0.26, linewidth=0)
        elif camp == -1:
            ax.axvspan(x - 0.5, x + 0.5, facecolor="#dde8ff", alpha=0.28, linewidth=0)


def draw_hardened(ax, os_df: pd.DataFrame, nodes: list, start: int, end: int) -> None:
    vis = sorted([n for n in nodes if start <= int(n.point_idx) <= end], key=lambda n: n.point_idx)
    if len(vis) < 2:
        return
    xs = [mdates.date2num(pd.to_datetime(os_df.iloc[int(n.point_idx)]["date"])) for n in vis]
    ys = [float(n.price) for n in vis]
    ax.plot(xs, ys, color="#6f35b5", linewidth=2.0, marker="o", markersize=3.8, label="峰极硬化连线")
    for n, x, y in zip(vis, xs, ys):
        ax.text(x, y, "峰" if n.raw_type == "HIGH" else "极", fontsize=7, color="#4a148c", ha="center", va="bottom" if n.raw_type == "HIGH" else "top")


def scan_ds01(os_df, engine, i: int) -> dict | None:
    if i < 1:
        return None
    prev, cur = os_df.iloc[i - 1], os_df.iloc[i]
    camp = int(cur.get("camp", 0))
    visible = engine.hardened_by_bar[max(0, i - 1)] if engine.hardened_by_bar else []
    if camp == 1 and float(prev["close"]) > float(prev["open"]):
        trigger = float(prev["high"])
        if float(cur["high"]) <= trigger:
            return None
        left_price = float(cur["high"])
        ok, cnt = ds01_left_filter_pass(visible, i, left_price, False, 30)
        if not ok:
            return None
        return {"strategy": "DS01", "side": "long", "trigger": trigger, "stop": float(prev["low"]), "left": cnt}
    if camp == -1 and float(prev["close"]) < float(prev["open"]):
        trigger = float(prev["low"])
        if float(cur["low"]) >= trigger:
            return None
        left_price = float(cur["low"])
        ok, cnt = ds01_left_filter_pass(visible, i, left_price, False, 30)
        if not ok:
            return None
        return {"strategy": "DS01", "side": "short", "trigger": trigger, "stop": float(prev["high"]), "left": cnt}
    return None


def scan_signals(os_df, engine, lookback_days: int = 21) -> pd.DataFrame:
    rows = []
    start_i = max(1, len(os_df) - lookback_days)
    consumed: set[str] = set()
    for i in range(start_i, len(os_df)):
        d = str(os_df.iloc[i]["date"])[:10]
        s1 = scan_ds01(os_df, engine, i)
        if s1:
            rows.append({"date": d, **s1})
        s3 = make_ds03_signal(os_df, i, consumed)
        if s3:
            rows.append(
                {
                    "date": d,
                    "strategy": "DS03",
                    "side": "long" if s3.side == 1 else "short",
                    "trigger": s3.entry_ref,
                    "stop": s3.initial_stop,
                    "left": "",
                    "source": s3.trigger_source,
                }
            )
    return pd.DataFrame(rows)


def plot(args: argparse.Namespace) -> Path:
    raw = load_futures_csv(Path(args.csv))
    if args.days > 0 and len(raw) > args.days:
        raw = raw.tail(args.days).reset_index(drop=True)
    os_df, engine = build_os_detail_frame(raw, gap=int(args.gap))
    signals = scan_signals(os_df, engine, lookback_days=int(args.scan_days))

    start = max(0, len(os_df) - int(args.plot_days))
    window = os_df.iloc[start:].copy()
    nodes = engine.hardened_by_bar[-1] if engine.hardened_by_bar else []

    set_font()
    fig, ax = plt.subplots(figsize=(18, 9), dpi=150)
    draw_camp(ax, window)
    draw_candles(ax, window)
    draw_hardened(ax, os_df, nodes, start, len(os_df) - 1)

    for _, sig in signals.iterrows():
        day = pd.to_datetime(sig["date"])
        idxs = os_df.index[pd.to_datetime(os_df["date"]).dt.normalize() == day.normalize()]
        if len(idxs) == 0:
            continue
        i = int(idxs[-1])
        x = mdates.date2num(pd.to_datetime(os_df.iloc[i]["date"]))
        y = float(sig["trigger"])
        color = "#00897b" if sig["side"] == "long" else "#c62828"
        mk = "^" if sig["side"] == "long" else "v"
        ax.scatter(x, y, marker=mk, s=90, color=color, zorder=9)
        ax.text(
            x,
            y,
            f"{sig['strategy']} {sig['side']}\n{float(sig['trigger']):.6g}",
            fontsize=7,
            color=color,
            ha="center",
            va="bottom" if sig["side"] == "long" else "top",
        )

    last_date = str(os_df.iloc[-1]["date"])[:10]
    title = f"碳酸锂 LC 日线沙盒（近{args.plot_days}根）| 数据至 {last_date} | 扫描近{args.scan_days}日信号 {len(signals)} 条"
    ax.set_title(title, fontsize=12)
    ax.set_ylabel("Price")
    ax.grid(True, linestyle=":", alpha=0.25)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m-%d"))
    ax.legend(loc="upper left", fontsize=8)
    fig.autofmt_xdate()
    fig.tight_layout()

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out)
    plt.close(fig)

    report = out.with_suffix(".signals.csv")
    signals.to_csv(report, index=False, encoding="utf-8-sig")
    print(f"saved={out}")
    print(f"signals={report}")
    if not signals.empty:
        print(signals.to_string(index=False))
    else:
        print("近段无 DS01/DS03 触发（或左30/假峰条件未过）")
    return out


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--csv", required=True)
    p.add_argument("--out", default="results/sandbox/lc_year/LC_1y_sandbox.png")
    p.add_argument("--days", type=int, default=400, help="OS 计算用尾部 K 数")
    p.add_argument("--plot-days", type=int, default=260, help="图上显示 K 数（约一年）")
    p.add_argument("--scan-days", type=int, default=21, help="近期信号扫描天数")
    p.add_argument("--gap", type=int, default=3)
    return p.parse_args()


if __name__ == "__main__":
    plot(parse_args())
