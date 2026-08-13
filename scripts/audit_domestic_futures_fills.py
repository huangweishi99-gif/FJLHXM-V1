#!/usr/bin/env python3
"""Audit + sandbox charts for domestic futures pending→paper fills (DS02–DS09)."""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
if str(ROOT / "packages" / "fengji_core") not in sys.path:
    sys.path.insert(0, str(ROOT / "packages" / "fengji_core"))

from fengji_core.fill_supervision import infer_record_timeframe, resolve_ohlcv_csv  # noqa: E402

PLOT_DS03 = ROOT / "scripts" / "plot_live_ds03_sandbox.py"
PLOT_GENERIC = ROOT / "scripts" / "plot_ds01_audit_sandbox.py"
AUDIT_FILLS = ROOT / "scripts" / "audit_paper_fills.py"
SYNC_EVENTS = ROOT / "scripts" / "sync_domestic_fill_events.py"
DS_STRATEGIES = {f"DS0{i}" for i in range(2, 10)}


def strategy_timeframe(strategy_id: str, record: dict | None = None) -> str:
    if record:
        tf = infer_record_timeframe(record)
        if tf:
            return tf
    sid = strategy_id.upper()
    if sid in {"DS07", "DS08"}:
        return "1h"
    if sid == "DS09":
        return "15m"
    if sid in {"DS04", "DS06"}:
        return "1h"
    return "1d"


def symbol_to_csv(data_dir: Path, symbol: str, timeframe: str) -> Path:
    path = resolve_ohlcv_csv(data_dir, symbol.upper(), timeframe, market="domestic")
    if path is None or not path.exists():
        base = symbol.upper().replace("USDT", "")
        raise FileNotFoundError(f"no {timeframe} csv for {symbol} under {data_dir} (tried {base})")
    return path


def sync_csv_from_remote(symbol: str, timeframe: str, *, ssh_host: str, remote_root: str) -> bool:
    base = symbol.upper().replace("USDT", "")
    local_dir = ROOT / "data" / timeframe
    local_dir.mkdir(parents=True, exist_ok=True)
    local_path = local_dir / f"{base}.csv"
    remote = f"{remote_root.replace(chr(92), '/')}/data/{timeframe}/{base}.csv"
    proc = subprocess.run(
        ["scp", "-o", "BatchMode=yes", "-o", "ConnectTimeout=20", f"{ssh_host}:{remote}", str(local_path)],
        capture_output=True,
        text=True,
    )
    return proc.returncode == 0 and local_path.exists()


def collect_fills_from_events(events_path: Path, order_ids: set[str]) -> list[dict]:
    rows: list[dict] = []
    if not order_ids or not events_path.is_file():
        return rows
    for line in events_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if str(obj.get("event_type", "")).lower() != "fill":
            continue
        order_id = str(obj.get("order_id", "")).strip()
        if order_id not in order_ids:
            continue
        symbol = str(obj.get("symbol", "")).upper().replace("-", "")
        if symbol and not symbol.endswith("USDT"):
            symbol = f"{symbol}USDT"
        side_raw = str(obj.get("side", "")).lower()
        side = "long" if side_raw in {"long", "buy", "1"} else "short"
        fill_price = float(obj.get("fill_price", 0) or 0)
        bar_time = str(obj.get("time") or obj.get("bar_time") or "")
        rows.append(
            {
                "symbol": symbol,
                "strategy_id": str(obj.get("strategy_id", "")).upper(),
                "side": side,
                "entry_time": bar_time,
                "entry_date": bar_time[:10] if bar_time else "",
                "entry_price": fill_price,
                "trigger_price": float(obj.get("trigger_price", fill_price) or fill_price),
                "stop_price": float(obj.get("stop_price", 0) or 0),
                "order_id": order_id,
                "status": "FILLED",
                "_record": obj,
            }
        )
    return rows


def resolve_plot_entry_date(csv_path: Path, entry_date: str) -> str:
    df = pd.read_csv(csv_path)
    if "timestamp" in df.columns and "date" not in df.columns:
        df = df.rename(columns={"timestamp": "date"})
    df["date"] = pd.to_datetime(df["date"])
    target = pd.to_datetime(entry_date)
    eligible = df[pd.to_datetime(df["date"]) <= target]
    if eligible.empty:
        return str(df["date"].iloc[-1])[:19]
    return str(eligible["date"].iloc[-1])[:19]


def plot_fill(row: dict, csv_path: Path, out: Path, *, data_dir: Path) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    strategy = row["strategy_id"]
    record = row.get("_record") or {}
    tf = strategy_timeframe(strategy, record)

    if strategy == "DS03" and PLOT_DS03.exists() and tf == "1d":
        staging = out.parent / "_staging" / "1d"
        staging.mkdir(parents=True, exist_ok=True)
        dest = staging / f"{row['symbol']}.csv"
        if not dest.exists():
            dest.write_bytes(csv_path.read_bytes())
        cmd = [
            sys.executable,
            str(PLOT_DS03),
            "--data-dir",
            str(staging.parent),
            "--symbol",
            row["symbol"],
            "--timeframe",
            "1d",
            "--date",
            row["entry_date"],
            "--side",
            row["side"],
            "--fill-price",
            str(row["entry_price"]),
            "--trigger-price",
            str(row["trigger_price"]),
            "--stop-price",
            str(row["stop_price"]),
            "--out",
            str(out),
        ]
        env = {**os.environ, "PYTHONPATH": f"{SRC};{ROOT / 'packages' / 'fengji_core'}"}
        proc = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True, env=env)
        if proc.returncode == 0:
            return

    plot_date = resolve_plot_entry_date(csv_path, row["entry_date"] or row["entry_time"])
    if len(plot_date) == 10:
        entry_dt = datetime.strptime(plot_date, "%Y-%m-%d")
        start = (entry_dt - timedelta(days=90)).strftime("%Y-%m-%d")
    else:
        entry_dt = pd.to_datetime(plot_date)
        start = (entry_dt - timedelta(days=30)).strftime("%Y-%m-%d")
    cmd = [
        sys.executable,
        str(PLOT_GENERIC),
        "--market",
        "futures",
        "--csv",
        str(csv_path),
        "--symbol",
        row["symbol"].replace("USDT", ""),
        "--side",
        row["side"],
        "--entry-date",
        plot_date[:10],
        "--fill-price",
        str(row["entry_price"]),
        "--start",
        start,
        "--end",
        datetime.now().strftime("%Y-%m-%d"),
        "--out",
        str(out),
        "--order-tag",
        strategy,
        "--verdict",
        f"{strategy} {tf} fill {row['entry_time']}",
    ]
    subprocess.run(cmd, check=True, cwd=str(ROOT))


def resolve_events_path(hours: int) -> Path:
    synced = ROOT / "runtime" / "fengji_pending_orders" / f"events_domestic_fills_{hours}h.jsonl"
    return synced


def sync_domestic_events(hours: int) -> Path | None:
    if not SYNC_EVENTS.exists():
        return None
    proc = subprocess.run(
        [sys.executable, str(SYNC_EVENTS), "--since-hours", str(hours)],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        return None
    path = resolve_events_path(hours)
    return path if path.exists() and path.stat().st_size > 0 else None


def run_fill_audit(out_dir: Path, *, hours: int, events_path: Path) -> dict:
    cmd = [
        sys.executable,
        str(AUDIT_FILLS),
        "--profile",
        "domestic",
        "--since-hours",
        str(hours),
        "--out-dir",
        str(out_dir / "fill_supervision"),
        "--events",
        str(events_path),
    ]
    subprocess.run(cmd, cwd=str(ROOT))
    latest = out_dir / "fill_supervision" / "fill_supervision_domestic_latest.json"
    if latest.exists():
        return json.loads(latest.read_text(encoding="utf-8"))
    return {}


def filter_ds_audit_rows(audit: dict, order_ids: set[str]) -> list[dict]:
    rows = audit.get("all_results") or []
    out = []
    for r in rows:
        if str(r.get("strategy_id", "")).upper() not in DS_STRATEGIES:
            continue
        if order_ids and str(r.get("order_id", "")) not in order_ids:
            continue
        out.append(r)
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", default=str(ROOT / "data"))
    parser.add_argument("--out-dir", default=str(ROOT / "results/domestic_futures_fills_audit"))
    parser.add_argument("--hours", type=int, default=168)
    parser.add_argument("--no-plot", action="store_true")
    parser.add_argument("--no-audit", action="store_true")
    parser.add_argument("--no-sync-csv", action="store_true")
    parser.add_argument("--ssh-host", default="domestic-quant")
    parser.add_argument("--remote-root", default="C:/Users/Administrator/quant_futures")
    parser.add_argument("--order-ids", required=True, help="comma-separated order_id list")
    args = parser.parse_args()

    hours = int(args.hours)
    order_ids = {x.strip() for x in args.order_ids.split(",") if x.strip()}
    events_path = resolve_events_path(hours)
    if not events_path.exists() or events_path.stat().st_size == 0:
        synced = sync_domestic_events(hours)
        if synced is not None:
            events_path = synced
    if not events_path.exists():
        print("events sync failed", file=sys.stderr)
        return 1

    positions = collect_fills_from_events(events_path, order_ids)
    if len(positions) != len(order_ids):
        found = {p["order_id"] for p in positions}
        missing = order_ids - found
        print(f"warn: missing order_ids in events: {missing}", file=sys.stderr)

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    data_dir = Path(args.data_dir)

    lines = [
        "# 国内期货 pending→paper 成交沙盒审计",
        "",
        f"生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"events：`{events_path}`",
        "",
        f"## 本批 · {len(positions)} 笔",
        "",
    ]

    for row in positions:
        tag = f"{row['symbol']}_{row['strategy_id']}_{row['side']}"
        tf = strategy_timeframe(row["strategy_id"], row.get("_record"))
        lines.append(f"### {tag}")
        lines.append(f"- order_id: `{row['order_id']}`")
        lines.append(f"- fill: {row['entry_time']} @ {row['entry_price']}")
        lines.append(f"- trigger/stop: {row['trigger_price']} / {row['stop_price']}")
        lines.append(f"- timeframe: **{tf}**")
        png = out_dir / f"{tag}.png"
        try:
            if not args.no_sync_csv:
                sync_csv_from_remote(
                    row["symbol"], tf, ssh_host=args.ssh_host, remote_root=args.remote_root
                )
            csv_path = symbol_to_csv(data_dir, row["symbol"], tf)
            if not args.no_plot:
                plot_fill(row, csv_path, png, data_dir=data_dir)
                lines.append(f"- 沙盒图：`{png.name}`")
        except Exception as exc:
            lines.append(f"- 沙盒/数据：**SKIP** — {exc}")
        lines.append("")

    if not args.no_audit:
        audit = run_fill_audit(out_dir, hours=hours, events_path=events_path)
        subset = filter_ds_audit_rows(audit, order_ids)
        lines.extend(["## fill_supervision（本批）", ""])
        for r in subset:
            issues = r.get("issues") or []
            extra = f" — {'; '.join(issues[:2])}" if issues else ""
            lines.append(
                f"- {r.get('symbol')} {r.get('strategy_id')} {r.get('side')} "
                f"→ **{r.get('verdict', '?')}**{extra}"
            )
        (out_dir / "fill_audit_subset.json").write_text(
            json.dumps(subset, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    summary = out_dir / "SUMMARY.md"
    summary.write_text("\n".join(lines), encoding="utf-8")
    print(summary.read_text(encoding="utf-8"))
    print(f"saved {summary}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
