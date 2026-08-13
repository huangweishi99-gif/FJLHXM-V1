#!/usr/bin/env python3
"""DS01 sandbox review for RENDER / IO / DOGE (latest DS01 fill per symbol)."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
for p in (SRC, ROOT / "packages" / "fengji_core"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import pandas as pd
from backtest_ds07 import build_os_detail_frame
from quant.ds01 import ds01_left_filter_pass, entry_fill
from quant.os_engine import BLUE, RED

PLOT = ROOT / "scripts" / "plot_ds01_audit_sandbox.py"
SYMBOLS = ("RENDERUSDT", "IOUSDT", "DOGEUSDT")


def _csv_last_date(path: Path) -> pd.Timestamp:
    df = load_csv(path)
    return pd.to_datetime(df["date"].iloc[-1])


def symbol_csv(data_dir: Path, symbol: str) -> Path:
    base = symbol.replace("USDT", "")
    candidates = [
        data_dir / "overseas_1d" / f"{symbol}.csv",
        data_dir / "1d" / f"{symbol}.csv",
        data_dir / "crypto_okx" / f"{base}-USDT_1D_1825d.csv",
        data_dir / "crypto_okx" / f"{base}-USDT_1D_180d.csv",
    ]
    existing = [p for p in candidates if p.is_file()]
    if not existing:
        raise FileNotFoundError(f"no D1 csv for {symbol}")
    return max(existing, key=_csv_last_date)


def load_csv(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    if "timestamp" in df.columns and "date" not in df.columns:
        df = df.rename(columns={"timestamp": "date"})
    df["date"] = pd.to_datetime(df["date"])
    return df.sort_values("date").reset_index(drop=True)


def pick_latest_ds01(bucket: dict[str, Any], symbol: str) -> dict[str, Any] | None:
    op = bucket.get("open_position")
    if isinstance(op, dict) and str(op.get("strategy_id", "")).upper() == "DS01":
        leg = (op.get("legs") or [{}])[0]
        return {
            "symbol": symbol,
            "strategy_id": "DS01",
            "side": str(op.get("direction") or "short").lower(),
            "entry_date": str(op.get("entry_time", ""))[:10],
            "entry_time": str(op.get("entry_time", "")),
            "entry_price": float(op.get("entry_price") or 0),
            "trigger_price": float(leg.get("trigger_price") or 0) or None,
            "stop_price": float(op.get("initial_stop") or leg.get("initial_stop") or 0),
            "order_id": str(op.get("order_id") or ""),
            "status": "OPEN",
        }
    closed = [
        t
        for t in (bucket.get("closed_trades") or [])
        if str(t.get("strategy_id", "")).upper() == "DS01"
    ]
    if not closed:
        return None
    closed.sort(key=lambda x: str(x.get("entry_time") or ""), reverse=True)
    t = closed[0]
    return {
        "symbol": symbol,
        "strategy_id": "DS01",
        "side": str(t.get("direction") or "short").lower(),
        "entry_date": str(t.get("entry_time", ""))[:10],
        "entry_time": str(t.get("entry_time", "")),
        "entry_price": float(t.get("entry_price") or 0),
        "trigger_price": None,
        "stop_price": float(t.get("initial_stop") or 0),
        "order_id": str(t.get("order_id") or ""),
        "exit_time": str(t.get("exit_time") or ""),
        "status": "CLOSED",
    }


def audit_ds01(row: dict[str, Any], csv_path: Path) -> dict[str, Any]:
    raw = load_csv(csv_path)
    os_df, engine = build_os_detail_frame(raw, gap=3)
    entry_day = pd.to_datetime(row["entry_date"]).normalize()
    matches = os_df.index[pd.to_datetime(os_df["date"]).dt.normalize() == entry_day]
    if len(matches) == 0:
        eligible = os_df[pd.to_datetime(os_df["date"]).dt.normalize() <= entry_day]
        if eligible.empty:
            return {"verdict": "needs-data", "issues": [f"entry date {entry_day} not in csv"]}
        i = int(eligible.index[-1])
        row = dict(row)
        row["entry_date"] = str(os_df.iloc[i]["date"])[:10]
        entry_day = pd.to_datetime(row["entry_date"]).normalize()
    else:
        i = int(matches[-1])
    if i < 1:
        return {"verdict": "invalid", "issues": ["no previous bar for signal stick"]}

    side = -1 if row["side"] == "short" else 1
    cur = os_df.iloc[i]
    prev = os_df.iloc[i - 1]
    camp_today = int(cur.get("camp", 0) or 0)
    camp_need = RED if side == 1 else BLUE
    trigger = float(prev["low"] if side == -1 else prev["high"])
    stop = float(prev["high"] if side == -1 else prev["low"])
    fill_ok = entry_fill(cur, side, trigger) is not None
    visible_nodes = engine.hardened_by_bar[i - 1] if engine.hardened_by_bar else []
    left_check = float(cur["low"] if side == -1 else cur["high"])
    left_ok, left_count = ds01_left_filter_pass(visible_nodes, i, left_check, False, 30)

    issues: list[str] = []
    if camp_today != camp_need:
        issues.append(f"camp_today={camp_today} expected={camp_need}")
    if side == -1 and not (float(prev["close"]) < float(prev["open"])):
        issues.append("signal bar not bearish")
    if side == 1 and not (float(prev["close"]) > float(prev["open"])):
        issues.append("signal bar not bullish")
    if not fill_ok:
        issues.append("entry_fill=False on entry bar OHLC")
    if not left_ok:
        issues.append(f"left_line fail count={left_count} (need <=2)")
    if row.get("trigger_price") is not None:
        tp = float(row["trigger_price"])
        if abs(trigger - tp) > max(1e-8, abs(trigger) * 0.005):
            issues.append(f"trigger mismatch calc={trigger} fill={tp}")
    if row.get("stop_price"):
        sp = float(row["stop_price"])
        if abs(stop - sp) > max(1e-8, abs(stop) * 0.02):
            issues.append(f"stop mismatch calc={stop} fill={sp} (initial_stop may trail)")

    return {
        "verdict": "valid" if not issues else "invalid",
        "issues": issues,
        "camp_today": camp_today,
        "signal_date": str(prev["date"]),
        "entry_date": str(cur["date"]),
        "trigger_calc": trigger,
        "stop_calc": stop,
        "fill_ok": fill_ok,
        "left_ok": left_ok,
        "left_count": left_count,
    }


def plot_row(row: dict[str, Any], audit: dict[str, Any], csv_path: Path, png: Path) -> None:
    entry_dt = datetime.strptime(row["entry_date"][:10], "%Y-%m-%d")
    start = (entry_dt - timedelta(days=90)).strftime("%Y-%m-%d")
    end = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
    verdict = "VALID" if audit.get("verdict") == "valid" else "; ".join(audit.get("issues") or [])
    subprocess.run(
        [
            sys.executable,
            str(PLOT),
            "--market",
            "crypto",
            "--csv",
            str(csv_path),
            "--symbol",
            row["symbol"],
            "--side",
            row["side"],
            "--entry-date",
            row["entry_date"][:10],
            "--fill-price",
            str(row["entry_price"]),
            "--start",
            start,
            "--end",
            end,
            "--out",
            str(png),
            "--verdict",
            f"DS01 {row['side']} {row.get('entry_time','')} left={audit.get('left_count')} {verdict}",
        ],
        check=True,
        cwd=str(ROOT),
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--paper-state", default=str(ROOT / "runtime" / "overseas_paper_state.json"))
    parser.add_argument("--data-dir", default=str(ROOT / "data"))
    parser.add_argument("--out-dir", default=str(ROOT / "results" / "ds01_three_coin_review_20260618"))
    args = parser.parse_args()

    ps = json.loads(Path(args.paper_state).read_text(encoding="utf-8"))
    data_dir = Path(args.data_dir)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    results: list[dict[str, Any]] = []
    for symbol in SYMBOLS:
        bucket = (ps.get("symbols") or {}).get(symbol) or {}
        row = pick_latest_ds01(bucket, symbol)
        if not row:
            results.append({"symbol": symbol, "verdict": "skipped", "reason": "no DS01 fill"})
            continue
        csv_path = symbol_csv(data_dir, symbol)
        audit = audit_ds01(row, csv_path)
        png = out_dir / f"{symbol}_DS01_{row['side']}.png"
        if audit.get("verdict") != "needs-data":
            plot_row(row, audit, csv_path, png)
        per = {
            "symbol": symbol,
            "row": row,
            "audit": audit,
            "csv": str(csv_path),
            "png": str(png) if png.exists() else None,
        }
        results.append(per)
        md = out_dir / f"{symbol}_DS01.md"
        lines = [
            f"# {symbol} DS01 复核",
            "",
            f"- 状态：**{row['status']}**",
            f"- order_id: `{row['order_id']}`",
            f"- 入场: {row['entry_time']} @ **{row['entry_price']}**",
            f"- 结论: **{audit.get('verdict', '').upper()}**",
        ]
        if audit.get("issues"):
            for issue in audit["issues"]:
                lines.append(f"  - {issue}")
        else:
            lines.append("  - 阵营 + 信号棍 + entry_fill + 左线<=2 与 OS 重算一致")
        lines.extend(
            [
                f"- left_count={audit.get('left_count')} camp={audit.get('camp_today')}",
                f"- 信号棍: {audit.get('signal_date')} · 入场K: {audit.get('entry_date')}",
                "",
                f"![{symbol}]({png.name})",
            ]
        )
        md.write_text("\n".join(lines), encoding="utf-8")

    summary_lines = [
        "# DS01 三币沙盒复核 · RENDER / IO / DOGE",
        "",
        f"生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "| 品种 | 状态 | 入场 | 结论 | left | 图 |",
        "|---|---|---|---:|---:|---|",
    ]
    valid_n = 0
    for per in results:
        if "row" not in per:
            summary_lines.append(f"| {per['symbol']} | — | — | {per.get('verdict')} | — | — |")
            continue
        row, audit = per["row"], per["audit"]
        v = audit.get("verdict", "")
        if v == "valid":
            valid_n += 1
        png_name = Path(per["png"]).name if per.get("png") else "—"
        summary_lines.append(
            f"| {row['symbol']} | {row['status']} | {row['entry_time']} | **{v}** | {audit.get('left_count')} | `{png_name}` |"
        )
    summary_lines.extend(["", f"**{valid_n}/{len(SYMBOLS)} VALID**", ""])
    for per in results:
        if "audit" in per and per["audit"].get("issues"):
            summary_lines.append(f"- {per['symbol']}: " + "; ".join(per["audit"]["issues"]))

    (out_dir / "SUMMARY.md").write_text("\n".join(summary_lines), encoding="utf-8")
    (out_dir / "report.json").write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"out_dir": str(out_dir), "valid": valid_n, "total": len(SYMBOLS)}, indent=2))
    return 0 if valid_n == len(SYMBOLS) else 1


if __name__ == "__main__":
    raise SystemExit(main())
