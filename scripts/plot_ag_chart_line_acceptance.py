#!/usr/bin/env python3
"""沪银 AG 峰极连线沙盒验收：OS state + Web segments 对照图。"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "packages" / "fengji_core"), str(ROOT / "services")]

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.patches import Rectangle

from api.main import resolve_csv
from chart_bundle import ChartBundleRequest, _build_stateful_os_overlay, _load_chart_ohlcv, build_chart_bundle
from fengji_core.chart_line import audit_hardened_segments, audit_web_vs_sandbox, iso_date
from plot_fengji_structure import draw_hardened_line, set_chinese_font


def _draw_candles(ax, df: pd.DataFrame) -> None:
    dates = mdates.date2num(pd.to_datetime(df["date"]).dt.to_pydatetime())
    width = 0.4 if len(dates) < 2 else max(float(pd.Series(dates).diff().median()) * 0.55, 0.2)
    for x, (_, row) in zip(dates, df.iterrows()):
        o, h, l, c = float(row["open"]), float(row["high"]), float(row["low"]), float(row["close"])
        color = "#d62728" if c >= o else "#1f77b4"
        body_low = min(o, c)
        ax.vlines(x, l, h, color=color, linewidth=0.7, alpha=0.85)
        ax.add_patch(
            Rectangle((x - width / 2, body_low), width, max(abs(c - o), 1e-9), facecolor=color, edgecolor=color, alpha=0.72)
        )


def _draw_segments(ax, segments: list[dict], *, style: str, color: str, label: str, lw: float, ls: str) -> None:
    xs: list[float] = []
    ys: list[float] = []
    for seg in segments:
        if style == "solid" and seg.get("style") == "dashed":
            continue
        if style == "dashed" and seg.get("style") != "dashed" and seg.get("kind") != "provisional":
            continue
        t0 = mdates.date2num(pd.to_datetime(seg["t0"]))
        t1 = mdates.date2num(pd.to_datetime(seg["t1"]))
        if not xs:
            xs.extend([t0, t1])
            ys.extend([seg["p0"], seg["p1"]])
        else:
            if xs[-1] != t0 or ys[-1] != seg["p0"]:
                xs.append(t0)
                ys.append(seg["p0"])
            xs.append(t1)
            ys.append(seg["p1"])
    if xs:
        ax.plot(xs, ys, color=color, linewidth=lw, linestyle=ls, marker="o", markersize=3, label=label)


def main() -> int:
    out_dir = ROOT / "results" / "sandbox" / "ag_chart_line_acceptance_20260612"
    out_dir.mkdir(parents=True, exist_ok=True)

    csv_path = resolve_csv("AG", "FUTURES")
    state_dir = ROOT / "runtime" / "fengji_os_state"
    req = ChartBundleRequest(
        csv_path=csv_path,
        strategy_id="DS03",
        years=2,
        futures_mode=True,
        os_state_dir=state_dir,
        os_symbol="AG",
        os_timeframe="1d",
    )
    bundle = build_chart_bundle(req)
    raw = _load_chart_ohlcv(req)
    os_df, engine, meta = _build_stateful_os_overlay(raw, req)

    start = pd.Timestamp("2026-04-01")
    end = pd.Timestamp(os_df["date"].max())
    mask = (pd.to_datetime(os_df["date"]) >= start) & (pd.to_datetime(os_df["date"]) <= end)
    window = os_df[mask].copy()
    start_idx = int(window.index.min())
    end_idx = int(window.index.max())

    bar_dates = {b["t"] for b in bundle["bars"]}
    segs = bundle["hardened_segments"]
    audit = audit_hardened_segments(segs, bar_dates, require_trail=True, last_bar_date=bundle["bars"][-1]["t"])
    sandbox_audit = audit_web_vs_sandbox(engine, os_df, segs, bar_dates, iso_date)

    report = {
        "symbol": "AG",
        "csv": str(csv_path),
        "os_state": meta,
        "bars": len(bundle["bars"]),
        "last_bar": bundle["bars"][-1]["t"],
        "solid_segments": len([s for s in segs if s.get("style", "solid") == "solid"]),
        "dashed_segments": len([s for s in segs if s.get("kind") == "provisional"]),
        "audit_issues": [{"code": i.code, "message": i.message} for i in audit],
        "sandbox_issues": [{"code": i.code, "message": i.message} for i in sandbox_audit],
        "trail_segments": [s for s in segs if s.get("kind") == "provisional"],
        "last_solid_segments": [s for s in segs if s.get("style", "solid") == "solid"][-3:],
        "pass": not audit and not sandbox_audit,
    }
    (out_dir / "ag_chart_line_audit.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    set_chinese_font()
    fig, ax = plt.subplots(figsize=(18, 9), dpi=140)
    _draw_candles(ax, window)
    draw_hardened_line(ax, os_df, engine.hardened_nodes, start_idx, end_idx)
    solid = [s for s in segs if s.get("style", "solid") == "solid" and s.get("kind") != "provisional"]
    dashed = [s for s in segs if s.get("kind") == "provisional"]
    _draw_segments(ax, solid, style="solid", color="#ff9500", label="Web 实线", lw=2.2, ls="-")
    _draw_segments(ax, dashed, style="dashed", color="#0a84ff", label="Web 橡皮筋", lw=2.0, ls="--")
    ax.set_title("沪银(AG) D1 峰极连线验收 | 紫=沙盒 hardened | 橙=Web实线 | 蓝=橡皮筋", fontsize=13)
    ax.set_ylabel("Price")
    ax.grid(True, linestyle=":", alpha=0.28)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m-%d"))
    ax.legend(loc="best", fontsize=9)
    fig.autofmt_xdate()
    fig.tight_layout()
    png = out_dir / "AG_D1_chart_line_acceptance.png"
    fig.savefig(png)
    plt.close(fig)

    print(f"Saved {png}")
    print(f"Saved {out_dir / 'ag_chart_line_audit.json'}")
    print(f"PASS={report['pass']} audit={len(audit)} sandbox={len(sandbox_audit)}")
    return 0 if report["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
