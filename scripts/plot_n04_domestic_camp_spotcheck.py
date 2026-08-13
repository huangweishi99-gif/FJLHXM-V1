#!/usr/bin/env python3
"""Spot-check sandbox charts for N04 domestic camp_changed symbols."""
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
from fengji_core.data import load_tq_futures_kline_csv, valid_futures_price_mask
from plot_fengji_structure import (
    add_camp_legend,
    draw_camp_background,
    draw_candles,
    draw_hardened_line,
    draw_identity_labels,
    draw_turn_marks,
    set_chinese_font,
)

# N04 rebuild domestic camp_changed (2026-06-10)
SPOTCHECKS = [
    {"symbol": "EB", "timeframe": "1h", "subdir": "1h", "start": "2026-05-20", "end": "2026-06-10", "note": "1h red->blue", "expected_after": "blue"},
    {"symbol": "FU", "timeframe": "1h", "subdir": "1h", "start": "2026-05-20", "end": "2026-06-10", "note": "1h red->blue", "expected_after": "blue"},
    {"symbol": "RB", "timeframe": "1d", "subdir": "1d", "start": "2026-05-25", "end": "2026-06-10", "note": "1d blue->red (DS01 invalid)", "expected_after": "red"},
    {"symbol": "RU", "timeframe": "15m", "subdir": "15m", "start": "2026-06-01", "end": "2026-06-10", "note": "15m red->blue", "expected_after": "blue"},
    {"symbol": "SA", "timeframe": "15m", "subdir": "15m", "start": "2026-06-01", "end": "2026-06-10", "note": "15m blue->red", "expected_after": "red"},
    {"symbol": "SF", "timeframe": "15m", "subdir": "15m", "start": "2026-06-01", "end": "2026-06-10", "note": "15m blue->red", "expected_after": "red"},
    {"symbol": "UR", "timeframe": "1h", "subdir": "1h", "start": "2026-05-20", "end": "2026-06-10", "note": "1h red->blue", "expected_after": "blue"},
]

TAIL_ROWS = {"1d": 1095, "1h": 2400, "15m": 960}
CAMP_NAME = {1: "红", -1: "蓝", 0: "中性"}
EXPECTED_CAMP = {"red": 1, "blue": -1}


def load_futures_csv(data_dir: Path, symbol: str, subdir: str, *, tail: int) -> pd.DataFrame:
    path = data_dir / subdir / f"{symbol}.csv"
    if not path.exists():
        raise FileNotFoundError(path)
    df = load_tq_futures_kline_csv(path)
    df = df[(df["date"] >= pd.Timestamp("2020-01-01")) & valid_futures_price_mask(df)]
    df = df.dropna(subset=["date", "open", "high", "low", "close"]).sort_values("date").reset_index(drop=True)
    if tail > 0 and len(df) > tail:
        df = df.tail(tail).reset_index(drop=True)
    return df


def plot_one(spec: dict, data_dir: Path, out_dir: Path) -> dict:
    tail = TAIL_ROWS.get(spec["timeframe"], 960)
    raw = load_futures_csv(data_dir, spec["symbol"], spec["subdir"], tail=tail)
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
    camp_name = CAMP_NAME.get(last_camp, str(last_camp))
    expected = EXPECTED_CAMP.get(spec["expected_after"])
    match = expected is not None and last_camp == expected
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
        "expected_after": spec["expected_after"],
        "png": str(out_path),
        "last_camp": last_camp,
        "match_expected": match,
        "turns_in_window": len(turns_in_window),
        "last_date": str(window.iloc[-1]["date"])[:19],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", default="data")
    parser.add_argument("--out-dir", default="results/os_state_rebuild/n04_domestic_spotcheck")
    args = parser.parse_args()
    data_dir = Path(args.data_dir)
    out_dir = Path(args.out_dir)

    rows = []
    for spec in SPOTCHECKS:
        row = plot_one(spec, data_dir, out_dir)
        rows.append(row)
        ok = "OK" if row["match_expected"] else "WARN"
        print(
            f"{ok} {row['symbol']} {row['timeframe']} last_camp={row['last_camp']} "
            f"expected={row['expected_after']} turns={row['turns_in_window']} -> {row['png']}"
        )

    md_lines = [
        "# N04 国内 camp_changed spot-check（2026-06-10）",
        "",
        "数据源：国内服务器天勤 CSV + 修复后 `os_engine` 重算。",
        "",
        "| symbol | tf | note | 末K camp | 期望 after | 一致 | 窗口内转势 | png |",
        "|---|---|---|---:|---|:---:|---:|---|",
    ]
    for r in rows:
        camp = CAMP_NAME.get(r["last_camp"], r["last_camp"])
        match = "✓" if r["match_expected"] else "△"
        md_lines.append(
            f"| {r['symbol']} | {r['timeframe']} | {r['note']} | {camp} | {r['expected_after']} | {match} | {r['turns_in_window']} | `{Path(r['png']).name}` |"
        )
    md_lines.extend([
        "",
        "## RB 关联",
        "",
        "- `RB_1d` blue→red 后，DS01 空单 `RBUSDT-DS01-D1-short-5b4e7fd42ee68111` 已 ack + monitor repair。",
    ])
    (out_dir / "spotcheck_summary.md").write_text("\n".join(md_lines) + "\n", encoding="utf-8")
    print(f"summary={out_dir / 'spotcheck_summary.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
