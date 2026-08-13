#!/usr/bin/env python3
"""D1 camp sandbox + radar trigger overlay for new10 symbols awaiting first fill."""
from __future__ import annotations

import argparse
import json
import sys
from argparse import Namespace
from pathlib import Path

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
for p in (SRC, ROOT / "packages" / "fengji_core", ROOT / "scripts"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from audit_crypto_camp_sandbox_review import load_d1, pick_csv  # noqa: E402
from backtest_ds07 import build_os_detail_frame
from fengji_total_radar import RadarRow, analyze_symbol
from plot_fengji_structure import (
    add_camp_legend,
    draw_camp_background,
    draw_candles,
    draw_hardened_line,
    draw_identity_labels,
    draw_turn_marks,
    set_chinese_font,
)

DEFAULT_SYMBOLS = ("ATHUSDT", "WLDUSDT")
def load_overseas_radar_rows(path: Path, symbol: str) -> list[RadarRow]:
    if not path.exists():
        return []
    raw = json.loads(path.read_text(encoding="utf-8"))
    items = raw if isinstance(raw, list) else (raw.get("items") or raw.get("signals") or [])
    rows: list[RadarRow] = []
    for item in items:
        if str(item.get("symbol", "")).upper() != symbol.upper():
            continue
        rows.append(
            RadarRow(
                symbol=symbol,
                strategy_id=str(item.get("strategy_id", "")),
                timeframe=str(item.get("timeframe", "D1")),
                side=str(item.get("side", "")),
                status=str(item.get("status", "")),
                setup=str(item.get("setup", "")),
                current_price=float(item.get("current_price", 0) or 0),
                trigger_price=float(item.get("trigger_price", 0) or 0),
                distance_pct=float(item.get("distance_pct", 0) or 0),
                stop_price=item.get("stop_price"),
                os_camp=str(item.get("os_camp", "")),
                latest_time=str(item.get("latest_time", "")),
                score=float(item.get("score", 0) or 0),
                reason=str(item.get("reason", "")),
                setup_key=str(item.get("setup_key", "")),
            )
        )
    return [r for r in rows if r.status in ("PENDING", "CONFIRM_ON_CLOSE", "READY_TRIGGERED", "ACTIVE")]


SIDE_COLOR = {"long": "#22c55e", "short": "#ef4444"}


def radar_args(data_dir: Path, os_state_dir: str) -> Namespace:
    return Namespace(
        data_dir=str(data_dir),
        symbols="",
        out_dir="runtime/fengji_radar",
        atr_window=14,
        gap=3,
        top_n=80,
        daily_tail=1095,
        h1_tail=2400,
        m15_tail=960,
        os_state_dir=os_state_dir,
        extreme_atr_tol=0.80,
        market="crypto",
    )


def plot_symbol(symbol: str, csv_path: Path, radar_rows: list[RadarRow], out_dir: Path, *, lookback_days: int) -> dict:
    raw = load_d1(csv_path)
    os_df, engine = build_os_detail_frame(raw, gap=3)
    last = os_df.iloc[-1]
    end_ts = pd.to_datetime(last["date"])
    start_ts = end_ts - pd.Timedelta(days=lookback_days)
    mask = (pd.to_datetime(os_df["date"]) >= start_ts) & (pd.to_datetime(os_df["date"]) <= end_ts)
    window = os_df[mask].copy()
    if window.empty:
        raise ValueError(f"empty window for {symbol}")
    start_idx = int(window.index.min())
    end_idx = int(window.index.max())

    set_chinese_font()
    fig, ax = plt.subplots(figsize=(18, 9), dpi=140)
    draw_camp_background(ax, window)
    draw_candles(ax, window)
    lo = start_idx
    for node in engine.hardened_nodes:
        if start_idx - 30 <= node.point_idx < start_idx:
            lo = min(lo, node.point_idx)
    draw_hardened_line(ax, os_df, engine.hardened_nodes, lo, end_idx)
    draw_identity_labels(
        ax, os_df, engine.identity_nodes, engine.hardened_nodes,
        os_df.iloc[end_idx], engine.turns, start_idx, end_idx,
    )
    draw_turn_marks(ax, os_df, engine.turns, start_idx, end_idx)

    labels: list[str] = []
    for row in radar_rows:
        color = SIDE_COLOR.get(str(row.side).lower(), "#94a3b8")
        ax.axhline(float(row.trigger_price), color=color, linestyle="--", linewidth=1.2, alpha=0.85)
        labels.append(f"{row.strategy_id} {row.side} {row.status} @ {row.trigger_price:g}")

    add_camp_legend(ax)
    camp = int(last.get("camp", 0) or 0)
    camp_name = {1: "红", -1: "蓝", 0: "中性"}.get(camp, str(camp))
    ax.set_title(
        f"{symbol} D1 雷达预览 | 末K {str(last['date'])[:10]} | camp={camp_name} | "
        f"雷达 {len(radar_rows)} 条",
        fontsize=11,
    )
    if labels:
        ax.text(
            0.01, 0.02, "\n".join(labels[:8]),
            transform=ax.transAxes, fontsize=8, va="bottom", ha="left",
            bbox=dict(boxstyle="round", facecolor="white", alpha=0.75),
        )
    ax.set_ylabel("Price")
    ax.grid(True, linestyle=":", alpha=0.25)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m-%d"))
    fig.autofmt_xdate()
    fig.tight_layout()

    out_dir.mkdir(parents=True, exist_ok=True)
    png = out_dir / f"{symbol}_D1_radar_preview.png"
    fig.savefig(png)
    plt.close(fig)

    return {
        "symbol": symbol,
        "png": str(png),
        "last_date": str(last["date"])[:10],
        "camp": camp,
        "close": float(last["close"]),
        "radar_rows": [
            {
                "strategy_id": r.strategy_id,
                "side": r.side,
                "status": r.status,
                "trigger_price": r.trigger_price,
                "timeframe": r.timeframe,
            }
            for r in radar_rows
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", default=str(ROOT / "data"))
    parser.add_argument("--symbols", default=",".join(DEFAULT_SYMBOLS))
    parser.add_argument("--lookback-days", type=int, default=120)
    parser.add_argument("--out-dir", default=str(ROOT / "results" / "new10_radar_preview_20260621"))
    parser.add_argument("--os-state-dir", default=str(ROOT / "runtime" / "fengji_os_state"))
    parser.add_argument("--overseas-radar-json", default="", help="Fallback radar.json when local scan empty")
    args = parser.parse_args()

    data_dir = Path(args.data_dir)
    out_dir = Path(args.out_dir)
    rargs = radar_args(data_dir, args.os_state_dir)
    overseas_radar = Path(args.overseas_radar_json) if args.overseas_radar_json else None
    symbols = [s.strip().upper() for s in args.symbols.split(",") if s.strip()]
    results: list[dict] = []

    for symbol in symbols:
        csv_path = pick_csv(data_dir, symbol)
        rows = analyze_symbol(data_dir, symbol, rargs)
        rows = [r for r in rows if r.status in ("PENDING", "CONFIRM_ON_CLOSE", "READY_TRIGGERED", "ACTIVE")]
        if not rows and overseas_radar is not None:
            rows = load_overseas_radar_rows(overseas_radar, symbol)
        results.append(plot_symbol(symbol, csv_path, rows, out_dir, lookback_days=args.lookback_days))

    report = {"symbols": results, "lookback_days": args.lookback_days}
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = ["# new10 雷达预览（待首笔 fill）", "", f"生成：{pd.Timestamp.now():%Y-%m-%d %H:%M}", ""]
    for item in results:
        lines.append(f"## {item['symbol']}")
        lines.append(f"- 末K：{item['last_date']} · camp={item['camp']} · close={item['close']}")
        lines.append(f"- 图：`{Path(item['png']).name}`")
        for r in item["radar_rows"]:
            lines.append(f"  - {r['strategy_id']} {r['side']} {r['status']} trigger={r['trigger_price']}")
        lines.append("")
    (out_dir / "SUMMARY.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"saved {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
