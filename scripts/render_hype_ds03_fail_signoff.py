#!/usr/bin/env python3
"""Build HYPE DS03 6/18 paper-fill FAIL audit pack (structure PASS, entry_fill FAIL)."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results" / "hype_ds03_paper_fail_audit_20260624"
ORDER_ID = "HYPEUSDT-DS03-D1-long-95cbbeb8f98887f3"
FILL = {
    "symbol": "HYPEUSDT",
    "strategy_id": "DS03",
    "side": "long",
    "entry_time": "2026-06-18 00:15:07",
    "entry_date": "2026-06-18",
    "entry_price": 75.853,
    "trigger_price": 75.778,
    "stop_price": 59.666,
    "order_id": ORDER_ID,
    "price_source": "binance",
    "close_time": "2026-06-23 10:59:00",
    "close_price": 65.175,
    "close_reason": "stop",
}


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    staging = OUT / "_staging" / "1d"
    staging.mkdir(parents=True, exist_ok=True)
    src = ROOT / "data" / "overseas_1d" / "HYPEUSDT.csv"
    if not src.exists():
        src = ROOT / "data" / "1d" / "HYPEUSDT.csv"
    if not src.exists():
        print(f"missing HYPE csv: {src}", file=sys.stderr)
        return 1
    dest = staging / "HYPEUSDT.csv"
    dest.write_bytes(src.read_bytes())

    open_png = OUT / "HYPEUSDT_DS03_open_FAIL.png"
    cmd = [
        sys.executable,
        str(ROOT / "scripts" / "plot_live_ds03_sandbox.py"),
        "--data-dir",
        str(staging.parent),
        "--symbol",
        "HYPEUSDT",
        "--timeframe",
        "1d",
        "--date",
        "2026-06-15",
        "--side",
        "long",
        "--fill-price",
        str(FILL["entry_price"]),
        "--trigger-price",
        str(FILL["trigger_price"]),
        "--stop-price",
        str(FILL["stop_price"]),
        "--out",
        str(open_png),
    ]
    env = os.environ.copy()
    env["PYTHONPATH"] = os.pathsep.join([str(ROOT / "src"), str(ROOT / "packages" / "fengji_core")])
    subprocess.run(cmd, cwd=str(ROOT), check=True, env=env)

    meta = {**FILL, "generated_at": datetime.now().isoformat(timespec="seconds")}
    (OUT / "fill_meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    summary = f"""# HYPEUSDT DS03 · 6/18 paper 成交 FAIL 审计包

生成：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## 结论（项目裁定）

| 维度 | 裁定 |
|------|------|
| 信号结构（6/15 真峰） | **PASS** |
| 开仓执行（攻击棍 entry_fill） | **FAIL** — 6/18 为 ticker 触价成交，非攻击棍 |
| 离场止损（守四 65.175） | **PASS**（已平仓） |

## 成交事实

- order_id: `{ORDER_ID}`
- fill: {FILL['entry_time']} @ **{FILL['entry_price']}**（{FILL['price_source']}）
- trigger/stop: {FILL['trigger_price']} / {FILL['stop_price']}
- close: {FILL['close_time']} @ **{FILL['close_price']}** ({FILL['close_reason']})

## 沙盒

- 开仓复核：`HYPEUSDT_DS03_open_FAIL.png`（DS03 结构图，标注 FAIL 原因见 CHANGELOG 2026-06-23）

## 用户签收（非 VALID 成交）

请确认是否同意：**这笔模拟开仓不应视为合法 DS03 成交**（FAIL 裁定正确）。

| 签收项 | 填写 |
|--------|------|
| 同意 FAIL 裁定 | **FAIL_ACK** / 不同意 |
| 备注 | |

新规则（攻击棍 entry_fill）已上线；本笔为历史个案。
"""
    (OUT / "SUMMARY.md").write_text(summary, encoding="utf-8")
    print(summary)
    print(f"saved {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
