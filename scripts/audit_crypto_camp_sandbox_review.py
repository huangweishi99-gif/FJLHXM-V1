#!/usr/bin/env python3
"""D1 camp sandbox charts for crypto symbols (visual review, no trade overlay)."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
for p in (SRC, ROOT / "packages" / "fengji_core"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

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

DEFAULT = ("DOGEUSDT", "LTCUSDT", "RENDERUSDT", "IOUSDT")
D1_TAIL = 1095


def pick_csv(data_dir: Path, symbol: str) -> Path:
    base = symbol.replace("USDT", "")
    cands = [
        data_dir / "overseas_1d" / f"{symbol}.csv",
        data_dir / "1d" / f"{symbol}.csv",
        data_dir / "crypto_okx" / f"{base}-USDT_1D_1825d.csv",
    ]
    found = [p for p in cands if p.is_file()]
    if not found:
        raise FileNotFoundError(f"no D1 csv for {symbol}")
    return max(found, key=lambda p: pd.read_csv(p).shape[0])


def load_d1(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    df.columns = [str(c).strip().lower() for c in df.columns]
    if "date" not in df.columns and "timestamp" in df.columns:
        df = df.rename(columns={"timestamp": "date"})
    df["date"] = pd.to_datetime(df["date"])
    for col in ("open", "high", "low", "close", "volume"):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    df = df.dropna(subset=["date", "open", "high", "low", "close"]).sort_values("date").reset_index(drop=True)
    if len(df) > D1_TAIL:
        df = df.tail(D1_TAIL).reset_index(drop=True)
    return df


def plot_symbol(symbol: str, csv_path: Path, out_dir: Path, *, lookback_days: int) -> dict:
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
    add_camp_legend(ax)

    camp = int(last.get("camp", 0) or 0)
    camp_name = {1: "红", -1: "蓝", 0: "中性"}.get(camp, str(camp))
    ah = last.get("active_high")
    al = last.get("active_low")
    close = float(last["close"])
    ax.set_title(
        f"{symbol} D1 阵营沙盒 | 末K {str(last['date'])[:10]} | camp={camp_name} | "
        f"close={close} | active_high={ah} active_low={al}",
        fontsize=11,
    )
    ax.set_ylabel("Price")
    ax.grid(True, linestyle=":", alpha=0.25)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m-%d"))
    fig.autofmt_xdate()
    fig.tight_layout()

    out_dir.mkdir(parents=True, exist_ok=True)
    png = out_dir / f"{symbol}_D1_camp_review.png"
    fig.savefig(png)
    plt.close(fig)

    turns = [t for t in engine.turns if start_idx <= t.idx <= end_idx and t.turn in ("RED_TO_BLUE", "BLUE_TO_RED")]
    return {
        "symbol": symbol,
        "csv": str(csv_path),
        "png": str(png),
        "last_date": str(last["date"])[:10],
        "camp": camp,
        "camp_label": {1: "red", -1: "blue", 0: "neutral"}.get(camp, str(camp)),
        "close": close,
        "active_high": ah,
        "active_low": al,
        "prev_camp": int(os_df.iloc[-2].get("camp", 0) or 0) if len(os_df) > 1 else camp,
        "turns_in_window": len(turns),
        "lookback_days": lookback_days,
        "verdict": "ok",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", default=str(ROOT / "data"))
    parser.add_argument("--symbols", default=",".join(DEFAULT))
    parser.add_argument("--lookback-days", type=int, default=120)
    parser.add_argument("--out-dir", default=str(ROOT / "results" / "crypto_camp_sandbox_review_20260618"))
    args = parser.parse_args()
    data_dir = Path(args.data_dir)
    out_dir = Path(args.out_dir)
    symbols = [s.strip().upper() for s in args.symbols.split(",") if s.strip()]

    rows = []
    for sym in symbols:
        try:
            csv_path = pick_csv(data_dir, sym)
            row = plot_symbol(sym, csv_path, out_dir, lookback_days=args.lookback_days)
            rows.append(row)
            print(f"OK {sym} camp={row['camp_label']} -> {row['png']}")
        except Exception as exc:
            rows.append({"symbol": sym, "verdict": "error", "error": str(exc)})
            print(f"FAIL {sym}: {exc}", file=sys.stderr)

    payload = {"symbols": rows}
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "report.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "# Crypto D1 阵营沙盒目视图",
        "",
        f"回看 **{args.lookback_days}** 日 · 数据源 `data/overseas_1d/`",
        "",
        "| 品种 | 末K | camp | close | active_high | active_low | 窗口转势 | 图 |",
        "|---|---|---:|---:|---:|---:|---:|---|",
    ]
    for r in rows:
        if r.get("verdict") == "error":
            lines.append(f"| {r['symbol']} | — | error | — | — | — | — | — |")
        else:
            lines.append(
                f"| {r['symbol']} | {r['last_date']} | **{r['camp_label']}** ({r['camp']}) | "
                f"{r['close']} | {r['active_high']} | {r['active_low']} | {r['turns_in_window']} | "
                f"`{Path(r['png']).name}` |"
            )
    lines += [
        "",
        "## 验收说明",
        "",
        "- 紫线为硬化峰极连线；背景色为 camp 区间",
        "- 末K camp 应与 OS 快照 `results/crypto_camp_snapshot_20260618/` 一致",
        "- 请目视确认：连线、峰极、阵营背景与规则图一致后签字 `USER_SIGNOFF.md`",
        "",
    ]
    (out_dir / "SUMMARY.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"summary={out_dir / 'SUMMARY.md'}")
    return 0 if all(r.get("verdict") == "ok" for r in rows) else 1


if __name__ == "__main__":
    raise SystemExit(main())
