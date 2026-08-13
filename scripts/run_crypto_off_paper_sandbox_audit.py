#!/usr/bin/env python3
"""定式单点沙盒审计：未进海外模拟盘的 crypto 品种 · DS01 + DS03/05/07/08。

只读审计 — 不改 OS/定式/风控/模拟盘配置。
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "packages" / "fengji_core"))
sys.path.insert(0, str(ROOT / "services"))

from api.main import resolve_csv  # noqa: E402
from backtest_ds01 import DS01BacktestConfig, run_ds01_backtest  # noqa: E402
from crypto_ingest import crypto_timeframe_csv_path, ingest_crypto_timeframes  # noqa: E402
from quant.data import load_ohlcv_for_engine  # noqa: E402
from unified_whitelist_engine import UnifiedConfig, run_unified_symbol  # noqa: E402

# 与 src/overseas_paper_monitor.py MONITOR_COINS 对齐（未进模拟盘 = 不在此集合）
PAPER_MONITOR_SYMBOLS = {
    "BTCUSDT",
    "ETHUSDT",
    "SOLUSDT",
    "AVAXUSDT",
    "TRUMPUSDT",
    "RENDERUSDT",
    "IOUSDT",
    "TAOUSDT",
    "DASHUSDT",
    "LTCUSDT",
    "DOGEUSDT",
    "ADAUSDT",
    "APTUSDT",
    "LINKUSDT",
    "BNBUSDT",
    "ZECUSDT",
    "XRPUSDT",
    "HYPEUSDT",
    "ATHUSDT",
    "PEPEUSDT",
    "ARBUSDT",
    "OPUSDT",
    "SUIUSDT",
    "NEARUSDT",
    "INJUSDT",
    "WLDUSDT",
}

# 优先尝试的非模拟盘品种（按流动性/数据可用性）
OFF_PAPER_CANDIDATES = [
    "XRPUSDT",
    "HYPEUSDT",
    "ATHUSDT",
    "PEPEUSDT",
    "ARBUSDT",
    "OPUSDT",
    "SUIUSDT",
    "NEARUSDT",
    "INJUSDT",
    "WLDUSDT",
    "TONUSDT",
    "FILUSDT",
    "DOTUSDT",
    "POLUSDT",
    "FETUSDT",
    "SEIUSDT",
    "TIAUSDT",
    "JUPUSDT",
]

AUDIT_STRATEGIES = ["DS01", "DS03", "DS05", "DS07", "DS08"]
PLOT = ROOT / "scripts" / "plot_ds01_audit_sandbox.py"


def _resolve_or_ingest(symbol: str, *, allow_ingest: bool) -> Path | None:
    sym = symbol.upper()
    try:
        return resolve_csv(sym, "CRYPTO")
    except FileNotFoundError:
        pass
    if not allow_ingest:
        return None
    try:
        ingest_crypto_timeframes(sym, timeframes=["D1", "H1"])
    except Exception as exc:  # noqa: BLE001
        print(f"  ingest_fail {sym}: {exc}")
        return None
    try:
        return resolve_csv(sym, "CRYPTO")
    except FileNotFoundError:
        return None


def select_symbols(*, count: int, allow_ingest: bool, extra: list[str] | None = None) -> list[str]:
    pool = list(dict.fromkeys((extra or []) + OFF_PAPER_CANDIDATES))
    selected: list[str] = []
    for sym in pool:
        if sym.upper() in PAPER_MONITOR_SYMBOLS:
            continue
        if sym.upper() in selected:
            continue
        path = _resolve_or_ingest(sym, allow_ingest=allow_ingest)
        if path is None:
            continue
        selected.append(sym.upper())
        print(f"  selected {sym.upper()} csv={path}")
        if len(selected) >= count:
            break
    return selected


def pick_latest_trade(df: pd.DataFrame, strategy_id: str) -> pd.Series | None:
    if df.empty:
        return None
    sub = df[df["strategy_id"].astype(str).str.upper() == strategy_id.upper()].copy()
    if sub.empty:
        return None
    sub["entry_time"] = pd.to_datetime(sub["entry_time"], errors="coerce")
    recent = sub[sub["entry_time"] >= pd.Timestamp("2024-01-01")]
    pool = recent if not recent.empty else sub
    return pool.sort_values("entry_time").iloc[-1]


def ds01_camp_check(symbol: str, csv_path: Path, entry_date: str, side: str) -> dict[str, Any]:
    config = DS01BacktestConfig(futures_mode=False, gap=3, atr_window=14)
    df = load_ohlcv_for_engine(csv_path, config.atr_window)
    trades = run_ds01_backtest(df, config)["trades"]
    if trades.empty:
        return {"camp_signal": None, "camp_ok": None}
    ed = pd.Timestamp(entry_date)
    hits = trades[pd.to_datetime(trades["entry_date"]).dt.normalize() == ed.normalize()]
    if hits.empty:
        return {"camp_signal": None, "camp_ok": None}
    row = hits.iloc[-1]
    camp = int(row.get("camp_signal") or 0)
    expected = -1 if side == "short" else 1
    return {"camp_signal": camp, "camp_ok": camp == expected}


def plot_trade(
    *,
    symbol: str,
    strategy_id: str,
    side: str,
    entry_date: str,
    fill_price: float,
    csv_path: Path,
    out_path: Path,
    camp_ok: bool | None,
) -> dict[str, Any]:
    ts = pd.Timestamp(entry_date)
    start = str((ts - timedelta(days=60)).date())
    end = str((ts + timedelta(days=30)).date())
    camp_tag = "camp_OK" if camp_ok else ("camp_unknown" if camp_ok is None else "audit_invalid_camp_mismatch")
    verdict = (
        f"OFF-PAPER {symbol} {strategy_id} | {camp_tag} | "
        f"{entry_date} {side} @ {fill_price:.6g} | not_in_paper_monitor"
    )
    cmd = [
        sys.executable,
        str(PLOT),
        "--csv",
        str(csv_path),
        "--market",
        "crypto",
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
        f"{strategy_id}-offpaper",
        "--verdict",
        verdict,
        "--out",
        str(out_path),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, cwd=str(ROOT))
    ok = proc.returncode == 0
    return {
        "ok": ok,
        "out": str(out_path),
        "verdict": verdict,
        "error": "" if ok else (proc.stderr or proc.stdout or "plot failed")[-500:],
    }


def audit_symbol(symbol: str, *, out_dir: Path, allow_ingest: bool) -> dict[str, Any]:
    sym = symbol.upper()
    csv_d1 = _resolve_or_ingest(sym, allow_ingest=allow_ingest)
    if csv_d1 is None:
        return {"symbol": sym, "status": "error", "error": "no D1 csv"}

    sym_dir = out_dir / sym
    sym_dir.mkdir(parents=True, exist_ok=True)
    h1 = crypto_timeframe_csv_path(sym, "H1")
    if not h1.exists() and allow_ingest:
        try:
            ingest_crypto_timeframes(sym, timeframes=["H1"])
        except Exception:
            pass

    config = UnifiedConfig(futures_mode=False, gap=3, atr_window=14)
    try:
        run_unified_symbol(
            sym,
            config,
            daily_csv=csv_d1,
            h1_csv=h1 if h1.exists() else None,
            m15_csv=None,
            strategies=AUDIT_STRATEGIES,
            out_dir=sym_dir / "unified",
        )
    except Exception as exc:  # noqa: BLE001
        return {"symbol": sym, "status": "error", "error": f"unified: {exc}"}

    cand_path = sym_dir / "unified" / "candidate_trades.csv"
    candidates = pd.read_csv(cand_path) if cand_path.exists() else pd.DataFrame()
    charts: list[dict[str, Any]] = []

    for strategy_id in AUDIT_STRATEGIES:
        row = pick_latest_trade(candidates, strategy_id)
        if row is None:
            charts.append({"strategy_id": strategy_id, "status": "no_trade"})
            continue
        side = str(row.get("direction") or "long").lower()
        if side not in {"long", "short"}:
            side = "long" if int(row.get("side") or 1) == 1 else "short"
        entry_time = pd.to_datetime(row["entry_time"], errors="coerce")
        entry_date = entry_time.strftime("%Y-%m-%d") if pd.notna(entry_time) else ""
        fill_price = float(row.get("entry_price") or 0)
        if not entry_date or fill_price <= 0:
            charts.append({"strategy_id": strategy_id, "status": "bad_row"})
            continue

        camp_meta = ds01_camp_check(sym, csv_d1, entry_date, side) if strategy_id == "DS01" else {
            "camp_signal": None,
            "camp_ok": None,
        }
        png = sym_dir / f"{sym}_{strategy_id}_sandbox.png"
        plot_meta = plot_trade(
            symbol=sym,
            strategy_id=strategy_id,
            side=side,
            entry_date=entry_date,
            fill_price=fill_price,
            csv_path=csv_d1,
            out_path=png,
            camp_ok=camp_meta.get("camp_ok"),
        )
        charts.append(
            {
                "strategy_id": strategy_id,
                "status": "ok" if plot_meta["ok"] else "plot_error",
                "entry_date": entry_date,
                "side": side,
                "fill_price": fill_price,
                **camp_meta,
                **plot_meta,
            }
        )

    ds01 = next((c for c in charts if c.get("strategy_id") == "DS01"), {})
    others = [c for c in charts if c.get("strategy_id") != "DS01" and c.get("status") == "ok"]
    status = "ok" if ds01.get("status") == "ok" else "partial" if others else "error"
    return {
        "symbol": sym,
        "status": status,
        "csv_d1": str(csv_d1),
        "candidate_count": int(len(candidates)),
        "charts": charts,
    }


def write_report(out_dir: Path, results: list[dict], symbols: list[str]) -> Path:
    stamp = datetime.now().strftime("%Y-%m-%d")
    lines = [
        f"# Crypto 非模拟盘定式沙盒审计 · {stamp}",
        "",
        "> 品种：**不在** `overseas_paper_monitor.MONITOR_COINS`（26 个模拟盘品种）内。",
        "> 定式：**DS01** 必审 + **DS03/DS05/DS07/DS08** 有成交则出图。",
        "> **只读** — 不改 OS/定式/模拟盘。",
        "",
        f"- 目标品种数：**{len(symbols)}**",
        f"- 完成审计：**{sum(1 for r in results if r.get('status') in {'ok', 'partial'})}**",
        "",
        "## 品种清单（非模拟盘）",
        "",
        "| # | 品种 | 状态 | DS01 | 其他定式出图 |",
        "|---|------|------|------|-------------|",
    ]
    for idx, row in enumerate(results, start=1):
        sym = row.get("symbol", "")
        charts = row.get("charts") or []
        ds01 = next((c for c in charts if c.get("strategy_id") == "DS01"), {})
        ds01_cell = "—"
        if ds01.get("status") == "ok":
            align = "✅" if ds01.get("camp_ok") else "❌" if ds01.get("camp_ok") is False else "?"
            ds01_cell = f"{ds01.get('entry_date')} {ds01.get('side')} {align}"
        elif ds01.get("status") == "no_trade":
            ds01_cell = "无成交"
        else:
            ds01_cell = ds01.get("status", "—")
        other_n = sum(
            1 for c in charts if c.get("strategy_id") != "DS01" and c.get("status") == "ok"
        )
        lines.append(f"| {idx} | {sym} | {row.get('status')} | {ds01_cell} | {other_n} |")

    lines.extend(["", "## 明细", ""])
    for row in results:
        sym = row.get("symbol")
        lines.append(f"### {sym}")
        for c in row.get("charts") or []:
            sid = c.get("strategy_id")
            if c.get("status") == "ok":
                camp = c.get("camp_ok")
                camp_txt = "camp_OK" if camp else ("?" if camp is None else "camp_MISMATCH")
                lines.append(
                    f"- **{sid}** {c.get('entry_date')} {c.get('side')} · {camp_txt} · `{Path(c.get('out','')).name}`"
                )
            else:
                lines.append(f"- **{sid}** {c.get('status')}")
        lines.append("")

    lines.extend(
        [
            "## 复跑",
            "",
            "```powershell",
            "python scripts/run_crypto_off_paper_sandbox_audit.py --count 10",
            "```",
            "",
        ]
    )
    report = out_dir / "CRYPTO_OFF_PAPER_SANDBOX_AUDIT.md"
    report.write_text("\n".join(lines), encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Crypto off-paper DS01+ sandbox audit batch")
    parser.add_argument("--count", type=int, default=10)
    parser.add_argument("--symbols", default="", help="Comma-separated override")
    parser.add_argument("--out-dir", default="")
    parser.add_argument("--no-ingest", action="store_true")
    args = parser.parse_args()

    stamp = datetime.now().strftime("%Y%m%d")
    out_dir = Path(args.out_dir) if args.out_dir else ROOT / "results" / f"crypto_off_paper_sandbox_{stamp}"
    out_dir.mkdir(parents=True, exist_ok=True)

    if args.symbols.strip():
        symbols = [s.strip().upper() for s in args.symbols.split(",") if s.strip()]
    else:
        symbols = select_symbols(count=args.count, allow_ingest=not args.no_ingest)

    if len(symbols) < args.count:
        print(f"WARN: only {len(symbols)}/{args.count} off-paper symbols with D1 data")

    results: list[dict] = []
    for sym in symbols:
        print(f"audit {sym} ...")
        results.append(audit_symbol(sym, out_dir=out_dir, allow_ingest=not args.no_ingest))

    manifest = out_dir / "crypto_off_paper_sandbox_manifest.json"
    manifest.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    report = write_report(out_dir, results, symbols)

    ok = sum(1 for r in results if r.get("status") == "ok")
    partial = sum(1 for r in results if r.get("status") == "partial")
    fail = sum(1 for r in results if r.get("status") == "error")
    print(f"CRYPTO_OFF_PAPER_SANDBOX ok={ok} partial={partial} error={fail}")
    print(f"manifest={manifest}")
    print(f"report={report}")
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
