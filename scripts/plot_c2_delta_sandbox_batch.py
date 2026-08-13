#!/usr/bin/env python3
"""C2 delta 沙盒抽查：对跟进报告列出的高 |delta| 品种出 DS01 审计图。"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import timedelta
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "packages" / "fengji_core"))

from backtest_ds01 import DS01BacktestConfig, run_ds01_backtest  # noqa: E402
from quant.data import load_ohlcv_for_engine  # noqa: E402
from quant.futures_specs import get_futures_spec  # noqa: E402

PLOT = ROOT / "scripts" / "plot_ds01_audit_sandbox.py"
OUT = ROOT / "results" / "c2_sandbox_samples"
C2_JSON = {
    "FUTURES": ROOT / "results" / "c2_ds01_s1_compare_futures.json",
    "CRYPTO": ROOT / "results" / "c2_ds01_s1_compare_crypto.json",
}

TARGETS = [
    # market, csv_symbol, display_symbol, data_subdir
    ("futures", "M", "豆粕", "futures/1d"),
    ("futures", "SR", "白糖", "futures/1d"),
    ("futures", "V", "PVC", "futures/1d"),
    ("crypto", "APTUSDT", "APTUSDT", "crypto/1d"),
    ("crypto", "RENDERUSDT", "RENDERUSDT", "crypto/1d"),
]


def c2_delta(market: str, display: str) -> str:
    path = C2_JSON.get(market.upper())
    if not path or not path.exists():
        return "n/a"
    data = json.loads(path.read_text(encoding="utf-8"))
    for item in data.get("items", []):
        if str(item.get("symbol")) == display:
            b, r, d = item.get("baseline_ds01"), item.get("rerun_ds01"), item.get("delta")
            return f"baseline={b} rerun={r} delta={d}"
    return "n/a"


def pick_trade(trades: pd.DataFrame) -> pd.Series | None:
    if trades.empty:
        return None
    closed = trades[trades.get("exit_reason", pd.Series(dtype=str)).astype(str) != "open"].copy()
    if closed.empty:
        closed = trades.copy()
    closed["entry_date"] = pd.to_datetime(closed["entry_date"])
    recent = closed[closed["entry_date"] >= pd.Timestamp("2024-01-01")]
    pool = recent if not recent.empty else closed
    return pool.sort_values("entry_date").iloc[-1]


def run_backtest(market: str, csv_path: Path) -> pd.DataFrame:
    spec = get_futures_spec(csv_path) if market == "futures" else None
    config = DS01BacktestConfig(
        futures_mode=market == "futures",
        spec=spec,
        gap=3,
        atr_window=14,
    )
    df = load_ohlcv_for_engine(csv_path, config.atr_window)
    return run_ds01_backtest(df, config)["trades"]


def plot_one(
    *,
    market: str,
    csv_symbol: str,
    display: str,
    data_root: Path,
    skip_existing: bool,
) -> dict:
    csv_path = data_root / f"{csv_symbol}.csv"
    out = OUT / f"{display.replace('/', '_')}_c2_ds01_sandbox.png"
    if skip_existing and out.exists():
        return {"symbol": display, "status": "skip", "out": str(out)}

    if not csv_path.exists():
        return {"symbol": display, "status": "error", "error": f"missing {csv_path}"}

    trades = run_backtest(market, csv_path)
    row = pick_trade(trades)
    if row is None:
        return {"symbol": display, "status": "error", "error": "no DS01 trades"}

    side = str(row["direction"])
    entry_date = pd.Timestamp(row["entry_date"]).strftime("%Y-%m-%d")
    fill_price = float(row["avg_entry_price"])
    camp = int(row.get("camp_signal") or 0)
    ts = pd.Timestamp(entry_date)
    start = str((ts - timedelta(days=45)).date())
    end = str((ts + timedelta(days=21)).date())
    verdict = (
        f"C2 {c2_delta(market.upper(), display)} | camp_signal={camp} | "
        f"rerun sample {entry_date} {side} @ {fill_price:.4g}"
    )

    cmd = [
        sys.executable,
        str(PLOT),
        "--csv",
        str(csv_path),
        "--market",
        market,
        "--symbol",
        display,
        "--side",
        side,
        "--entry-date",
        entry_date,
        "--fill-price",
        str(fill_price),
        "--start",
        start,
        "--end",
        end,
        "--order-tag",
        "C2-delta-spot",
        "--verdict",
        verdict,
        "--out",
        str(out),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, cwd=str(ROOT))
    if proc.returncode != 0:
        return {
            "symbol": display,
            "status": "error",
            "error": (proc.stderr or proc.stdout or "plot failed")[-500:],
        }
    return {
        "symbol": display,
        "status": "ok",
        "out": str(out),
        "entry_date": entry_date,
        "side": side,
        "fill_price": fill_price,
        "camp_signal": camp,
        "rerun_trades": int(len(trades)),
        "c2": c2_delta(market.upper(), display),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="C2 delta DS01 sandbox spot-check batch.")
    parser.add_argument("--data-root", default=str(ROOT / "data" / "c2_sandbox_staging"))
    parser.add_argument("--skip-existing", action="store_true")
    args = parser.parse_args()
    data_root = Path(args.data_root)

    results: list[dict] = []
    for market, csv_sym, display, sub in TARGETS:
        root = data_root / sub
        results.append(
            plot_one(
                market=market,
                csv_symbol=csv_sym,
                display=display,
                data_root=root,
                skip_existing=args.skip_existing,
            )
        )

    OUT.mkdir(parents=True, exist_ok=True)
    manifest = OUT / "c2_delta_sandbox_manifest.json"
    manifest.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")

    ok = sum(1 for r in results if r.get("status") == "ok")
    fail = sum(1 for r in results if r.get("status") == "error")
    print(f"C2 sandbox batch ok={ok} fail={fail} manifest={manifest}")
    for row in results:
        print(f"  {row.get('symbol')}: {row.get('status')} {row.get('out', row.get('error', ''))}")
    return 1 if fail else 0


if __name__ == "__main__":
    raise SystemExit(main())
