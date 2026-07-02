#!/usr/bin/env python3
"""批量审计 Web 峰极连线 segments（实线/橡皮筋/沙盒对齐）。

用法:
  python scripts/audit_fengji_chart_lines.py
  python scripts/audit_fengji_chart_lines.py --symbols SC,NI,AG,RB
  python scripts/audit_fengji_chart_lines.py --market CRYPTO --symbols ETHUSDT,SOLUSDT
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "packages" / "fengji_core"), str(ROOT / "services")]

from chart_bundle import ChartBundleRequest, build_chart_bundle, _build_stateful_os_overlay, _load_chart_ohlcv
from fengji_core.chart_line import audit_hardened_segments, audit_web_vs_sandbox, iso_date
from api.main import resolve_csv


def _audit_symbol(symbol: str, market: str, years: int, state_dir: Path) -> dict:
    csv_path = resolve_csv(symbol, market)
    futures_mode = market.upper() not in {"CRYPTO", "A_STOCK", "ASTOCK"}
    req = ChartBundleRequest(
        csv_path=csv_path,
        strategy_id="DS03",
        years=years,
        futures_mode=futures_mode,
        os_state_dir=state_dir,
        os_symbol=symbol,
        os_timeframe="1d",
        os_tail_rows=1095,
    )
    bundle = build_chart_bundle(req)
    bars = bundle.get("bars") or []
    segments = bundle.get("hardened_segments") or []
    bar_dates = {b["t"] for b in bars}
    last_bar = bars[-1]["t"] if bars else None

    issues = audit_hardened_segments(
        segments,
        bar_dates,
        require_trail=bool(bars),
        last_bar_date=last_bar,
    )

    sandbox_issues: list = []
    if req.os_state_dir is not None:
        try:
            raw = _load_chart_ohlcv(req)
            _, engine, _ = _build_stateful_os_overlay(raw, req)
            visible = bar_dates
            sandbox_issues = audit_web_vs_sandbox(engine, raw, segments, visible, iso_date)
        except Exception as exc:  # noqa: BLE001
            sandbox_issues = [
                type("X", (), {"code": "SANDBOX_ERROR", "message": str(exc), "segment_index": None})()
            ]

    all_issues = list(issues) + list(sandbox_issues)
    solid = [s for s in segments if s.get("style", "solid") == "solid" and s.get("kind") != "provisional"]
    dashed = [s for s in segments if s.get("style") == "dashed" or s.get("kind") == "provisional"]
    return {
        "symbol": symbol,
        "market": market,
        "bars": len(bars),
        "last_bar": last_bar,
        "solid_segments": len(solid),
        "dashed_segments": len(dashed),
        "issues": [{"code": i.code, "message": i.message, "segment_index": i.segment_index} for i in all_issues],
        "ok": not all_issues,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit Fengji chart line segments")
    parser.add_argument("--market", default="FUTURES", help="FUTURES | CRYPTO | A_STOCK")
    parser.add_argument("--symbols", default="", help="Comma-separated; empty = default batch")
    parser.add_argument("--years", type=int, default=2)
    parser.add_argument("--state-dir", default=str(ROOT / "runtime" / "fengji_os_state"))
    parser.add_argument("--json-out", default="")
    args = parser.parse_args()

    if args.symbols.strip():
        symbols = [s.strip().upper() for s in args.symbols.split(",") if s.strip()]
    elif args.market.upper() == "CRYPTO":
        symbols = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT"]
    else:
        symbols = ["SC", "NI", "AG", "RB", "LC", "LH", "PVC", "PP", "SI", "FG"]

    state_dir = Path(args.state_dir)
    results = []
    failed = 0
    for sym in symbols:
        try:
            row = _audit_symbol(sym, args.market, args.years, state_dir)
        except FileNotFoundError as exc:
            row = {"symbol": sym, "market": args.market, "ok": False, "issues": [{"code": "NO_CSV", "message": str(exc)}]}
        except Exception as exc:  # noqa: BLE001
            row = {"symbol": sym, "market": args.market, "ok": False, "issues": [{"code": "ERROR", "message": f"{type(exc).__name__}: {exc}"}]}
        results.append(row)
        if row.get("ok"):
            print(
                f"OK  {sym}: bars={row.get('bars')} solid={row.get('solid_segments')} "
                f"dashed={row.get('dashed_segments')} last={row.get('last_bar')}"
            )
        else:
            failed += 1
            print(f"FAIL {sym}:", file=sys.stderr)
            for issue in row.get("issues") or []:
                print(f"  - [{issue.get('code')}] {issue.get('message')}", file=sys.stderr)

    if args.json_out:
        out = Path(args.json_out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Wrote {out}")

    print(f"\nSummary: {len(results) - failed}/{len(results)} passed, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
