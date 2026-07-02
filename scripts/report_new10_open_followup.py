#!/usr/bin/env python3
"""Report new10 OPEN positions: stop vs monitor-aligned completed bar."""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))
if str(ROOT / "packages" / "fengji_core") not in sys.path:
    sys.path.insert(0, str(ROOT / "packages" / "fengji_core"))

from fengji_core.stop_bar_monitor import (  # noqa: E402
    filter_valid_price_rows,
    read_latest_bar,
    stop_bar_after_entry,
    stop_crossed,
    stop_timeframe_for_position,
)
from fengji_core.os_state_store import find_data_file  # noqa: E402
from fengji_core.runtime_stop_updater import stop_bar_requires_completed_close  # noqa: E402

import pandas as pd  # noqa: E402

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


def load_paper(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def position_side_token(position: dict[str, Any]) -> str:
    direction = str(position.get("direction") or position.get("side") or "").lower()
    if direction in {"1", "long"}:
        return "long"
    if direction in {"-1", "short"}:
        return "short"
    return direction


def read_post_entry_bar(data_dir: Path, symbol: str, position: dict[str, Any]) -> dict[str, Any] | None:
    """Latest bar at or after entry (audit display when monitor bar is pre-entry)."""
    timeframe = stop_timeframe_for_position(position)
    if not timeframe or stop_bar_requires_completed_close(timeframe):
        return None
    path = find_data_file(data_dir, symbol, timeframe)
    if not path.is_file():
        return None
    entry_time = pd.to_datetime(position.get("entry_time") or position.get("created_at"), errors="coerce")
    if pd.isna(entry_time):
        return None
    try:
        frame = pd.read_csv(path)
    except Exception:
        return None
    frame.columns = [str(c).strip().lower() for c in frame.columns]
    if "date" not in frame.columns:
        frame["date"] = frame.get("datetime", frame.iloc[:, 0])
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
    frame = filter_valid_price_rows(frame)
    if frame.empty:
        return None
    post = frame[frame["date"] >= entry_time]
    if post.empty:
        return None
    row = post.iloc[-1]
    return {
        "symbol": symbol,
        "timeframe": timeframe,
        "date": str(pd.to_datetime(row["date"]).strftime("%Y-%m-%d %H:%M:%S")),
        "open": float(row["open"]),
        "high": float(row["high"]),
        "low": float(row["low"]),
        "close": float(row["close"]),
        "bar_kind": "post_entry_latest",
    }


def read_pending_eval_bar(data_dir: Path, symbol: str, position: dict[str, Any]) -> dict[str, Any] | None:
    """When monitor still points at pre-entry completed D1, show latest CSV row if after entry day."""
    timeframe = stop_timeframe_for_position(position)
    tf = str(timeframe or "").lower()
    if tf not in {"1d", "d1", "day"}:
        return None
    path = find_data_file(data_dir, symbol, timeframe)
    if not path.is_file():
        return None
    entry_time = pd.to_datetime(position.get("entry_time") or position.get("created_at"), errors="coerce")
    if pd.isna(entry_time):
        return None
    try:
        frame = pd.read_csv(path)
    except Exception:
        return None
    frame.columns = [str(c).strip().lower() for c in frame.columns]
    if "date" not in frame.columns:
        frame["date"] = frame.get("datetime", frame.iloc[:, 0])
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
    frame = filter_valid_price_rows(frame)
    if len(frame) < 1:
        return None
    row = frame.iloc[-1]
    bar_time = pd.to_datetime(row["date"], errors="coerce")
    if pd.isna(bar_time) or bar_time.normalize() <= entry_time.normalize():
        return None
    return {
        "symbol": symbol,
        "timeframe": timeframe,
        "date": str(bar_time.strftime("%Y-%m-%d %H:%M:%S")),
        "open": float(row["open"]),
        "high": float(row["high"]),
        "low": float(row["low"]),
        "close": float(row["close"]),
        "bar_kind": "pending_eval_latest",
    }


def monitor_stop_bar(data_dir: Path, symbol: str, position: dict[str, Any]) -> dict[str, Any] | None:
    timeframe = stop_timeframe_for_position(position)
    if not timeframe:
        return None
    bar = read_latest_bar(
        data_dir,
        symbol,
        [timeframe],
        completed_only=stop_bar_requires_completed_close(timeframe),
    )
    if not bar:
        return None
    bar["bar_kind"] = "completed" if stop_bar_requires_completed_close(timeframe) else "latest"
    return bar


def stop_eval_note(position: dict[str, Any], bar: dict[str, Any] | None) -> str | None:
    """Human-readable hint when completed bar is not yet evaluable for stop."""
    if bar is None:
        return None
    if stop_bar_after_entry(position, bar):
        return None
    entry_time = pd.to_datetime(position.get("entry_time") or position.get("created_at"), errors="coerce")
    bar_time = pd.to_datetime(bar.get("date"), errors="coerce")
    if pd.isna(entry_time) or pd.isna(bar_time):
        return None
    tf = str(stop_timeframe_for_position(position) or "").lower()
    if tf in {"1d", "d1", "day"} and bar_time.normalize() == entry_time.normalize():
        return "入场当日 D1 整根 bar 不计止损（bar 时间戳为日初）；首根可判定 bar 为 **次日** 已完成 D1"
    if tf in {"15m", "m15"} and bar_time <= entry_time:
        return "本地 15m bar 早于/等于入场时刻；请 sync 15m 或参照海外 monitor（DS09 用最新 bar）"
    if bar_time <= entry_time:
        return "当前展示 bar 早于入场，仅参考"
    return None


def build_report(paper_state: dict, data_dir: Path) -> dict:
    rows: list[dict] = []
    for sym, st in sorted((paper_state.get("symbols") or {}).items()):
        if sym not in NEW10:
            continue
        op = (st or {}).get("open_position")
        if not op:
            continue
        strategy = str(op.get("strategy_id", "")).upper()
        tf = stop_timeframe_for_position(op) or "1h"
        bar = monitor_stop_bar(data_dir, sym, op)
        direction = position_side_token(op)
        item: dict[str, Any] = {
            "symbol": sym,
            "strategy_id": strategy,
            "timeframe": str(tf).upper(),
            "direction": direction,
            "order_id": op.get("order_id"),
            "entry_time": op.get("entry_time"),
            "entry_price": op.get("entry_price"),
            "current_stop": op.get("current_stop") or op.get("initial_stop"),
            "stop_bar": bar,
        }
        if bar:
            after_entry = stop_bar_after_entry(op, bar)
            breached_raw = bool(stop_crossed(op, bar))
            item["after_entry"] = after_entry
            item["stop_check"] = {
                "breached_on_bar": breached_raw,
                "breached_effective": bool(after_entry and breached_raw),
                "close": bar.get("close"),
                "high": bar.get("high"),
                "low": bar.get("low"),
                "bar_kind": bar.get("bar_kind"),
            }
            note = stop_eval_note(op, bar)
            if note:
                item["stop_eval_note"] = note
            post_bar = read_post_entry_bar(data_dir, sym, op)
            if post_bar:
                item["post_entry_bar"] = post_bar
                item["post_entry_stop_check"] = {
                    "breached_on_bar": bool(stop_crossed(op, post_bar)),
                    "breached_effective": bool(stop_crossed(op, post_bar)),
                    "high": post_bar.get("high"),
                    "low": post_bar.get("low"),
                    "close": post_bar.get("close"),
                }
            pending_bar = read_pending_eval_bar(data_dir, sym, op)
            if pending_bar:
                item["pending_eval_bar"] = pending_bar
                item["pending_eval_stop_check"] = {
                    "breached_on_bar": bool(stop_crossed(op, pending_bar)),
                    "breached_effective": bool(stop_bar_after_entry(op, pending_bar) and stop_crossed(op, pending_bar)),
                    "high": pending_bar.get("high"),
                    "low": pending_bar.get("low"),
                    "close": pending_bar.get("close"),
                }
        elif stop_timeframe_for_position(op):
            tf_label = str(stop_timeframe_for_position(op) or "")
            item["stop_eval_note"] = f"本地缺少 {tf_label} CSV，无法展示 stop bar（海外 monitor 仍按该周期判定）"
        rows.append(item)
    return {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "open_count": len(rows),
        "monitor_aligned": True,
        "positions": rows,
    }


def render_markdown(report: dict) -> str:
    lines = [
        f"# new10 OPEN 跟进 · {report['generated_at']}",
        "",
        f"持仓数：**{report['open_count']}** · 止损 K 线与 **pending monitor 同口径**（D1/H1 用**已完成** bar）",
        "",
        "| # | 品种 | 定式 | 方向 | 止损 | 判定 bar | high/low | 触停? |",
        "|---|------|------|------|------|----------|----------|-------|",
    ]
    pending_sections: list[str] = []
    for i, p in enumerate(report["positions"], start=1):
        bar = p.get("stop_bar") or {}
        chk = p.get("stop_check") or {}
        breached = "⚠️" if chk.get("breached_effective") else ("—（入场前）" if chk.get("breached_on_bar") and not p.get("after_entry") else "—")
        hl = f"{chk.get('high', 'n/a')}/{chk.get('low', 'n/a')}"
        bar_label = f"{bar.get('date', 'n/a')} ({chk.get('bar_kind', '?')})" if bar else "—（无本地 bar）"
        lines.append(
            f"| {i} | {p['symbol']} | {p['strategy_id']} | {p['direction']} | "
            f"{p.get('current_stop')} | {bar_label} | {hl} | {breached} |"
        )
        if p.get("post_entry_stop_check"):
            pe = p["post_entry_stop_check"]
            pb = p.get("post_entry_bar") or {}
            flag = "⚠️" if pe.get("breached_effective") else "—"
            pending_sections.extend(
                [
                    f"### {p['symbol']} 入场后 bar（审计展示）",
                    "",
                    f"- bar：`{pb.get('date')}` · high/low **{pe.get('high')}/{pe.get('low')}** · 触停 **{flag}**",
                    "",
                ]
            )
        if p.get("pending_eval_stop_check"):
            pe = p["pending_eval_stop_check"]
            pb = p.get("pending_eval_bar") or {}
            flag = "⚠️ 待 monitor 切到已完成 D1" if pe.get("breached_effective") else "—"
            pending_sections.extend(
                [
                    f"### {p['symbol']} 下一根可判定 D1（CSV 末行 · monitor 尚未 iloc[-2]）",
                    "",
                    f"- bar：`{pb.get('date')}` · high/low **{pe.get('high')}/{pe.get('low')}** · 触停 **{flag}**",
                    "",
                ]
            )
    if pending_sections:
        lines.extend(["", "## 待切换 / 审计 bar", ""] + pending_sections)
    notes = [(p["symbol"], p["stop_eval_note"]) for p in report["positions"] if p.get("stop_eval_note")]
    if notes:
        lines.extend(["", "## 止损判定备注", ""])
        for sym, note in notes:
            lines.append(f"- **{sym}**：{note}")
    lines.extend(
        [
            "",
            "## 说明",
            "",
            "- DS01/DS05 止损周期 **D1**；DS08 **H1**（见 `TIMEFRAME_BY_STRATEGY`）",
            "- `1d`/`1h` 判定用 **已完成** K（`iloc[-2]`），非当日/当小时未成 K",
            "- **入场前 bar** 仅展示参考，不计触停（`breached_effective=false`）",
            "- **D1 当日入场**：bar 时间戳为日初，`bar_time > entry_time` 不满足 → 首根可判定止损为 **次日** 已完成 D1",
            "- 签收 #23–#27 已闭环；#28 HYPE 单独 OPEN 跟踪",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--paper-state", default=str(ROOT / "runtime" / "overseas_paper_state.json"))
    parser.add_argument("--data-dir", default=str(ROOT / "data"))
    parser.add_argument("--out-dir", default="")
    args = parser.parse_args()
    paper_path = Path(args.paper_state)
    if not paper_path.is_file():
        print(f"missing: {paper_path}", file=sys.stderr)
        return 1
    report = build_report(load_paper(paper_path), Path(args.data_dir))
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if args.out_dir:
        out = Path(args.out_dir)
        out.mkdir(parents=True, exist_ok=True)
        (out / "followup.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        (out / "FOLLOWUP.md").write_text(render_markdown(report), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
