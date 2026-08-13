#!/usr/bin/env python3
"""Refresh ATHUSDT DS03 trigger distance from local pending/radar snapshot."""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load_json(path: Path) -> dict:
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    symbol = "ATHUSDT"
    pending_paths = [
        ROOT / "runtime" / "overseas_pending_orders" / "pending_orders.json",
        ROOT / "runtime" / "fengji_pending_orders" / "pending_orders.json",
    ]
    radar_paths = [
        ROOT / "runtime" / "overseas_radar_snapshot.json",
        ROOT / "runtime" / "fengji_radar" / "radar.json",
    ]

    pending_rows: list[dict] = []
    for path in pending_paths:
        data = load_json(path)
        rows = data.get("orders") if isinstance(data, dict) else data
        if isinstance(rows, list):
            pending_rows.extend(r for r in rows if str(r.get("symbol", "")).upper() == symbol)

    radar_rows: list[dict] = []
    for path in radar_paths:
        data = load_json(path)
        if isinstance(data, dict) and isinstance(data.get("rows"), list):
            radar_rows.extend(r for r in data["rows"] if str(r.get("symbol", "")).upper() == symbol)
        elif isinstance(data, list):
            radar_rows.extend(r for r in data if str(r.get("symbol", "")).upper() == symbol)

    ds03 = [r for r in pending_rows + radar_rows if str(r.get("strategy_id", "")).upper() == "DS03"]
    out_dir = ROOT / "results" / "ath_status_20260624"
    out_dir.mkdir(parents=True, exist_ok=True)

    lines = [
        "# ATHUSDT DS03 触发距离快照",
        "",
        f"生成：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        f"- pending DS03 行数：**{len([r for r in pending_rows if str(r.get('strategy_id','')).upper()=='DS03'])}**",
        f"- radar DS03 行数：**{len([r for r in radar_rows if str(r.get('strategy_id','')).upper()=='DS03'])}**",
        "",
    ]
    for row in ds03[:5]:
        dist = row.get("distance_pct")
        trig = row.get("trigger_price")
        cur = row.get("current_price")
        lines.append(
            f"- {row.get('strategy_id')} {row.get('side')} status={row.get('status')} "
            f"trigger={trig} current={cur} distance_pct={dist}"
        )
    if not ds03:
        lines.append("- 本地无 ATH DS03 pending/radar 行（可能仅在海外服务器）")

    md = "\n".join(lines) + "\n"
    (out_dir / "ATH_DS03_DISTANCE.md").write_text(md, encoding="utf-8")
    print(md)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
