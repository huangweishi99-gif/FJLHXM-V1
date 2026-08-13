#!/usr/bin/env python3
"""Wave 4 S2 · DS01 D1 审计沙盒批量（四市场验收品种集）。

默认品种：D4c smoke（000021/沪金/SOL/NVDA）+ C2 delta 抽查（豆粕/白糖/APT）+ P0（AG/RB/BNB）。
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "packages" / "fengji_core"))
sys.path.insert(0, str(ROOT / "services"))

from api.main import resolve_csv  # noqa: E402
from backtest_ds01 import DS01BacktestConfig, run_ds01_backtest  # noqa: E402
from quant.data import load_ohlcv_for_engine  # noqa: E402
from quant.futures_specs import get_futures_spec  # noqa: E402

PLOT = ROOT / "scripts" / "plot_ds01_audit_sandbox.py"

# market_tag, symbol, plot_market (plot_ds01_audit_sandbox --market)
DEFAULT_TARGETS: list[tuple[str, str, str]] = [
    ("A_STOCK", "000021", "crypto"),
    ("FUTURES", "沪金", "futures"),
    ("FUTURES", "AG", "futures"),
    ("FUTURES", "RB", "futures"),
    ("FUTURES", "M", "futures"),
    ("FUTURES", "SR", "futures"),
    ("CRYPTO", "SOLUSDT", "crypto"),
    ("CRYPTO", "BNBUSDT", "crypto"),
    ("CRYPTO", "APTUSDT", "crypto"),
    ("US_STOCK", "NVDA", "crypto"),
]


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
    futures_mode = market == "FUTURES"
    spec = get_futures_spec(csv_path) if futures_mode else None
    config = DS01BacktestConfig(
        futures_mode=futures_mode,
        spec=spec,
        gap=3,
        atr_window=14,
    )
    df = load_ohlcv_for_engine(csv_path, config.atr_window)
    return run_ds01_backtest(df, config)["trades"]


def plot_one(
    *,
    market: str,
    symbol: str,
    plot_market: str,
    out_dir: Path,
    skip_existing: bool,
) -> dict:
    safe = symbol.replace("/", "_").replace(" ", "")
    out = out_dir / f"{market}_{safe}_ds01_sandbox.png"
    if skip_existing and out.exists():
        return {"market": market, "symbol": symbol, "status": "skip", "out": str(out)}

    try:
        csv_path = resolve_csv(symbol, market)
    except FileNotFoundError as exc:
        return {"market": market, "symbol": symbol, "status": "error", "error": str(exc)}

    try:
        trades = run_backtest(market, csv_path)
    except Exception as exc:
        return {"market": market, "symbol": symbol, "status": "error", "error": f"backtest: {exc}"}

    row = pick_trade(trades)
    if row is None:
        return {"market": market, "symbol": symbol, "status": "error", "error": "no DS01 trades"}

    side = str(row["direction"])
    entry_date = pd.Timestamp(row["entry_date"]).strftime("%Y-%m-%d")
    fill_price = float(row["avg_entry_price"])
    camp = int(row.get("camp_signal") or 0)
    expected = -1 if side == "short" else 1
    camp_ok = camp == expected
    ts = pd.Timestamp(entry_date)
    start = str((ts - timedelta(days=60)).date())
    end = str((ts + timedelta(days=30)).date())
    verdict = (
        f"S2 {market}/{symbol} | camp_signal={camp} expected={expected} | "
        f"{'camp_OK' if camp_ok else 'audit_invalid_camp_mismatch'} | "
        f"{entry_date} {side} @ {fill_price:.6g}"
    )

    cmd = [
        sys.executable,
        str(PLOT),
        "--csv",
        str(csv_path),
        "--market",
        plot_market,
        "--symbol",
        symbol,
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
        f"S2-{market}",
        "--verdict",
        verdict,
        "--out",
        str(out),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, cwd=str(ROOT))
    if proc.returncode != 0:
        return {
            "market": market,
            "symbol": symbol,
            "status": "error",
            "error": (proc.stderr or proc.stdout or "plot failed")[-800:],
        }
    return {
        "market": market,
        "symbol": symbol,
        "status": "ok",
        "out": str(out),
        "csv": str(csv_path),
        "entry_date": entry_date,
        "side": side,
        "fill_price": fill_price,
        "camp_signal": camp,
        "camp_ok": camp_ok,
        "trade_count": int(len(trades)),
        "verdict": verdict,
    }


def write_report(out_dir: Path, results: list[dict], stamp: str) -> Path:
    ok = [r for r in results if r.get("status") == "ok"]
    fail = [r for r in results if r.get("status") == "error"]
    camp_bad = [r for r in ok if not r.get("camp_ok")]
    lines = [
        f"# Wave 4 S2 · DS01 沙盒批量验收（{stamp}）",
        "",
        "> OS 结构 + 阵营底色 + 硬化峰极线 + DS01 信号棍/入场标注。",
        "> **不修改** OS/定式规则；仅审计最近一笔 DS01 成交是否合理。",
        "",
        f"- 成功出图：**{len(ok)}/{len(results)}**",
        f"- camp 对齐：**{len(ok) - len(camp_bad)}/{len(ok)}**",
        f"- camp 不匹配（audit_invalid 候选）：**{len(camp_bad)}**",
        "",
        "## 汇总",
        "",
        "| 市场 | 品种 | 状态 | 入场 | 方向 | camp | 对齐 | 图 |",
        "|------|------|------|------|------|------|------|-----|",
    ]
    for r in results:
        if r.get("status") == "ok":
            align = "✅" if r.get("camp_ok") else "❌"
            lines.append(
                f"| {r['market']} | {r['symbol']} | ok | {r['entry_date']} | {r['side']} | "
                f"{r['camp_signal']} | {align} | `{Path(r['out']).name}` |"
            )
        elif r.get("status") == "skip":
            lines.append(f"| {r['market']} | {r['symbol']} | skip | | | | | `{Path(r['out']).name}` |")
        else:
            lines.append(f"| {r['market']} | {r['symbol']} | error | | | | | {r.get('error', '')[:60]} |")

    if camp_bad:
        lines.extend(["", "## camp 不匹配明细（需人工看图裁定）", ""])
        for r in camp_bad:
            lines.append(f"- **{r['market']}/{r['symbol']}** {r['verdict']}")

    lines.extend(
        [
            "",
            "## 复跑",
            "",
            "```powershell",
            "python scripts/run_s2_ds01_sandbox_batch.py",
            "```",
            "",
        ]
    )
    report = out_dir / f"s2_ds01_sandbox_report_{stamp.replace('-', '')}.md"
    report.write_text("\n".join(lines), encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="S2 DS01 audit sandbox batch (4 markets).")
    parser.add_argument(
        "--out-dir",
        default="",
        help="Output directory (default: results/s2_ds01_sandbox_YYYYMMDD)",
    )
    parser.add_argument("--skip-existing", action="store_true")
    args = parser.parse_args()

    stamp = datetime.now().strftime("%Y-%m-%d")
    out_dir = Path(args.out_dir) if args.out_dir else ROOT / "results" / f"s2_ds01_sandbox_{stamp.replace('-', '')}"
    out_dir.mkdir(parents=True, exist_ok=True)

    results: list[dict] = []
    for market, symbol, plot_market in DEFAULT_TARGETS:
        results.append(
            plot_one(
                market=market,
                symbol=symbol,
                plot_market=plot_market,
                out_dir=out_dir,
                skip_existing=args.skip_existing,
            )
        )

    manifest = out_dir / "s2_ds01_sandbox_manifest.json"
    manifest.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    report = write_report(out_dir, results, stamp)

    ok = sum(1 for r in results if r.get("status") == "ok")
    fail = sum(1 for r in results if r.get("status") == "error")
    camp_bad = sum(1 for r in results if r.get("status") == "ok" and not r.get("camp_ok"))
    print(f"S2 sandbox ok={ok} fail={fail} camp_mismatch={camp_bad}")
    print(f"manifest={manifest}")
    print(f"report={report}")
    for row in results:
        tag = row.get("status")
        extra = row.get("out") or row.get("error", "")
        print(f"  {row.get('market')}/{row.get('symbol')}: {tag} {extra}")
    return 1 if fail else 0


if __name__ == "__main__":
    raise SystemExit(main())
