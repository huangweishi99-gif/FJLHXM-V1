#!/usr/bin/env python3
"""从 domestic_paper_state 读取开仓，做 OS camp 沙盒深度复核（通用）。"""
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
from backtest_ds07 import build_os_detail_frame  # noqa: E402
from fengji_core.data import load_tq_futures_kline_csv  # noqa: E402

PLOT = ROOT / "scripts" / "plot_ds01_audit_sandbox.py"
DEFAULT_STATE = ROOT / "runtime" / "domestic_paper_state.json"
FUTURES_CODE = {
    "EBUSDT": "EB",
    "RBUSDT": "RB",
    "PGUSDT": "PG",
    "PPUSDT": "PP",
}


def _load_positions(state_path: Path, symbol: str) -> list[dict[str, Any]]:
    state = json.loads(state_path.read_text(encoding="utf-8"))
    bucket = (state.get("symbols") or {}).get(symbol.upper()) or {}
    rows: list[dict[str, Any]] = []
    for pos in bucket.get("open_positions") or []:
        if not isinstance(pos, dict):
            continue
        entry_time = str(pos.get("entry_time") or "")
        entry_date = entry_time[:10] if entry_time else ""
        rows.append(
            {
                "strategy_id": str(pos.get("strategy_id") or "").upper(),
                "entry_date": entry_date,
                "entry_time": entry_time,
                "fill_price": float(pos.get("entry_price") or pos.get("trigger_price") or 0),
                "side": str(pos.get("direction") or "long").lower(),
                "order_id": str(pos.get("order_id") or pos.get("key") or ""),
                "setup": str(pos.get("setup") or ""),
            }
        )
    return rows


def _resolve_csv(symbol: str) -> Path:
    code = FUTURES_CODE.get(symbol.upper()) or symbol.upper().replace("USDT", "")
    return resolve_csv(code, "FUTURES")


def _load_os(csv: Path) -> tuple[pd.DataFrame, Any]:
    df = load_tq_futures_kline_csv(csv)
    df = df[df["date"] >= pd.Timestamp("2020-01-01")].sort_values("date")
    return build_os_detail_frame(df, gap=3)


def _bar_evidence(os_df: pd.DataFrame, entry_date: str, side: str) -> dict[str, Any]:
    edt = pd.Timestamp(entry_date).normalize()
    idxs = os_df.index[pd.to_datetime(os_df["date"]).dt.normalize() == edt]
    if len(idxs) == 0:
        rows = os_df[pd.to_datetime(os_df["date"]).dt.normalize() <= edt]
        if rows.empty:
            raise ValueError(f"no D1 bar for {entry_date}")
        entry_i = int(rows.index[-1])
    else:
        entry_i = int(idxs[-1])
    signal_i = entry_i - 1 if entry_i > 0 else entry_i
    er = os_df.iloc[entry_i]
    sr = os_df.iloc[signal_i]
    expected = -1 if side == "short" else 1
    signal_camp = int(sr.get("camp", 0) or 0)
    entry_camp = int(er.get("camp", 0) or 0)
    return {
        "signal_date": str(sr["date"])[:10],
        "entry_date": str(er["date"])[:10],
        "signal_camp": signal_camp,
        "entry_camp": entry_camp,
        "camp_confirmed_signal": int(sr.get("camp_confirmed", 0) or 0),
        "camp_confirmed_entry": int(er.get("camp_confirmed", 0) or 0),
        "signal_ohlc": (float(sr["open"]), float(sr["high"]), float(sr["low"]), float(sr["close"])),
        "entry_ohlc": (float(er["open"]), float(er["high"]), float(er["low"]), float(er["close"])),
        "trigger_ref": float(sr["low"] if side == "short" else sr["high"]),
        "stop_ref": float(sr["high"] if side == "short" else sr["low"]),
        "camp_ok": signal_camp == expected and entry_camp == expected,
        "expected_camp": expected,
    }


def _combo_key(pos: dict[str, Any]) -> tuple[str, str, str]:
    return (pos["entry_time"][:16], pos["side"], f"{pos['fill_price']:.4f}")


def _verdict(pos: dict[str, Any], ev: dict[str, Any], combo_dup: bool) -> tuple[str, str]:
    if not ev["camp_ok"]:
        return "audit_invalid", "signal/entry camp 与方向不一致"
    if combo_dup:
        return "combo_review", "同品种同向同刻/同价并行，组合层待确认（camp 对齐）"
    sid = pos["strategy_id"]
    if sid == "DS01":
        o, _, _, c = ev["signal_ohlc"]
        if pos["side"] == "short" and c < o and ev["signal_camp"] == -1:
            return "valid", "蓝营阴线信号棍 + 触发对齐"
        if pos["side"] == "long" and c > o and ev["signal_camp"] == 1:
            return "valid", "红营阳线信号棍 + 触发对齐"
        return "valid", "camp 对齐（形态见沙盒图）"
    return "valid", f"{sid} camp 对齐；结构见沙盒图"


def _plot(csv: Path, symbol: str, pos: dict[str, Any], ev: dict[str, Any], out: Path) -> None:
    ts = pd.Timestamp(pos["entry_date"])
    cmd = [
        sys.executable,
        str(PLOT),
        "--csv",
        str(csv),
        "--market",
        "futures",
        "--symbol",
        symbol,
        "--side",
        pos["side"],
        "--entry-date",
        pos["entry_date"],
        "--fill-price",
        str(pos["fill_price"]),
        "--start",
        str((ts - timedelta(days=75)).date()),
        "--end",
        str((ts + timedelta(days=25)).date()),
        "--order-tag",
        f"{symbol}-{pos['strategy_id']}-deep",
        "--verdict",
        f"{symbol} {pos['strategy_id']} {pos['side']} camp_signal={ev['signal_camp']} expected={ev['expected_camp']}",
        "--out",
        str(out),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, cwd=str(ROOT))
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr or proc.stdout or "plot failed")


def _render(symbol: str, results: list[dict[str, Any]]) -> str:
    display = FUTURES_CODE.get(symbol, symbol.replace("USDT", ""))
    lines = [
        f"# S2 深度复核 · {display} ({symbol}) · paper 当前持仓",
        "",
        f"生成：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "## 总结论",
        "",
    ]
    valid = sum(1 for r in results if r["verdict"] == "valid")
    combo = sum(1 for r in results if r["verdict"] == "combo_review")
    invalid = sum(1 for r in results if r["verdict"] == "audit_invalid")
    lines.append(f"- **valid** {valid} · **combo_review** {combo} · **audit_invalid** {invalid}")
    lines.append("- 只读审计；不改 OS/定式/paper_state。")
    lines.append("")
    for r in results:
        p, ev = r["position"], r["evidence"]
        lines.extend(
            [
                f"## {p['strategy_id']} · {p['entry_date']} {p['side']} @ {p['fill_price']}",
                "",
                f"**{r['verdict']}** — {r['reason']}",
                "",
                f"- order_id：`{p['order_id']}`",
                f"- setup：{p.get('setup') or '—'}",
                "",
                f"| 信号棍 | {ev['signal_date']} camp **{ev['signal_camp']}** |",
                f"| 入场 K | {ev['entry_date']} camp **{ev['entry_camp']}** |",
                f"| camp | {'PASS camp_OK' if ev['camp_ok'] else 'FAIL'} |",
                f"| 图 | `{Path(r['png']).name}` |",
                "",
            ]
        )
    lines.extend(
        [
            "## 复跑",
            "",
            f"```powershell",
            f"python scripts/run_paper_symbol_deep_review.py --symbol {symbol}",
            "```",
            "",
        ]
    )
    return "\n".join(lines)


def review_symbol(
    symbol: str,
    *,
    state_path: Path = DEFAULT_STATE,
    out_dir: Path,
) -> dict[str, Any]:
    symbol = symbol.upper()
    positions = _load_positions(state_path, symbol)
    if not positions:
        raise SystemExit(f"no open positions for {symbol}")
    csv = _resolve_csv(symbol)
    os_df, _ = _load_os(csv)

    combo_counts: dict[tuple[str, str, str], int] = {}
    for p in positions:
        k = _combo_key(p)
        combo_counts[k] = combo_counts.get(k, 0) + 1

    results: list[dict[str, Any]] = []
    for pos in positions:
        ev = _bar_evidence(os_df, pos["entry_date"], pos["side"])
        dup = combo_counts.get(_combo_key(pos), 0) > 1 and len(positions) > 1
        # same entry_time same side but different price -> combo_review
        same_moment = sum(
            1
            for o in positions
            if o["entry_time"][:16] == pos["entry_time"][:16] and o["side"] == pos["side"]
        ) > 1
        verdict, reason = _verdict(pos, ev, dup or same_moment)
        tag = f"{symbol.replace('USDT', '')}_{pos['strategy_id']}_deep_{pos['entry_date'].replace('-', '')}"
        png = out_dir / f"{tag}.png"
        _plot(csv, symbol, pos, ev, png)
        results.append(
            {
                "position": pos,
                "evidence": ev,
                "png": str(png),
                "verdict": verdict,
                "reason": reason,
            }
        )

    stamp = datetime.now().strftime("%Y%m%d")
    md = out_dir / f"{symbol.replace('USDT', '')}_deep_review_{stamp}.md"
    md.write_text(_render(symbol, results), encoding="utf-8")
    manifest = {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "symbol": symbol,
        "csv": str(csv),
        "results": results,
        "markdown": str(md),
    }
    json_path = out_dir / f"{symbol.replace('USDT', '')}_deep_review_{stamp}.json"
    json_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    return {"symbol": symbol, "markdown": str(md), "results": results}


def main() -> int:
    parser = argparse.ArgumentParser(description="Paper symbol deep review sandbox")
    parser.add_argument("--symbol", action="append", required=True, help="e.g. EBUSDT RBUSDT")
    parser.add_argument("--state", type=Path, default=DEFAULT_STATE)
    parser.add_argument("--out-dir", default="", help="default results/s2_ds01_sandbox_20260614")
    args = parser.parse_args()
    out_dir = Path(args.out_dir) if args.out_dir else ROOT / "results" / "s2_ds01_sandbox_20260614"
    out_dir.mkdir(parents=True, exist_ok=True)

    summaries = []
    for sym in args.symbol:
        summaries.append(review_symbol(sym, state_path=args.state, out_dir=out_dir))
        r = summaries[-1]
        print(f"{sym}:")
        for row in r["results"]:
            p = row["position"]
            print(f"  {p['strategy_id']} {p['entry_date']} -> {row['verdict']}")
        print(f"  report={r['markdown']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
