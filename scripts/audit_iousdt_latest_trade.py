#!/usr/bin/env python3
"""Audit + sandbox for IOUSDT latest DS01 fill."""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
if str(ROOT / "packages" / "fengji_core") not in sys.path:
    sys.path.insert(0, str(ROOT / "packages" / "fengji_core"))

import pandas as pd
from backtest_ds07 import build_os_detail_frame
from quant.ds01 import ds01_left_filter_pass, entry_fill
from quant.os_engine import BLUE, RED

PLOT = ROOT / "scripts" / "plot_ds01_audit_sandbox.py"
OUT_DIR = ROOT / "results" / "iousdt_latest_trade_audit_20260618"


def symbol_csv(data_dir: Path, symbol: str) -> Path:
    for p in (data_dir / "overseas_1d" / f"{symbol}.csv", data_dir / "1d" / f"{symbol}.csv"):
        if p.exists():
            return p
    raise FileNotFoundError(symbol)


def load_csv(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    if "timestamp" in df.columns and "date" not in df.columns:
        df = df.rename(columns={"timestamp": "date"})
    df["date"] = pd.to_datetime(df["date"])
    return df.sort_values("date").reset_index(drop=True)


def audit_ds01_short(row: dict, csv_path: Path) -> dict:
    raw = load_csv(csv_path)
    os_df, engine = build_os_detail_frame(raw, gap=3)
    entry_day = pd.to_datetime(row["entry_date"]).normalize()
    matches = os_df.index[pd.to_datetime(os_df["date"]).dt.normalize() == entry_day]
    if len(matches) == 0:
        return {"verdict": "needs-data", "reason": f"entry date {entry_day} not in csv"}
    i = int(matches[-1])
    side = -1
    cur = os_df.iloc[i]
    prev = os_df.iloc[i - 1] if i > 0 else cur
    camp_today = int(cur.get("camp", 0) or 0)
    trigger = float(prev["low"] if side == -1 else prev["high"])
    stop = float(prev["high"] if side == -1 else prev["low"])
    fill_ok = entry_fill(cur, side, trigger) is not None
    visible_nodes = engine.hardened_by_bar[i - 1] if engine.hardened_by_bar and i > 0 else []
    left_check = float(cur["low"] if side == -1 else cur["high"])
    left_ok, left_count = ds01_left_filter_pass(visible_nodes, i, left_check, False, 30)

    issues = []
    if camp_today != BLUE:
        issues.append(f"camp_today={camp_today} expected BLUE(-1) for short")
    if not (float(prev["close"]) < float(prev["open"])):
        issues.append("signal bar not bearish")
    if not fill_ok:
        issues.append("entry_fill=False on entry bar OHLC")
    if not left_ok:
        issues.append(f"left30 fail count={left_count}")
    if abs(trigger - float(row["trigger_price"])) > max(1e-8, abs(trigger) * 0.005):
        issues.append(f"trigger mismatch calc={trigger} fill={row['trigger_price']}")
    if abs(stop - float(row["stop_price"])) > max(1e-8, abs(stop) * 0.005):
        issues.append(f"stop mismatch calc={stop} fill={row['stop_price']}")

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
        "signal_bearish": float(prev["close"]) < float(prev["open"]),
    }


def main() -> int:
    root = Path("/home/ubuntu/quant_crypto")
    ps = json.loads((root / "runtime/fengji_paper/state.json").read_text())
    pos = ps["symbols"]["IOUSDT"]["open_position"]
    row = {
        "symbol": "IOUSDT",
        "strategy_id": "DS01",
        "side": "short",
        "entry_date": pos["entry_time"][:10],
        "entry_time": pos["entry_time"],
        "entry_price": float(pos["entry_price"]),
        "trigger_price": float(pos["legs"][0]["trigger_price"]),
        "stop_price": float(pos["initial_stop"]),
        "order_id": pos["order_id"],
    }
    data_dir = root / "data"
    csv_path = symbol_csv(data_dir, "IOUSDT")
    audit = audit_ds01_short(row, csv_path)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    entry_dt = datetime.strptime(row["entry_date"], "%Y-%m-%d")
    start = (entry_dt - timedelta(days=90)).strftime("%Y-%m-%d")
    end = datetime.now().strftime("%Y-%m-%d")
    png = OUT_DIR / "IOUSDT_DS01_short_latest.png"
    verdict = "PASS camp_OK left30_OK" if audit["verdict"] == "valid" else "; ".join(audit.get("issues") or [])
    subprocess.run(
        [
            sys.executable,
            str(PLOT),
            "--market",
            "crypto",
            "--csv",
            str(csv_path),
            "--symbol",
            "IOUSDT",
            "--side",
            "short",
            "--entry-date",
            row["entry_date"],
            "--fill-price",
            str(row["entry_price"]),
            "--start",
            start,
            "--end",
            end,
            "--out",
            str(png),
            "--verdict",
            f"DS01 short {row['entry_time']} left={audit.get('left_count')} {verdict}",
        ],
        check=True,
        cwd=str(ROOT),
    )

    lines = [
        "# IOUSDT 最近一笔模拟交易核查",
        "",
        f"生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "## 成交摘要",
        "",
        f"- order_id: `{row['order_id']}`",
        f"- 定式: **DS01 D1 short**",
        f"- 入场: {row['entry_time']} @ **{row['entry_price']}**",
        f"- 触发/止损: {row['trigger_price']} / {row['stop_price']}",
        f"- 当前动态止损: {pos.get('current_stop')}（{pos.get('stop_source')}）",
        f"- OS 阵营（挂单记录）: **blue**",
        f"- left_count（挂单 reason）: 2",
        "",
        "## 规则复核",
        "",
        f"- **结论: {audit['verdict'].upper()}**",
    ]
    if audit.get("issues"):
        for issue in audit["issues"]:
            lines.append(f"  - {issue}")
    else:
        lines.append("  - 蓝营 + 阴线信号棍 + entry_fill + 左30≤2 与 OS 重算一致")
    lines.extend(
        [
            f"- 信号棍日期: {audit.get('signal_date')}",
            f"- 入场 K 日期: {audit.get('entry_date')}",
            f"- camp={audit.get('camp_today')} trigger_calc={audit.get('trigger_calc')} stop_calc={audit.get('stop_calc')}",
            f"- left_count_calc={audit.get('left_count')} fill_ok={audit.get('fill_ok')}",
            "",
            f"## 沙盒图",
            "",
            f"![IOUSDT DS01 short](IOUSDT_DS01_short_latest.png)",
            "",
            f"路径: `{png}`",
        ]
    )
    summary = OUT_DIR / "SUMMARY.md"
    summary.write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps({"audit": audit, "png": str(png), "summary": str(summary)}, ensure_ascii=False, indent=2))
    print(summary.read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
