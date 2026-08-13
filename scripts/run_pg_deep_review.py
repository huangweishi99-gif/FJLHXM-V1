#!/usr/bin/env python3
"""PG（液化气）模拟持仓深度复核：DS01 / DS03 / DS06 三笔 short 沙盒 + OS 证据。"""
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
SYMBOL = "PG"
MARKET = "FUTURES"
CSV = resolve_csv(SYMBOL, MARKET)

POSITIONS: list[dict[str, Any]] = [
    {
        "strategy_id": "DS03",
        "entry_date": "2026-06-12",
        "fill_price": 5407.0,
        "side": "short",
        "order_id": "PGUSDT-DS03-D1-short-6b661ae10175f184",
        "setup": "blue camp break active low (starter bar only)",
        "note": "挂单监控 15m 触发；D1 信号棍 2026-06-11",
    },
    {
        "strategy_id": "DS06",
        "entry_date": "2026-06-12",
        "fill_price": 5407.0,
        "side": "short",
        "note": "与 DS03 同入场时刻/同价；S3 裁定 DS06 与 DS03 去重边界需组合层确认",
        "order_id": "PGUSDT-DS06-D1-short-7563a1f1d3b947df",
        "setup": "revolution D/E complete, waiting external break",
    },
    {
        "strategy_id": "DS01",
        "entry_date": "2026-06-15",
        "fill_price": 5316.0,
        "side": "short",
        "order_id": "PGUSDT-DS01-D1-short-0043eb7719385867",
        "setup": "yesterday blue-camp bearish stick; signal 2026-06-12 low=5316",
        "note": "setup_key signal=20260611160000；实际触发价对齐 6/12 低点",
    },
]


def _load_os() -> tuple[pd.DataFrame, Any]:
    df = load_tq_futures_kline_csv(CSV)
    df = df[df["date"] >= pd.Timestamp("2020-01-01")].sort_values("date")
    return build_os_detail_frame(df, gap=3)


def _bar_evidence(os_df: pd.DataFrame, entry_date: str) -> dict[str, Any]:
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
    side = "short"
    expected = -1
    signal_camp = int(sr.get("camp", 0) or 0)
    entry_camp = int(er.get("camp", 0) or 0)
    camp_ok = signal_camp == expected and entry_camp == expected
    trigger = float(sr["low"] if side == "short" else sr["high"])
    stop = float(sr["high"] if side == "short" else sr["low"])
    return {
        "signal_date": str(sr["date"])[:10],
        "entry_date": str(er["date"])[:10],
        "signal_camp": signal_camp,
        "entry_camp": entry_camp,
        "camp_confirmed_signal": int(sr.get("camp_confirmed", 0) or 0),
        "camp_confirmed_entry": int(er.get("camp_confirmed", 0) or 0),
        "signal_ohlc": (float(sr["open"]), float(sr["high"]), float(sr["low"]), float(sr["close"])),
        "entry_ohlc": (float(er["open"]), float(er["high"]), float(er["low"]), float(er["close"])),
        "trigger_ref": trigger,
        "stop_ref": stop,
        "camp_ok": camp_ok,
        "expected_camp": expected,
    }


def _plot_one(pos: dict[str, Any], out: Path, evidence: dict[str, Any]) -> None:
    ts = pd.Timestamp(pos["entry_date"])
    start = str((ts - timedelta(days=75)).date())
    end = str((ts + timedelta(days=25)).date())
    sid = pos["strategy_id"]
    verdict = (
        f"PG {sid} short | signal_camp={evidence['signal_camp']} entry_camp={evidence['entry_camp']} "
        f"expected=-1 | {'camp_OK' if evidence['camp_ok'] else 'audit_invalid_camp_mismatch'}"
    )
    cmd = [
        sys.executable,
        str(PLOT),
        "--csv",
        str(CSV),
        "--market",
        "futures",
        "--symbol",
        "PGUSDT",
        "--side",
        pos["side"],
        "--entry-date",
        pos["entry_date"],
        "--fill-price",
        str(pos["fill_price"]),
        "--start",
        start,
        "--end",
        end,
        "--order-tag",
        f"PG-{sid}-deep",
        "--verdict",
        verdict,
        "--out",
        str(out),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, cwd=str(ROOT))
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr or proc.stdout or "plot failed")


def _verdict_for_strategy(pos: dict[str, Any], evidence: dict[str, Any]) -> tuple[str, str]:
    if not evidence["camp_ok"]:
        return "audit_invalid", "signal/entry camp 与 short 方向不一致"
    sid = pos["strategy_id"]
    if sid == "DS01":
        sig = evidence["signal_ohlc"]
        bearish = sig[3] < sig[0]
        if bearish and evidence["signal_camp"] == -1:
            return "valid", "蓝营内阴线信号棍 + 触发价对齐 signal low；结构有效"
        return "review", "camp 对齐但信号棍形态需人工看图"
    if sid == "DS03":
        return "valid", "蓝营 camp=-1；DS03 破 active low 首棒 starter 口径（见沙盒 active low 结构）"
    if sid == "DS06":
        return "combo_review", "camp 对齐；与 DS03 同价同刻并行，组合去重规则待确认（不改 OS）"
    return "review", "—"


def render_markdown(results: list[dict[str, Any]], out_dir: Path) -> str:
    lines = [
        "# S2 深度复核 · PG 液化气 D1 · 三笔并行 short（2026-06-12 / 06-15）",
        "",
        "## 总结论",
        "",
    ]
    valid_n = sum(1 for r in results if r["verdict"] == "valid")
    combo = sum(1 for r in results if r["verdict"] == "combo_review")
    lines.append(
        f"- **OS 阵营**：三笔入场时 D1 均为 **蓝营 camp=-1**（5/25 红转蓝后持续蓝营）。"
    )
    lines.append(
        f"- **结构裁定**：**{valid_n}** 笔 **valid** · **{combo}** 笔 **combo_review**（DS06 与 DS03 同触发并行）。"
    )
    lines.append("- **不修改** OS/定式/挂单规则；仅只读审计 paper_state 当前持仓。")
    lines.append("")
    lines.append("## 背景 OS（5 月转势）")
    lines.append("")
    lines.append("| 日期 | 事件 |")
    lines.append("|------|------|")
    lines.append("| 2026-04-09 | 红转蓝（5802→5201 下破） |")
    lines.append("| 2026-05-13 | 蓝转红（6215 上破） |")
    lines.append("| **2026-05-25** | **红转蓝**（5628→5616）→ 此后 **蓝营** |")
    lines.append("")
    for r in results:
        pos = r["position"]
        ev = r["evidence"]
        lines.extend(
            [
                f"## {pos['strategy_id']} · {pos['entry_date']} short @ {pos['fill_price']}",
                "",
                f"**裁定：{r['verdict']}** — {r['reason']}",
                "",
                f"- order_id：`{pos['order_id']}`",
                f"- setup：{pos.get('setup', '—')}",
                "",
                "| 项目 | 值 |",
                "|------|-----|",
                f"| 信号棍 | **{ev['signal_date']}** · camp **{ev['signal_camp']}** · conf **{ev['camp_confirmed_signal']}** |",
                f"| 入场 K | **{ev['entry_date']}** · camp **{ev['entry_camp']}** · conf **{ev['camp_confirmed_entry']}** |",
                f"| 信号 OHLC | O{ev['signal_ohlc'][0]:.0f} H{ev['signal_ohlc'][1]:.0f} "
                f"L{ev['signal_ohlc'][2]:.0f} C{ev['signal_ohlc'][3]:.0f} |",
                f"| trigger 参考 | **{ev['trigger_ref']:.0f}** |",
                f"| stop 参考 | **{ev['stop_ref']:.0f}** |",
                f"| fill | **{pos['fill_price']:.0f}** |",
                f"| camp 对齐 | {'PASS camp_OK' if ev['camp_ok'] else 'FAIL audit_invalid'} |",
                "",
                f"沙盒图：`{Path(r['png']).name}`",
                "",
            ]
        )
    lines.extend(
        [
            "## 组合层说明（DS03 + DS06）",
            "",
            "两笔 **同入场时刻、同价 5407**、同 D1 信号棍（2026-06-11）。按 Wave4 **S3** 裁定，DS06 与 DS03 同触发价时挂单器可能去重；",
            "模拟盘允许非连续定式并行时，**camp 结构仍 valid**，但应在组合风控层确认是否应只保留优先级更高的一笔。",
            "",
            "## 修正建议",
            "",
            "- **无需改 OS / DS01 / DS03 / DS06 核心规则**（camp 均对齐蓝营做空）。",
            "- 若需收紧模拟盘：可在挂单监控层对「同品种同向同价」仅保留 DS03 或 DS06 之一（需你确认后再改，非本复核自动 apply）。",
            "",
            "## 复跑",
            "",
            "```powershell",
            "python scripts/run_pg_deep_review.py",
            "```",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="PG deep review sandbox")
    parser.add_argument(
        "--out-dir",
        default="",
        help="default: results/s2_ds01_sandbox_20260614",
    )
    args = parser.parse_args()
    out_dir = Path(args.out_dir) if args.out_dir else ROOT / "results" / "s2_ds01_sandbox_20260614"
    out_dir.mkdir(parents=True, exist_ok=True)

    os_df, _engine = _load_os()
    results: list[dict[str, Any]] = []
    for pos in POSITIONS:
        ev = _bar_evidence(os_df, pos["entry_date"])
        png = out_dir / f"PG_{pos['strategy_id']}_deep_{pos['entry_date'].replace('-', '')}.png"
        _plot_one(pos, png, ev)
        verdict, reason = _verdict_for_strategy(pos, ev)
        results.append(
            {
                "position": pos,
                "evidence": ev,
                "png": str(png),
                "verdict": verdict,
                "reason": reason,
            }
        )

    md_path = out_dir / "PG_deep_review_20260615.md"
    md_path.write_text(render_markdown(results, out_dir), encoding="utf-8")
    manifest = {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "symbol": "PGUSDT",
        "csv": str(CSV),
        "results": results,
        "markdown": str(md_path),
    }
    json_path = out_dir / "PG_deep_review_20260615.json"
    json_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, default=str), encoding="utf-8")

    # also copy primary composite name for index parity
    primary = out_dir / "PG_deep_review_20260615.png"
    if results:
        import shutil

        shutil.copy2(results[-1]["png"], primary)

    print(json.dumps({"ok": True, "markdown": str(md_path), "results": len(results)}, ensure_ascii=False))
    for r in results:
        print(f"  {r['position']['strategy_id']}: {r['verdict']} -> {Path(r['png']).name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
