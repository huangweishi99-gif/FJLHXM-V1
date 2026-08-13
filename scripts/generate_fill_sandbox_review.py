#!/usr/bin/env python3
"""Build a post-fill sandbox review pack from effective pending status.

The script is intentionally an orchestration layer. It does not reimplement
FengJi strategy rules; it selects already-filled orders and delegates chart
rendering to the existing sandbox plotters.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
for search_path in (ROOT, ROOT / "src", ROOT / "packages" / "fengji_core"):
    if str(search_path) not in sys.path:
        sys.path.insert(0, str(search_path))

from scripts.summarize_pending_effective_status import load_json, load_orders, setup_key, summarize


FILL_STATUSES = {"filled", "filled_open"}
SUPPORTED_STRATEGIES = {"DS01", "DS03", "DS04", "DS05", "DS07", "DS08", "DS09"}


@dataclass
class ReviewTask:
    symbol: str
    strategy_id: str
    side: str
    effective_status: str
    order_id: str
    setup_key: str
    output: str
    status: str
    reason: str
    command: list[str]
    event_time: str = ""
    fill_price: Any = None
    trigger_price: Any = None
    stop_price: Any = None
    stdout: str = ""
    stderr: str = ""


def tail_text_lines(path: Path, max_lines: int) -> list[str]:
    if max_lines <= 0:
        return path.read_text(encoding="utf-8-sig", errors="ignore").splitlines()
    chunk_size = 64 * 1024
    chunks: list[bytes] = []
    line_count = 0
    with path.open("rb") as handle:
        handle.seek(0, 2)
        position = handle.tell()
        while position > 0 and line_count <= max_lines:
            read_size = min(chunk_size, position)
            position -= read_size
            handle.seek(position)
            chunk = handle.read(read_size)
            chunks.append(chunk)
            line_count += chunk.count(b"\n")
    data = b"".join(reversed(chunks))
    return data.decode("utf-8-sig", errors="ignore").splitlines()[-max_lines:]


def load_jsonl(path: Path, *, tail_lines: int) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in tail_text_lines(path, tail_lines):
        line = line.strip()
        if not line:
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(item, dict):
            rows.append(item)
    return rows


def index_events(paths: list[Path], *, tail_lines: int) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    by_order_id: dict[str, dict[str, Any]] = {}
    by_setup_key: dict[str, dict[str, Any]] = {}
    for path in paths:
        for event in load_jsonl(path, tail_lines=tail_lines):
            if str(event.get("event_type", "")).lower() != "fill":
                continue
            order_id = str(event.get("order_id") or "").strip()
            key = str(event.get("setup_key") or "").strip()
            if order_id:
                by_order_id[order_id] = event
            if key:
                by_setup_key[key] = event
    return by_order_id, by_setup_key


def coalesce(*values: Any) -> Any:
    for value in values:
        if value not in (None, ""):
            return value
    return None


def clean_strategy(value: Any) -> str:
    return str(value or "").strip().upper()


def clean_side(value: Any) -> str:
    side = str(value or "").strip().lower()
    if side in {"buy", "long", "1"}:
        return "long"
    if side in {"sell", "short", "-1"}:
        return "short"
    return side


def safe_name(value: str) -> str:
    text = re.sub(r"[^A-Za-z0-9_.-]+", "_", value.strip())
    return text.strip("._") or "item"


def resolve_csv(data_dir: Path, symbol: str, timeframe: str) -> Path:
    tf = timeframe.lower()
    candidates = [
        data_dir / tf / f"{symbol}.csv",
        data_dir / tf / f"{symbol.replace('USDT', '')}.csv",
    ]
    if tf == "1d":
        candidates.extend([data_dir / "d1" / f"{symbol}.csv", data_dir / "daily" / f"{symbol}.csv"])
    if tf in {"15m", "m15"}:
        candidates.extend([data_dir / "m15" / f"{symbol}.csv", data_dir / "15m" / f"{symbol.replace('USDT', '')}.csv"])
    for path in candidates:
        if path.exists():
            return path
    return candidates[0]


def first_time(event: dict[str, Any], row: dict[str, Any], *fields: str) -> str:
    for field in fields:
        value = coalesce(event.get(field), row.get(field))
        if value:
            return str(value)
    return str(coalesce(event.get("time"), row.get("latest_time"), row.get("created_at"), "") or "")


def parse_reason_float(reason: str, name: str) -> float | None:
    match = re.search(rf"{name}=([-+]?[0-9]*\.?[0-9]+)", reason, flags=re.IGNORECASE)
    if not match:
        return None
    try:
        return float(match.group(1))
    except ValueError:
        return None


def match_trade_no(trades: Any, *, side: str, fill: Any, trigger: Any, when: str = "") -> int | None:
    import pandas as pd

    if trades is None or getattr(trades, "empty", True):
        return None
    candidates = trades.copy()
    if "direction" in candidates.columns and side:
        candidates = candidates[candidates["direction"].astype(str).str.lower() == side]
    if candidates.empty:
        return None

    fill_value = None
    trigger_value = None
    try:
        fill_value = float(fill)
    except (TypeError, ValueError):
        pass
    try:
        trigger_value = float(trigger)
    except (TypeError, ValueError):
        pass

    target_time = None
    if when:
        try:
            target_time = pd.to_datetime(when)
        except Exception:
            target_time = None

    scored: list[tuple[float, int]] = []
    for _, trade in candidates.iterrows():
        score = 0.0
        entry_price = float(trade.get("entry_price", 0.0) or 0.0)
        if fill_value is not None:
            score += abs(entry_price - fill_value) / max(abs(fill_value), 1.0)
        elif trigger_value is not None:
            score += abs(entry_price - trigger_value) / max(abs(trigger_value), 1.0)
        if target_time is not None and "entry_date" in trade:
            try:
                entry_time = pd.to_datetime(trade.get("entry_date"))
                delta_days = abs((entry_time.normalize() - target_time.normalize()).days)
                score += min(delta_days, 30) * 0.01
            except Exception:
                pass
        scored.append((score, int(trade["trade_no"])))

    if not scored:
        return None
    scored.sort(key=lambda item: item[0])
    best_score, best_trade_no = scored[0]
    return best_trade_no if best_score <= 0.05 else None


def find_ds05_trade_no(csv_path: Path, *, side: str, fill: Any, trigger: Any, when: str) -> tuple[int | None, str]:
    try:
        from backtest_ds05 import DS05BacktestConfig, run_ds05_backtest
        from quant.data import load_ohlcv_for_engine
        from quant.futures_specs import get_futures_spec

        spec = get_futures_spec(csv_path)
        config = DS05BacktestConfig(futures_mode=spec is not None, spec=spec)
        result = run_ds05_backtest(load_ohlcv_for_engine(csv_path, config.atr_window), config)
        trade_no = match_trade_no(result.get("trades"), side=side, fill=fill, trigger=trigger, when=when)
        return trade_no, "" if trade_no is not None else "no DS05 backtest trade matched fill"
    except Exception as exc:
        return None, f"DS05 trade lookup failed: {exc}"


def find_ds04_trade_no(csv_path: Path, *, side: str, fill: Any, trigger: Any, when: str) -> tuple[int | None, str]:
    try:
        from backtest_ds04 import DS04BacktestConfig, run_ds04_backtest
        from quant.data import load_ohlcv_for_engine
        from quant.futures_specs import get_futures_spec

        spec = get_futures_spec(csv_path)
        config = DS04BacktestConfig(futures_mode=True, spec=spec)
        result = run_ds04_backtest(load_ohlcv_for_engine(csv_path, config.atr_window), config)
        trade_no = match_trade_no(result.get("trades"), side=side, fill=fill, trigger=trigger, when=when)
        return trade_no, "" if trade_no is not None else "no DS04 backtest trade matched fill"
    except Exception as exc:
        return None, f"DS04 trade lookup failed: {exc}"


def find_ds09_trade_no(d1_csv: Path, m15_csv: Path, *, symbol: str, side: str, fill: Any, trigger: Any, when: str) -> tuple[int | None, str]:
    try:
        from backtest_ds09 import DS09BacktestConfig, load_frame, load_m15_frame, run_ds09_backtest
        from quant.futures_specs import get_futures_spec

        spec = get_futures_spec(d1_csv) or get_futures_spec(m15_csv)
        config = DS09BacktestConfig(futures_mode=True, spec=spec)
        result = run_ds09_backtest(load_frame(d1_csv, config.atr_window), load_m15_frame(m15_csv, config.atr_window), config, symbol=symbol)
        trade_no = match_trade_no(result.get("trades"), side=side, fill=fill, trigger=trigger, when=when)
        return trade_no, "" if trade_no is not None else "no DS09 backtest trade matched fill"
    except Exception as exc:
        return None, f"DS09 trade lookup failed: {exc}"


def build_command(row: dict[str, Any], event: dict[str, Any], *, data_dir: Path, os_state_dir: Path, out: Path) -> tuple[list[str], str, str]:
    symbol = str(row.get("symbol") or "").upper()
    strategy = clean_strategy(row.get("strategy_id"))
    side = clean_side(row.get("side"))
    trigger = coalesce(event.get("trigger_price"), row.get("trigger_price"))
    stop = coalesce(event.get("stop_price"), row.get("stop_price"))
    fill = coalesce(event.get("fill_price"), trigger)

    if strategy not in SUPPORTED_STRATEGIES:
        return [], "unsupported", f"{strategy} has no unified sandbox plotter yet"
    if not symbol or not side or trigger is None or stop is None or fill is None:
        return [], "missing_data", "symbol, side, trigger, stop, or fill price is missing"

    if strategy == "DS01":
        plotter = ROOT / "scripts" / "plot_crypto_ds01_trade_sandbox.py"
        if not plotter.exists():
            return [], "missing_plotter", f"missing plotter: {plotter}"
        csv_path = resolve_csv(data_dir, symbol, "1d")
        if not csv_path.exists():
            return [], "missing_data", f"missing D1 csv: {csv_path}"
        entry_date = first_time(event, row, "latest_time", "time")
        if not entry_date:
            return [], "missing_data", "missing DS01 entry date"
        return [
            sys.executable,
            str(plotter),
            "--csv",
            str(csv_path),
            "--symbol",
            symbol,
            "--side",
            side,
            "--entry-date",
            entry_date,
            "--entry-price",
            str(fill),
            "--stop-price",
            str(stop),
            "--out",
            str(out),
        ], "ready", ""

    if strategy == "DS04":
        plotter = ROOT / "scripts" / "plot_live_ds04_sandbox.py"
        if not plotter.exists():
            return [], "missing_plotter", f"missing plotter: {plotter}"
        csv_path = resolve_csv(data_dir, symbol, "1d")
        if not csv_path.exists():
            return [], "missing_data", f"missing D1 csv: {csv_path}"
        return [
            sys.executable,
            str(plotter),
            "--csv",
            str(csv_path),
            "--symbol",
            symbol,
            "--side",
            side,
            "--setup-key",
            str(row.get("setup_key") or event.get("setup_key") or ""),
            "--fill-price",
            str(fill),
            "--stop-price",
            str(stop),
            "--out",
            str(out),
        ], "ready", ""

    if strategy == "DS05":
        csv_path = resolve_csv(data_dir, symbol, "1d")
        if not csv_path.exists():
            return [], "missing_data", f"missing D1 csv: {csv_path}"
        if str(row.get("effective_status")) == "filled_open":
            plotter = ROOT / "scripts" / "plot_live_ds05_sandbox.py"
            if not plotter.exists():
                return [], "missing_plotter", f"missing plotter: {plotter}"
            return [
                sys.executable,
                str(plotter),
                "--csv",
                str(csv_path),
                "--symbol",
                symbol,
                "--side",
                side,
                "--setup-key",
                str(row.get("setup_key") or event.get("setup_key") or ""),
                "--fill-price",
                str(fill),
                "--stop-price",
                str(stop),
                "--out",
                str(out),
            ], "ready", ""
        plotter = ROOT / "src" / "plot_ds05_sandbox.py"
        if not plotter.exists():
            return [], "missing_plotter", f"missing plotter: {plotter}"
        when = first_time(event, row, "latest_time", "time")
        trade_no, reason = find_ds05_trade_no(csv_path, side=side, fill=fill, trigger=trigger, when=when)
        if trade_no is None:
            return [], "no_backtest_trade", reason
        command = [
            sys.executable,
            str(plotter),
            "--csv",
            str(csv_path),
            "--trade-no",
            str(trade_no),
            "--out",
            str(out),
            "--line-mode",
            "hardened",
        ]
        try:
            from quant.futures_specs import get_futures_spec

            if get_futures_spec(csv_path) is not None:
                command.append("--futures-mode")
        except Exception:
            pass
        return command, "ready", ""

    if strategy == "DS03":
        plotter = ROOT / "scripts" / "plot_live_ds03_sandbox.py"
        if not plotter.exists():
            return [], "missing_plotter", f"missing plotter: {plotter}"
        when = first_time(event, row, "latest_time", "attack_bar_time", "time")
        if not when:
            return [], "missing_data", "missing DS03 date"
        return [
            sys.executable,
            str(plotter),
            "--data-dir",
            str(data_dir),
            "--symbol",
            symbol,
            "--timeframe",
            "1d",
            "--date",
            when,
            "--side",
            side,
            "--fill-price",
            str(fill),
            "--trigger-price",
            str(trigger),
            "--stop-price",
            str(stop),
            "--out",
            str(out),
        ], "ready", ""

    if strategy == "DS07":
        plotter = ROOT / "scripts" / "plot_live_ds07_sandbox.py"
        if not plotter.exists():
            return [], "missing_plotter", f"missing plotter: {plotter}"
        when = first_time(event, row, "time", "latest_time", "bar_time")
        if not when:
            return [], "missing_data", "missing DS07 trigger time"
        return [
            sys.executable,
            str(plotter),
            "--symbol",
            symbol,
            "--trigger-time",
            when,
            "--side",
            side,
            "--trigger-price",
            str(trigger),
            "--stop-price",
            str(stop),
            "--fill-price",
            str(fill),
            "--pattern",
            str(coalesce(event.get("setup"), row.get("setup"), "")),
            "--data-dir",
            str(data_dir),
            "--out",
            str(out),
        ], "ready", ""

    if strategy == "DS08":
        plotter = ROOT / "scripts" / "plot_live_ds08_sandbox.py"
        if not plotter.exists():
            return [], "missing_plotter", f"missing plotter: {plotter}"
        when = first_time(event, row, "latest_time", "activation_bar_time", "time")
        if not when:
            return [], "missing_data", "missing DS08 setup time"
        return [
            sys.executable,
            str(plotter),
            "--symbol",
            symbol,
            "--side",
            side,
            "--setup-time",
            when,
            "--trigger-price",
            str(trigger),
            "--stop-price",
            str(stop),
            "--pattern",
            str(coalesce(event.get("setup"), row.get("setup"), "")),
            "--data-dir",
            str(data_dir),
            "--os-state-dir",
            str(os_state_dir),
            "--out",
            str(out),
        ], "ready", ""

    d1_csv = resolve_csv(data_dir, symbol, "1d")
    m15_csv = resolve_csv(data_dir, symbol, "15m")
    missing = [str(path) for path in (d1_csv, m15_csv) if not path.exists()]
    if missing:
        return [], "missing_data", f"missing DS09 csv: {', '.join(missing)}"
    if str(row.get("effective_status")) == "filled_open":
        plotter = ROOT / "scripts" / "plot_live_ds09_sandbox.py"
        if not plotter.exists():
            return [], "missing_plotter", f"missing plotter: {plotter}"
        reason = str(coalesce(event.get("reason"), row.get("reason"), ""))
        boundary = parse_reason_float(reason, "boundary")
        return [
            sys.executable,
            str(plotter),
            "--d1-csv",
            str(d1_csv),
            "--m15-csv",
            str(m15_csv),
            "--symbol",
            symbol,
            "--side",
            side,
            "--setup-key",
            str(row.get("setup_key") or event.get("setup_key") or ""),
            "--reason",
            reason,
            "--entry-time",
            first_time(event, row, "bar_time", "time", "latest_time"),
            "--fill-price",
            str(fill),
            "--trigger-price",
            str(trigger),
            "--stop-price",
            str(stop),
            "--boundary",
            str(boundary or 0.0),
            "--pattern",
            str(coalesce(event.get("setup"), row.get("setup"), "")),
            "--out",
            str(out),
        ], "ready", ""
    plotter = ROOT / "src" / "plot_ds09_sandbox.py"
    if not plotter.exists():
        return [], "missing_plotter", f"missing plotter: {plotter}"
    when = first_time(event, row, "time", "latest_time", "bar_time")
    trade_no, reason = find_ds09_trade_no(d1_csv, m15_csv, symbol=symbol, side=side, fill=fill, trigger=trigger, when=when)
    if trade_no is None:
        return [], "no_backtest_trade", reason
    return [
        sys.executable,
        str(plotter),
        "--d1-csv",
        str(d1_csv),
        "--m15-csv",
        str(m15_csv),
        "--trade-no",
        str(trade_no),
        "--symbol",
        symbol,
        "--out",
        str(out),
    ], "ready", ""


def build_review_tasks(
    *,
    orders_file: Path,
    state_file: Path,
    paper_state_file: Path,
    event_files: list[Path],
    data_dir: Path,
    os_state_dir: Path,
    out_dir: Path,
    symbol: str = "",
    limit: int = 20,
    event_tail_lines: int = 20000,
) -> list[ReviewTask]:
    payload = summarize(load_orders(orders_file), load_json(state_file, {}), load_json(paper_state_file, {}), symbol_filter=symbol)
    by_order_id, by_setup_key = index_events(event_files, tail_lines=event_tail_lines)
    tasks: list[ReviewTask] = []
    for row in payload["rows"]:
        if str(row.get("effective_status")) not in FILL_STATUSES:
            continue
        order_id = str(row.get("order_id") or "").strip()
        key = setup_key(row)
        event = by_order_id.get(order_id) or by_setup_key.get(key) or {}
        strategy = clean_strategy(row.get("strategy_id"))
        side = clean_side(row.get("side"))
        event_time = first_time(event, row, "time", "latest_time", "created_at")
        stamp = safe_name(event_time.replace(":", "").replace(" ", "_")[:32] or "no_time")
        base = safe_name(f"{stamp}_{row.get('symbol')}_{strategy}_{side}_{order_id[:18]}")
        out = out_dir / f"{base}.png"
        command, status, reason = build_command(row, event, data_dir=data_dir, os_state_dir=os_state_dir, out=out)
        task = ReviewTask(
            symbol=str(row.get("symbol") or ""),
            strategy_id=strategy,
            side=side,
            effective_status=str(row.get("effective_status") or ""),
            order_id=order_id,
            setup_key=key,
            output=str(out),
            status=status,
            reason=reason,
            command=command,
            event_time=event_time,
            fill_price=coalesce(event.get("fill_price"), row.get("trigger_price")),
            trigger_price=coalesce(event.get("trigger_price"), row.get("trigger_price")),
            stop_price=coalesce(event.get("stop_price"), row.get("stop_price")),
        )
        tasks.append(task)
        if limit > 0 and len(tasks) >= limit:
            break
    return tasks


def execute_tasks(tasks: list[ReviewTask], *, timeout: int) -> None:
    for task in tasks:
        if task.status != "ready":
            continue
        result = subprocess.run(task.command, cwd=ROOT, text=True, capture_output=True, timeout=timeout)
        task.stdout = result.stdout.strip()
        task.stderr = result.stderr.strip()
        if result.returncode == 0 and Path(task.output).exists():
            task.status = "generated"
            task.reason = "chart generated"
        else:
            task.status = "failed"
            task.reason = f"plotter exited {result.returncode}"


def render_markdown(tasks: list[ReviewTask]) -> str:
    lines = [
        "# Fill Sandbox Review",
        "",
        "| symbol | strategy | side | status | fill | trigger | stop | output | reason |",
        "|---|---|---|---|---:|---:|---:|---|---|",
    ]
    for task in tasks:
        output = task.output if task.status == "generated" else ""
        reason = task.reason.replace("|", "/")
        lines.append(
            f"| {task.symbol} | {task.strategy_id} | {task.side} | {task.status} | "
            f"{task.fill_price} | {task.trigger_price} | {task.stop_price} | {output} | {reason} |"
        )
    if not tasks:
        lines.append("| | | | no_candidates | | | | | no filled or filled_open effective rows |")
    lines.append("")
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate a post-fill sandbox review pack.")
    parser.add_argument("--orders-file", default="runtime/fengji_pending_orders/pending_orders.json")
    parser.add_argument("--state-file", default="runtime/fengji_pending_orders/futures_pending_state.json")
    parser.add_argument("--paper-state-file", default="runtime/fengji_futures/state_futures_v2.json")
    parser.add_argument("--event-file", action="append", default=[], help="pending monitor events JSONL; repeatable")
    parser.add_argument("--data-dir", default="data")
    parser.add_argument("--os-state-dir", default="runtime/fengji_os_state")
    parser.add_argument("--out-dir", default="runtime/fill_sandbox_review")
    parser.add_argument("--symbol", default="")
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--event-tail-lines", type=int, default=20000, help="read only the last N lines from each events JSONL; 0 reads full files")
    parser.add_argument("--execute", action="store_true", help="run supported sandbox plotters")
    parser.add_argument("--timeout", type=int, default=120)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    event_files = [Path(path) for path in args.event_file]
    tasks = build_review_tasks(
        orders_file=Path(args.orders_file),
        state_file=Path(args.state_file),
        paper_state_file=Path(args.paper_state_file),
        event_files=event_files,
        data_dir=Path(args.data_dir),
        os_state_dir=Path(args.os_state_dir),
        out_dir=out_dir,
        symbol=args.symbol,
        limit=int(args.limit),
        event_tail_lines=int(args.event_tail_lines),
    )
    if args.execute:
        execute_tasks(tasks, timeout=int(args.timeout))

    payload = {"tasks": [asdict(task) for task in tasks]}
    json_path = out_dir / "fill_sandbox_review.json"
    md_path = out_dir / "fill_sandbox_review.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(render_markdown(tasks), encoding="utf-8")

    counts: dict[str, int] = {}
    for task in tasks:
        counts[task.status] = counts.get(task.status, 0) + 1
    print(f"fill sandbox review: total={len(tasks)} counts={counts} json={json_path} md={md_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
