#!/usr/bin/env python3
"""Audit + sandbox charts for new-10 crypto pending→paper fills (overseas)."""
from __future__ import annotations

import argparse
import json
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

NEW10 = {
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

PLOT_DS03 = ROOT / "scripts" / "plot_live_ds03_sandbox.py"
PLOT_GENERIC = ROOT / "scripts" / "plot_ds01_audit_sandbox.py"
AUDIT_FILLS = ROOT / "scripts" / "audit_paper_fills.py"


def symbol_to_csv(data_dir: Path, symbol: str) -> Path:
    base = symbol.replace("USDT", "")
    candidates = [
        data_dir / "overseas_1d" / f"{symbol}.csv",
        data_dir / "1d" / f"{symbol}.csv",
        data_dir / "crypto_okx" / f"{base}-USDT_1D_1825d.csv",
    ]
    for path in candidates:
        if path.exists():
            return path
    raise FileNotFoundError(f"no D1 csv for {symbol}")


def collect_positions(paper_state: dict) -> list[dict]:
    rows: list[dict] = []
    for symbol, symbol_state in (paper_state.get("symbols") or {}).items():
        if symbol not in NEW10:
            continue
        pos = (symbol_state or {}).get("open_position")
        if not pos:
            continue
        rows.append(_position_row(symbol, pos))
    return rows


def _position_row(symbol: str, pos: dict) -> dict:
    return {
        "symbol": symbol,
        "strategy_id": str(pos.get("strategy_id", "")).upper(),
        "side": str(pos.get("direction", "long" if int(pos.get("side", 0) or 0) == 1 else "short")).lower(),
        "entry_time": str(pos.get("entry_time", "")),
        "entry_date": str(pos.get("entry_time", ""))[:10],
        "entry_price": float(pos.get("entry_price", 0) or 0),
        "trigger_price": float((pos.get("legs") or [{}])[0].get("trigger_price", pos.get("entry_price", 0)) or 0),
        "stop_price": float(pos.get("initial_stop", 0) or 0),
        "order_id": str(pos.get("order_id", "")),
        "status": "OPEN",
    }


def collect_fills_from_events(events_path: Path, order_ids: set[str]) -> list[dict]:
    if not order_ids or not events_path.is_file():
        return []
    rows: list[dict] = []
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
        if side_raw in {"long", "buy", "1", "1.0"}:
            side = "long"
        elif side_raw in {"short", "sell", "-1", "-1.0"}:
            side = "short"
        else:
            side = side_raw or "short"
        fill_price = float(obj.get("fill_price", 0) or obj.get("entry_price", 0) or 0)
        bar_time = str(obj.get("bar_time") or obj.get("time") or "")
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
                "status": "CLOSED_OR_FILLED",
            }
        )
    return rows


def merge_positions(*groups: list[dict]) -> list[dict]:
    merged: dict[str, dict] = {}
    for group in groups:
        for row in group:
            key = str(row.get("order_id") or "") or f"{row.get('symbol')}|{row.get('strategy_id')}|{row.get('entry_time')}"
            merged[key] = row
    return list(merged.values())


def resolve_plot_entry_date(csv_path: Path, entry_date: str) -> str:
    """Use last available D1 bar on/before entry when CSV lags (e.g. HYPE OKX)."""
    df = pd.read_csv(csv_path)
    if "timestamp" in df.columns and "date" not in df.columns:
        df = df.rename(columns={"timestamp": "date"})
    df["date"] = pd.to_datetime(df["date"])
    target = pd.to_datetime(entry_date).normalize()
    eligible = df[pd.to_datetime(df["date"]).dt.normalize() <= target]
    if eligible.empty:
        return str(df["date"].iloc[-1])[:10]
    return str(eligible["date"].iloc[-1])[:10]


def plot_fill(row: dict, csv_path: Path, out: Path, *, data_dir: Path) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    strategy = row["strategy_id"]
    use_ds03_plot = strategy == "DS03" and PLOT_DS03.exists()
    if use_ds03_plot:
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
        proc = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True)
        if proc.returncode == 0:
            return
    plot_date = resolve_plot_entry_date(csv_path, row["entry_date"])
    entry_dt = datetime.strptime(plot_date, "%Y-%m-%d")
    start = (entry_dt - timedelta(days=90)).strftime("%Y-%m-%d")
    cmd = [
        sys.executable,
        str(PLOT_GENERIC),
        "--market",
        "crypto",
        "--csv",
        str(csv_path),
        "--symbol",
        row["symbol"],
        "--side",
        row["side"],
        "--entry-date",
        plot_date,
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
        f"{strategy} pending fill {row['entry_time']} plot_date={plot_date}",
    ]
    subprocess.run(cmd, check=True, cwd=str(ROOT))


def resolve_overseas_events_path(hours: int) -> Path:
    """Prefer lightweight SSH-synced fill slice; avoid full ~700MB events.jsonl scp."""
    synced = ROOT / "runtime" / "fengji_pending_orders" / f"events_overseas_fills_{hours}h.jsonl"
    if synced.exists() and synced.stat().st_size > 0:
        return synced
    fallback = ROOT / "runtime" / "fengji_pending_orders" / "events.jsonl"
    if fallback.exists() and fallback.stat().st_size > 0:
        return fallback
    return synced


def sync_overseas_fill_events(hours: int) -> Path | None:
    sync_py = ROOT / "scripts" / "sync_overseas_fill_events.py"
    if not sync_py.exists():
        return None
    proc = subprocess.run(
        [sys.executable, str(sync_py), "--since-hours", str(hours)],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        return None
    path = resolve_overseas_events_path(hours)
    return path if path.exists() and path.stat().st_size > 0 else None


def run_fill_audit(out_dir: Path, *, hours: int, events_path: Path | None = None) -> dict:
    if events_path is None:
        events_path = resolve_overseas_events_path(hours)
        if not events_path.exists() or events_path.stat().st_size == 0:
            synced = sync_overseas_fill_events(hours)
            if synced is not None:
                events_path = synced

    cmd = [
        sys.executable,
        str(AUDIT_FILLS),
        "--profile",
        "overseas",
        "--since-hours",
        str(hours),
        "--out-dir",
        str(out_dir / "fill_supervision"),
    ]
    if events_path is not None and events_path.exists() and events_path.stat().st_size > 0:
        cmd.extend(["--events", str(events_path)])

    subprocess.run(cmd, cwd=str(ROOT))
    latest = out_dir / "fill_supervision" / "fill_supervision_overseas_latest.json"
    if latest.exists():
        return json.loads(latest.read_text(encoding="utf-8"))
    return {}


def _filter_new10_audit_rows(audit: dict) -> list[dict]:
    rows = audit.get("all_results") or []
    if not rows:
        rows = (audit.get("valid_fills") or []) + (audit.get("invalid_fills") or [])
    return [r for r in rows if str(r.get("symbol", "")).upper() in NEW10]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--paper-state", default=str(ROOT / "runtime/overseas_paper_state.json"))
    parser.add_argument("--data-dir", default=str(ROOT / "data"))
    parser.add_argument("--out-dir", default=str(ROOT / "results/new10_crypto_fills_audit"))
    parser.add_argument("--hours", type=int, default=720)
    parser.add_argument("--no-plot", action="store_true")
    parser.add_argument("--no-audit", action="store_true")
    parser.add_argument("--only-symbols", default="", help="comma-separated; plot/audit subset only (watch new fills)")
    parser.add_argument("--order-ids", default="", help="comma-separated order_id; include closed fills from events.jsonl")
    args = parser.parse_args()

    paper_state = json.loads(Path(args.paper_state).read_text(encoding="utf-8"))
    hours = int(args.hours)
    events_path = resolve_overseas_events_path(hours)
    if not events_path.exists() or events_path.stat().st_size == 0:
        synced = sync_overseas_fill_events(hours)
        if synced is not None:
            events_path = synced

    order_ids = {item.strip() for item in args.order_ids.split(",") if item.strip()}
    positions = merge_positions(
        collect_positions(paper_state),
        collect_fills_from_events(events_path, order_ids),
    )
    only = {s.strip().upper() for s in args.only_symbols.split(",") if s.strip()}
    if only:
        positions = [p for p in positions if p["symbol"] in only]
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    data_dir = Path(args.data_dir)

    lines = [
        "# 新 10 crypto pending→paper 成交审计",
        "",
        f"生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"paper_state：`{args.paper_state}`",
        "",
        f"## 当前持仓（new10 内）· {len(positions)} 笔",
        "",
    ]

    for row in positions:
        tag = f"{row['symbol']}_{row['strategy_id']}_{row['side']}"
        lines.append(f"### {tag}")
        lines.append(f"- order_id: `{row['order_id']}`")
        lines.append(f"- entry: {row['entry_time']} @ {row['entry_price']}")
        lines.append(f"- trigger/stop: {row['trigger_price']} / {row['stop_price']}")
        png = out_dir / f"{tag}.png"
        try:
            csv_path = symbol_to_csv(data_dir, row["symbol"])
            if not args.no_plot:
                plot_fill(row, csv_path, png, data_dir=data_dir)
                lines.append(f"- 沙盒图：`{png.name}`")
            lines.append(f"- 状态：**{row.get('status', 'OPEN')}**")
        except Exception as exc:
            lines.append(f"- 沙盒/数据：**SKIP** — {exc}")
        lines.append("")

    if not args.no_audit:
        audit = run_fill_audit(out_dir, hours=hours, events_path=events_path if events_path.exists() else None)
        new10_audit = _filter_new10_audit_rows(audit)
        events_note = resolve_overseas_events_path(int(args.hours))
        lines.extend(
            [
                "## fill_supervision（new10 子集）",
                "",
                f"- 窗口：{args.hours}h · events=`{events_note}` · 合计 new10 fills={len(new10_audit)}",
            ]
        )
        for r in new10_audit:
            lines.append(
                f"- {r.get('symbol')} {r.get('strategy_id')} {r.get('side')} "
                f"→ **{r.get('verdict', r.get('status', '?'))}**"
            )
        (out_dir / "fill_audit_new10_subset.json").write_text(
            json.dumps(new10_audit, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    summary = out_dir / "SUMMARY.md"
    summary.write_text("\n".join(lines), encoding="utf-8")
    print(summary.read_text(encoding="utf-8"))
    print(f"saved {summary}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
