#!/usr/bin/env python3
"""Spot-check sandbox charts for N04 overseas camp_changed symbols."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
if str(ROOT / "packages" / "fengji_core") not in sys.path:
    sys.path.insert(0, str(ROOT / "packages" / "fengji_core"))

from backtest_ds07 import build_os_detail_frame
from plot_fengji_structure import (
    add_camp_legend,
    draw_camp_background,
    draw_candles,
    draw_hardened_line,
    draw_identity_labels,
    draw_turn_marks,
    set_chinese_font,
)

# N04 rebuild overseas camp_changed (2026-06-10)
SPOTCHECKS = [
    {"symbol": "ADAUSDT", "timeframe": "1h", "subdir": "1h", "start": "2026-05-20", "end": "2026-06-10", "note": "1h red->blue"},
    {"symbol": "BNBUSDT", "timeframe": "1d", "subdir": "1d", "start": "2026-05-10", "end": "2026-06-10", "note": "1d red->blue (6/3破628.22)"},
    {"symbol": "BTCUSDT", "timeframe": "15m", "subdir": "15m", "start": "2026-06-01", "end": "2026-06-10", "note": "15m red->blue"},
    {"symbol": "ETHUSDT", "timeframe": "15m", "subdir": "15m", "start": "2026-06-01", "end": "2026-06-10", "note": "15m red->blue"},
    {"symbol": "TRUMPUSDT", "timeframe": "15m", "subdir": "15m", "start": "2026-06-01", "end": "2026-06-10", "note": "15m red->blue"},
]


TAIL_ROWS = {"1d": 1095, "1h": 2400, "15m": 960}


def load_csv(data_dir: Path, symbol: str, subdir: str, *, tail: int) -> pd.DataFrame:
    candidates = [data_dir / subdir / f"{symbol}.csv"]
    if subdir == "1d":
        candidates.insert(0, data_dir / "overseas_1d" / f"{symbol}.csv")
    path = next((p for p in candidates if p.exists()), None)
    if path is None:
        raise FileNotFoundError(candidates[0])
    df = pd.read_csv(path)
    df.columns = [str(c).strip().lower() for c in df.columns]
    if "date" not in df.columns and "timestamp" in df.columns:
        df = df.rename(columns={"timestamp": "date"})
    df["date"] = pd.to_datetime(df["date"])
    for col in ("open", "high", "low", "close", "volume"):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    df = df.dropna(subset=["date", "open", "high", "low", "close"]).sort_values("date").reset_index(drop=True)
    if tail > 0 and len(df) > tail:
        df = df.tail(tail).reset_index(drop=True)
    return df


def camp_at(os_df: pd.DataFrame, day: str) -> int | None:
    ts = pd.Timestamp(day)
    m = pd.to_datetime(os_df["date"]).dt.normalize() == ts.normalize()
    if not m.any():
        return None
    return int(os_df.loc[m].iloc[-1].get("camp", 0) or 0)


def plot_one(spec: dict, data_dir: Path, out_dir: Path) -> dict:
    tail = TAIL_ROWS.get(spec["timeframe"], 960)
    raw = load_csv(data_dir, spec["symbol"], spec["subdir"], tail=tail)
    os_df, engine = build_os_detail_frame(raw, gap=3)
    start_ts = pd.to_datetime(spec["start"])
    end_ts = pd.to_datetime(spec["end"])
    mask = (pd.to_datetime(os_df["date"]) >= start_ts) & (pd.to_datetime(os_df["date"]) <= end_ts)
    window = os_df[mask].copy()
    if window.empty:
        raise ValueError(f"empty window for {spec['symbol']}")
    start_idx = int(window.index.min())
    end_idx = int(window.index.max())

    set_chinese_font()
    fig_w = 22 if spec["timeframe"] == "15m" else 18
    fig, ax = plt.subplots(figsize=(fig_w, 9), dpi=140)
    draw_camp_background(ax, window)
    draw_candles(ax, window)
    lo = start_idx
    for node in engine.hardened_nodes:
        if start_idx - 20 <= node.point_idx < start_idx:
            lo = min(lo, node.point_idx)
    draw_hardened_line(ax, os_df, engine.hardened_nodes, lo, end_idx)
    draw_identity_labels(
        ax, os_df, engine.identity_nodes, engine.hardened_nodes,
        os_df.iloc[end_idx], engine.turns, start_idx, end_idx,
    )
    draw_turn_marks(ax, os_df, engine.turns, start_idx, end_idx)
    add_camp_legend(ax)

    last_camp = int(window.iloc[-1].get("camp", 0) or 0)
    camp_name = {1: "红", -1: "蓝", 0: "中性"}.get(last_camp, str(last_camp))
    ax.set_title(
        f"{spec['symbol']} {spec['timeframe']} N04 spot-check | {spec['note']} | 末K camp={camp_name}",
        fontsize=11,
    )
    ax.set_ylabel("Price")
    ax.grid(True, linestyle=":", alpha=0.25)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%m-%d %H:%M" if spec["timeframe"] != "1d" else "%Y-%m-%d"))
    fig.autofmt_xdate()
    fig.tight_layout()

    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{spec['symbol']}_{spec['timeframe']}_n04_spotcheck.png"
    fig.savefig(out_path)
    plt.close(fig)

    turns_in_window = [
        t for t in engine.turns if start_idx <= t.idx <= end_idx and t.turn in ("RED_TO_BLUE", "BLUE_TO_RED")
    ]
    return {
        "symbol": spec["symbol"],
        "timeframe": spec["timeframe"],
        "note": spec["note"],
        "png": str(out_path),
        "last_camp": last_camp,
        "turns_in_window": len(turns_in_window),
        "last_date": str(window.iloc[-1]["date"])[:19],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", default="data")
    parser.add_argument("--out-dir", default="results/os_state_rebuild/n04_overseas_spotcheck")
    args = parser.parse_args()
    data_dir = Path(args.data_dir)
    out_dir = Path(args.out_dir)

    rows = []
    for spec in SPOTCHECKS:
        row = plot_one(spec, data_dir, out_dir)
        rows.append(row)
        print(f"OK {row['symbol']} {row['timeframe']} last_camp={row['last_camp']} turns={row['turns_in_window']} -> {row['png']}")

    md_lines = [
        "# N04 海外 camp_changed spot-check（2026-06-10）",
        "",
        "| symbol | tf | note | 末K camp | 窗口内转势 | png |",
        "|---|---|---|---:|---:|---|",
    ]
    for r in rows:
        camp = {1: "红", -1: "蓝", 0: "中性"}.get(r["last_camp"], r["last_camp"])
        md_lines.append(
            f"| {r['symbol']} | {r['timeframe']} | {r['note']} | {camp} | {r['turns_in_window']} | `{Path(r['png']).name}` |"
        )
    (out_dir / "spotcheck_summary.md").write_text("\n".join(md_lines) + "\n", encoding="utf-8")
    print(f"summary={out_dir / 'spotcheck_summary.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
