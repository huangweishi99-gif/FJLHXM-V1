#!/usr/bin/env python3
"""审计监测品种各周期峰极 OS 状态：连线/阵营是否与 K 线同步，可选增量修复。"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages" / "fengji_core"))
sys.path.insert(0, str(ROOT / "scripts"))

from fengji_core.os_state_store import date_key, read_os_state, state_matches_frame  # noqa: E402
from rebuild_os_state_all import (  # noqa: E402
    DEFAULT_TAIL_ROWS,
    discover_sources,
    load_ohlcv,
    parse_input_spec,
    rebuild_one,
    source_preference_key,
    state_path,
    state_symbol,
    write_outputs,
)

DOMESTIC_FUTURES_CODES = {
    c.strip().upper()
    for c in "SA,FG,RB,PG,FU,CJ,OI,SP,LH,JD,SI,PP,SH,EB,NI,SR,EG,AO,JM,EC,RU,BR,SF,M,MA,P,V,TA,UR,CF,LC,AU,AG,SC".split(",")
    if c.strip()
}

CRYPTO_FALLBACK = {
    "BTCUSDT", "ETHUSDT", "SOLUSDT", "AVAXUSDT", "TRUMPUSDT", "RENDERUSDT", "IOUSDT", "TAOUSDT",
    "DASHUSDT", "LTCUSDT", "DOGEUSDT", "ADAUSDT", "APTUSDT", "LINKUSDT", "BNBUSDT", "ZECUSDT",
    "XRPUSDT", "HYPEUSDT", "ATHUSDT", "PEPEUSDT", "ARBUSDT", "OPUSDT", "SUIUSDT", "NEARUSDT",
    "INJUSDT", "WLDUSDT",
}


def load_crypto_monitored(root: Path) -> set[str]:
    path = root / "src" / "overseas_paper_monitor.py"
    if not path.exists():
        return set(CRYPTO_FALLBACK)
    text = path.read_text(encoding="utf-8")
    block = re.search(r"MONITOR_COINS\s*=\s*\[(.*?)\]", text, re.S)
    if not block:
        return set(CRYPTO_FALLBACK)
    coins = set(re.findall(r'"([A-Z0-9]+USDT)"', block.group(1)))
    return coins or set(CRYPTO_FALLBACK)


def collect_sources(market: str, root: Path) -> list:
    specs = [
        parse_input_spec(f"data/1d,market={market}"),
        parse_input_spec(f"data/1h,market={market}"),
        parse_input_spec(f"data/15m,market={market}"),
    ]
    by_key: dict[tuple[str, str, str], Any] = {}
    for spec in specs:
        for source in discover_sources(spec):
            key = (source.market, state_symbol(source.symbol, source.market), source.timeframe)
            current = by_key.get(key)
            if current is None or source_preference_key(source) < source_preference_key(current):
                by_key[key] = source
    return sorted(by_key.values(), key=lambda s: (s.symbol, s.timeframe))


def monitored_keys(market: str, root: Path) -> set[tuple[str, str]]:
    if market == "crypto":
        return {(state_symbol(s, "crypto"), tf) for s in load_crypto_monitored(root) for tf in ("1d", "1h", "15m")}
    return {(code, tf) for code in DOMESTIC_FUTURES_CODES for tf in ("1d", "1h", "15m")}


def tail_for_timeframe(tf: str, args: argparse.Namespace) -> int:
    mapping = {
        "1d": max(int(args.d1_tail), DEFAULT_TAIL_ROWS["1d"]),
        "1h": max(int(args.h1_tail), DEFAULT_TAIL_ROWS["1h"]),
        "15m": max(int(args.m15_tail), DEFAULT_TAIL_ROWS["15m"]),
    }
    return mapping[tf]


def audit_one(source, *, state_dir: Path, gap: int, tail_rows: int) -> dict[str, Any]:
    issues: list[str] = []
    fixable = False
    csv_last = ""
    st_last = ""
    camp = camp_confirmed = pending_turn = None
    try:
        frame = load_ohlcv(source.path, market=source.market, tail_rows=tail_rows)
        csv_last = date_key(frame.iloc[-1]["date"])
        out_state = state_path(state_dir, source)
        state = read_os_state(out_state)
        record_hbb = source.timeframe == "1d"
        if state is None:
            issues.append("missing_state")
            fixable = True
        else:
            st_last = str(state.get("last_date", ""))
            camp = state.get("camp")
            camp_confirmed = state.get("camp_confirmed")
            pending_turn = bool(state.get("pending_turn", False))
            if st_last != csv_last:
                issues.append(f"stale_csv:{st_last}!={csv_last}")
                fixable = True
            if not state_matches_frame(state, frame, gap, record_hbb):
                issues.append("fingerprint_mismatch")
                fixable = True
            if not pending_turn and camp is not None and camp_confirmed is not None and int(camp) != int(camp_confirmed):
                issues.append(f"camp_unconfirmed:{camp}!={camp_confirmed}")
        ok = len(issues) == 0
        return {
            "market": source.market,
            "symbol": source.symbol,
            "state_symbol": state_symbol(source.symbol, source.market),
            "timeframe": source.timeframe,
            "status": "ok" if ok else "issue",
            "issues": issues,
            "fixable": fixable,
            "csv_last": csv_last,
            "state_last": st_last,
            "camp": camp,
            "camp_confirmed": camp_confirmed,
            "pending_turn": pending_turn,
            "source_csv": str(source.path),
            "state_file": str(out_state),
            "rows": len(frame),
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "market": source.market,
            "symbol": source.symbol,
            "state_symbol": state_symbol(source.symbol, source.market),
            "timeframe": source.timeframe,
            "status": "error",
            "issues": [f"{type(exc).__name__}:{exc}"],
            "fixable": False,
            "csv_last": csv_last,
            "state_last": st_last,
            "source_csv": str(source.path),
            "error": str(exc),
        }


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit FengJi OS state freshness for monitored symbols.")
    parser.add_argument("--market", choices=("crypto", "futures"), required=True)
    parser.add_argument("--root", default=str(ROOT))
    parser.add_argument("--state-dir", default="runtime/fengji_os_state")
    parser.add_argument("--audit-dir", default="")
    parser.add_argument("--gap", type=int, default=3)
    parser.add_argument("--d1-tail", type=int, default=1095)
    parser.add_argument("--h1-tail", type=int, default=2400)
    parser.add_argument("--m15-tail", type=int, default=960)
    parser.add_argument("--fix", action="store_true", help="Incremental rebuild for stale/missing/mismatch states")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()

    root = Path(args.root)
    state_dir = root / args.state_dir
    os.environ["FENGJI_MARKET"] = args.market

    wanted = monitored_keys(args.market, root)
    sources = [s for s in collect_sources(args.market, root) if (state_symbol(s.symbol, s.market), s.timeframe) in wanted]

    rows: list[dict[str, Any]] = []
    for source in sources:
        tail = tail_for_timeframe(source.timeframe, args)
        row = audit_one(source, state_dir=state_dir, gap=args.gap, tail_rows=tail)
        rows.append(row)

    fixed: list[dict[str, Any]] = []
    if args.fix:
        for source in sources:
            audit = next(r for r in rows if r["symbol"] == source.symbol and r["timeframe"] == source.timeframe)
            if audit.get("status") == "ok" or not audit.get("fixable"):
                continue
            tail = tail_for_timeframe(source.timeframe, args)
            fix_row = rebuild_one(
                source,
                state_dir=state_dir,
                gap=args.gap,
                mode="incremental",
                record_hardened_by_bar=(source.timeframe == "1d"),
                tail_rows=tail,
            )
            fixed.append(fix_row)
            # re-audit
            after = audit_one(source, state_dir=state_dir, gap=args.gap, tail_rows=tail)
            after["fixed_from"] = audit.get("issues")
            idx = rows.index(audit)
            rows[idx] = after

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    audit_dir = Path(args.audit_dir) if args.audit_dir else root / "results" / f"os_state_freshness_{args.market}_{stamp}"
    audit_dir.mkdir(parents=True, exist_ok=True)
    write_outputs(rows, audit_dir)
    if fixed:
        (audit_dir / "os_state_fix.json").write_text(json.dumps(fixed, ensure_ascii=False, indent=2, default=str), encoding="utf-8")

    issue_rows = [r for r in rows if r.get("status") != "ok"]
    summary = {
        "market": args.market,
        "generated_at": datetime.now().astimezone().isoformat(),
        "monitored_pairs": len(wanted),
        "audited": len(rows),
        "ok": sum(1 for r in rows if r.get("status") == "ok"),
        "issues": len(issue_rows),
        "errors": sum(1 for r in rows if r.get("status") == "error"),
        "fixed_count": len(fixed),
        "issue_symbols": sorted({r["state_symbol"] for r in issue_rows}),
        "audit_dir": str(audit_dir),
    }
    (audit_dir / "freshness_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    if args.quiet:
        print(
            f"{'PASS' if not issue_rows else 'FAIL'} market={args.market} "
            f"ok={summary['ok']}/{summary['audited']} fixed={summary['fixed_count']} "
            f"issues={summary['issues']}"
        )
    else:
        print(json.dumps({"summary": summary, "issues_sample": issue_rows[:20]}, ensure_ascii=False, indent=2, default=str))

    return 0 if not issue_rows else 1


if __name__ == "__main__":
    raise SystemExit(main())
