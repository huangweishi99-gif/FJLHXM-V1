#!/usr/bin/env python3
"""HYPE DS06 pending vs DS03 open combo review (Wave4 S3 observation case)."""
from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
for p in (SRC, ROOT / "packages" / "fengji_core"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

PLOT = ROOT / "scripts" / "plot_ds01_audit_sandbox.py"


def load_pending_row(pending_csv: Path, symbol: str, strategy: str) -> dict | None:
    if not pending_csv.is_file():
        return None
    with pending_csv.open(encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            row = {k.strip(): v for k, v in row.items()}
            if row.get("symbol", "").upper() == symbol.upper() and row.get("strategy_id", "").upper() == strategy:
                if not row.get("order_id"):
                    row["order_id"] = row.get("setup_key", "").split("|")[0] or None
                return row
    return None


def load_open_position(paper_state: Path, symbol: str) -> dict | None:
    ps = json.loads(paper_state.read_text(encoding="utf-8"))
    st = (ps.get("symbols") or {}).get(symbol.upper()) or {}
    op = st.get("open_position")
    if not isinstance(op, dict):
        return None
    leg = (op.get("legs") or [{}])[0]
    return {
        "strategy_id": str(op.get("strategy_id", "")).upper(),
        "side": str(op.get("direction", "long")).lower(),
        "entry_time": str(op.get("entry_time", "")),
        "entry_price": float(op.get("entry_price") or 0),
        "trigger_price": float(leg.get("trigger_price") or op.get("entry_price") or 0),
        "stop_price": float(op.get("initial_stop") or leg.get("initial_stop") or 0),
        "order_id": str(op.get("order_id") or ""),
    }


def pick_d1(data_dir: Path, symbol: str) -> Path:
    cands = [
        data_dir / "overseas_1d" / f"{symbol}.csv",
        data_dir / "1d" / f"{symbol}.csv",
    ]
    found = [p for p in cands if p.is_file()]
    if not found:
        raise FileNotFoundError(f"no D1 for {symbol}")
    return found[0]


def plot_pending(row: dict, csv_path: Path, png: Path, *, title: str) -> None:
    signal_date = (row.get("latest_time") or row.get("signal_time") or row.get("created_at") or "")[:10]
    if not signal_date:
        signal_date = "2026-06-15"
    import pandas as pd

    df = pd.read_csv(csv_path)
    if "timestamp" in df.columns and "date" not in df.columns:
        df = df.rename(columns={"timestamp": "date"})
    df["date"] = pd.to_datetime(df["date"])
    target = pd.to_datetime(signal_date).normalize()
    eligible = df[pd.to_datetime(df["date"]).dt.normalize() <= target]
    if not eligible.empty:
        signal_date = str(eligible["date"].iloc[-1])[:10]
    entry_dt = datetime.strptime(signal_date[:10], "%Y-%m-%d")
    side = str(row.get("side", "long")).lower()
    trigger = float(row.get("trigger_price") or 0)
    stop = float(row.get("stop_price") or 0)
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
            side,
            "--entry-date",
            signal_date[:10],
            "--fill-price",
            str(trigger),
            "--start",
            (entry_dt - timedelta(days=90)).strftime("%Y-%m-%d"),
            "--end",
            datetime.now().strftime("%Y-%m-%d"),
            "--out",
            str(png),
            "--verdict",
            title,
        ],
        check=True,
        cwd=str(ROOT),
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbol", default="HYPEUSDT")
    parser.add_argument("--paper-state", default=str(ROOT / "runtime/overseas_paper_state.json"))
    parser.add_argument("--pending-csv", default=str(ROOT / "runtime/overseas_pending_orders/pending_orders.csv"))
    parser.add_argument("--data-dir", default=str(ROOT / "data"))
    parser.add_argument("--out-dir", default=str(ROOT / "results/hype_ds06_combo_review_20260621"))
    args = parser.parse_args()

    sym = args.symbol.upper()
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    ds06 = load_pending_row(Path(args.pending_csv), sym, "DS06")
    ds03 = load_open_position(Path(args.paper_state), sym)
    csv_path = pick_d1(Path(args.data_dir), sym)

    report: dict = {"symbol": sym, "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
    issues: list[str] = []

    if not ds06:
        issues.append("no DS06 pending row")
    if not ds03 or ds03.get("strategy_id") != "DS03":
        issues.append("no DS03 open_position")

    if ds06 and ds03:
        t6 = round(float(ds06.get("trigger_price") or 0), 6)
        t3 = round(float(ds03.get("trigger_price") or 0), 6)
        s6 = round(float(ds06.get("stop_price") or 0), 6)
        s3 = round(float(ds03.get("stop_price") or 0), 6)
        same_trigger = t6 == t3
        same_stop = s6 == s3
        same_side = str(ds06.get("side", "")).lower() == ds03.get("side")
        report["ds06_pending"] = {
            "order_id": ds06.get("order_id"),
            "status": ds06.get("status"),
            "trigger": t6,
            "stop": s6,
            "side": ds06.get("side"),
            "signal_time": ds06.get("latest_time") or ds06.get("created_at"),
            "note": ds06.get("note") or ds06.get("reason"),
        }
        report["ds03_open"] = ds03
        report["comparison"] = {
            "same_trigger": same_trigger,
            "same_stop": same_stop,
            "same_side": same_side,
            "verdict": "combo_review" if same_trigger and same_side else "distinct_trigger",
        }
        if same_trigger and same_side:
            report["ruling"] = (
                "DS06 与 DS03 同品种同向同触发价/止损；DS03 已成交，DS06 仍为 READY_TRIGGERED。"
                "按 S3：导出期 DS06/DS03 同结构去重；持仓期第二笔同价 fill 应由 cross-strategy 去重或监控层拦截。"
            )
        else:
            report["ruling"] = "独立触发价 DS06 — 符合 S3 允许单独 pending 观察案例。"

        png_ds03 = out_dir / f"{sym}_DS03_open.png"
        png_ds06 = out_dir / f"{sym}_DS06_pending.png"
        plot_pending(
            {**ds06, "symbol": sym},
            csv_path,
            png_ds06,
            title=f"DS06 {ds06.get('status')} trigger={t6} combo={'same' if same_trigger else 'diff'} vs DS03",
        )
        plot_pending(
            {
                "symbol": sym,
                "side": ds03["side"],
                "signal_time": ds03["entry_time"],
                "trigger_price": ds03["trigger_price"],
                "stop_price": ds03["stop_price"],
            },
            csv_path,
            png_ds03,
            title=f"DS03 OPEN fill={ds03['entry_price']} trigger={t3}",
        )
        report["png"] = {"ds03": str(png_ds03), "ds06": str(png_ds06)}

    report["issues"] = issues
    (out_dir / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "# HYPE DS06 vs DS03 组合复核",
        "",
        f"生成：{report['generated_at']}",
        "",
    ]
    if issues:
        lines.append("## 问题\n")
        for i in issues:
            lines.append(f"- {i}")
    else:
        c = report["comparison"]
        lines.extend(
            [
                "## 结论",
                "",
                f"- **裁定**：`{c['verdict']}`",
                f"- DS03 OPEN：`{report['ds03_open']['order_id']}` @ {report['ds03_open']['entry_price']}",
                f"- DS06 pending：`{report['ds06_pending']['order_id']}` · **{report['ds06_pending']['status']}**",
                f"- 触发价：DS03={report['ds03_open']['trigger_price']} · DS06={report['ds06_pending']['trigger']} · same={c['same_trigger']}",
                f"- 止损：DS03={report['ds03_open']['stop_price']} · DS06={report['ds06_pending']['stop']} · same={c['same_stop']}",
                "",
                report.get("ruling", ""),
                "",
                "## 沙盒",
                "",
                f"- DS03：`{Path(report['png']['ds03']).name}`",
                f"- DS06：`{Path(report['png']['ds06']).name}`",
                "",
                "## 建议",
                "",
                "- **不改 OS/定式规则**；维持 Wave4 S3 裁定",
                "- 若 DS06 同价再次触发 fill：挂单监控应 cross-strategy 去重（仅保留优先级更高的一笔）",
                "- 本案例归档为「同触发价 DS06 观察」；真正独立触发价案例仍待后续 radar 日志",
            ]
        )
    (out_dir / "SUMMARY.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print((out_dir / "SUMMARY.md").read_text(encoding="utf-8"))
    return 0 if not issues else 1


if __name__ == "__main__":
    raise SystemExit(main())
