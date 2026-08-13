from __future__ import annotations

import argparse
import json
import math
import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any


PRICE_FIELDS = {
    "entry_price",
    "exit_price",
    "fill_price",
    "trigger_price",
    "stop_price",
    "initial_stop",
    "current_stop",
    "bad_exit_price",
    "open",
    "high",
    "low",
    "close",
    "bar_open",
    "bar_high",
    "bar_low",
    "bar_close",
}
TIME_FIELDS = {
    "time",
    "event_time",
    "created_at",
    "entry_time",
    "exit_time",
    "bar_time",
    "latest_time",
    "closed_at",
    "audit_invalid_at",
    "stop_updated_at",
}
STATE_RECORD_LISTS = (
    "open_positions",
    "audit_invalid_positions",
    "audit_invalid_closes",
    "closed_positions",
    "closed_trades",
)
STATE_ID_LISTS = (
    "seen_entries",
    "closed_entries",
    "audit_invalid_entries",
)
MONITOR_ID_LISTS = (
    "filled_order_ids",
    "cancelled_order_ids",
    "filled_setup_keys",
    "cancelled_setup_keys",
    "consumed_ds03_setup_keys",
)
MONITOR_RECORD_LISTS = ("fills", "closes", "events")


@dataclass(frozen=True)
class Window:
    start: datetime
    end: datetime

    def contains(self, value: datetime | None) -> bool:
        return value is not None and self.start <= value <= self.end

    def text(self) -> str:
        return f"{format_time(self.start)}..{format_time(self.end)}"


def format_time(value: datetime) -> str:
    return value.strftime("%Y-%m-%d %H:%M:%S")


def parse_time(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, (int, float)) and math.isfinite(float(value)):
        raw = float(value)
        try:
            if raw > 10**17:
                return datetime.fromtimestamp(raw / 1_000_000_000)
            if raw > 10**12:
                return datetime.fromtimestamp(raw / 1_000)
            if raw > 10**9:
                return datetime.fromtimestamp(raw)
        except (OSError, OverflowError, ValueError):
            return None

    text = str(value).strip()
    if not text:
        return None
    text = text.replace("T", " ")
    if text.endswith("Z"):
        text = text[:-1]
    text = text[:19]
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%Y/%m/%d %H:%M:%S", "%Y/%m/%d"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return None


def parse_entry_bar(value: Any) -> datetime | None:
    text = str(value or "").strip()
    match = re.search(r"(\d{4}[-/]\d{2}[-/]\d{2}[ T]\d{2}:\d{2}:\d{2})", text)
    return parse_time(match.group(1)) if match else None


def normalize_symbol(value: Any) -> str:
    text = str(value or "").strip().upper()
    if not text:
        return ""

    paren_match = re.findall(r"[\(（]([A-Z]{1,6})[\)）]", text)
    if paren_match:
        text = paren_match[-1]
    elif "." in text:
        text = text.rsplit(".", 1)[-1]
    elif "@" in text:
        text = text.rsplit("@", 1)[-1]

    text = text.replace("-", "").replace("_", "").replace(" ", "")
    text = re.sub(r"[^A-Z0-9]", "", text)
    if text.endswith("USDT"):
        return text

    contract_match = re.match(r"([A-Z]+)\d{3,4}$", text)
    if contract_match:
        text = contract_match.group(1)
    if not text:
        return ""
    return f"{text}USDT"


def split_symbols(value: str) -> list[str]:
    symbols = []
    for item in str(value or "").replace(";", ",").split(","):
        symbol = normalize_symbol(item)
        if symbol and symbol not in symbols:
            symbols.append(symbol)
    return symbols


def safe_load_json(path: Path | None) -> dict[str, Any]:
    if path is None or not path.is_file():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def load_jsonl(path: Path | None) -> list[dict[str, Any]]:
    if path is None or not path.is_file():
        return []
    records: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as fh:
        for line_no, line in enumerate(fh, start=1):
            text = line.strip()
            if not text:
                continue
            try:
                item = json.loads(text)
            except json.JSONDecodeError:
                records.append({"_line_no": line_no, "_decode_error": True, "raw": text[:300]})
                continue
            if isinstance(item, dict):
                item["_line_no"] = line_no
                records.append(item)
    return records


def record_symbol(record: dict[str, Any], fallback: str = "") -> str:
    for key in ("symbol", "display_symbol", "品种"):
        symbol = normalize_symbol(record.get(key))
        if symbol:
            return symbol
    for key in ("order_id", "setup_key", "trade_key", "key"):
        text = str(record.get(key) or "")
        match = re.search(r"\b([A-Z]{1,6}USDT)\b", text.upper())
        if match:
            return match.group(1)
    return fallback


def record_ids(record: dict[str, Any]) -> list[str]:
    ids: list[str] = []
    for key in ("order_id", "setup_key", "trade_key", "key", "id"):
        value = str(record.get(key) or "").strip()
        if value and value not in ids:
            ids.append(value)
    return ids


def record_times(record: dict[str, Any]) -> dict[str, str]:
    times: dict[str, str] = {}
    for key in TIME_FIELDS:
        parsed = parse_time(record.get(key))
        if parsed is not None:
            times[key] = format_time(parsed)
    entry_bar_time = parse_entry_bar(record.get("entry_bar"))
    if entry_bar_time is not None:
        times["entry_bar_time"] = format_time(entry_bar_time)
    return dict(sorted(times.items()))


def record_in_window(record: dict[str, Any], window: Window) -> bool:
    for key in TIME_FIELDS:
        if window.contains(parse_time(record.get(key))):
            return True
    return window.contains(parse_entry_bar(record.get("entry_bar")))


def id_matches_symbol(value: Any, symbols: set[str]) -> bool:
    text = str(value or "").upper()
    if not text:
        return False
    return any(symbol in text or symbol.removesuffix("USDT") in text for symbol in symbols)


def impossible_price_reasons(record: dict[str, Any]) -> list[str]:
    reasons: list[str] = []
    for key in sorted(PRICE_FIELDS):
        if key not in record:
            continue
        value = record.get(key)
        try:
            price = float(value)
        except (TypeError, ValueError):
            reasons.append(f"{key}=non_numeric")
            continue
        if not math.isfinite(price):
            reasons.append(f"{key}=non_finite")
        elif price <= 1e-6:
            reasons.append(f"{key}=too_small")
        elif price >= 1e8:
            reasons.append(f"{key}=too_large")
    return reasons


def suspicious_reasons(record: dict[str, Any], window: Window, source: str) -> list[str]:
    reasons = impossible_price_reasons(record)
    entry_time = parse_time(record.get("entry_time"))
    exit_time = parse_time(record.get("exit_time"))
    if entry_time is not None and exit_time is not None and exit_time <= entry_time:
        reasons.append("exit_time_not_after_entry_time")

    event_type = str(record.get("event_type") or "").strip().lower()
    if event_type in {"fill", "close", "audit_invalid_close", "audit_restore"} and record_in_window(record, window):
        reasons.append(f"{event_type}_touches_corrupt_window")

    if window.contains(parse_entry_bar(record.get("entry_bar"))):
        reasons.append("entry_bar_in_corrupt_window")
    if source in {"open_positions", "audit_invalid_positions", "audit_invalid_closes"} and record_in_window(record, window):
        reasons.append(f"{source}_time_in_corrupt_window")
    return sorted(set(reasons))


def slim_record(record: dict[str, Any], source: str, window: Window) -> dict[str, Any]:
    keys = (
        "_line_no",
        "event_type",
        "symbol",
        "display_symbol",
        "strategy_id",
        "side",
        "direction",
        "timeframe",
        "order_id",
        "setup_key",
        "trade_key",
        "key",
        "entry_time",
        "exit_time",
        "time",
        "event_time",
        "created_at",
        "bar_time",
        "entry_bar",
        "entry_price",
        "exit_price",
        "fill_price",
        "trigger_price",
        "stop_price",
        "initial_stop",
        "current_stop",
        "bar_high",
        "bar_low",
        "net_pnl",
        "reason",
        "audit_invalid_reason",
        "price_source",
        "risk_rule",
        "setup",
    )
    out = {key: record.get(key) for key in keys if key in record}
    out["_source"] = source
    out["_symbol"] = record_symbol(record)
    out["_times"] = record_times(record)
    reasons = suspicious_reasons(record, window, source)
    if reasons:
        out["_suspicious_reasons"] = reasons
    return out


def collect_state_records(
    state: dict[str, Any],
    symbols: set[str],
    window: Window,
) -> tuple[dict[str, dict[str, list[Any]]], set[str], list[dict[str, Any]]]:
    by_symbol: dict[str, dict[str, list[Any]]] = {
        symbol: {name: [] for name in (*STATE_RECORD_LISTS, *STATE_ID_LISTS)} for symbol in sorted(symbols)
    }
    matched_ids: set[str] = set()
    suspicious: list[dict[str, Any]] = []
    state_symbols = state.get("symbols") if isinstance(state, dict) else {}
    if not isinstance(state_symbols, dict):
        return by_symbol, matched_ids, suspicious

    for state_symbol, symbol_state in state_symbols.items():
        normalized_state_symbol = normalize_symbol(state_symbol)
        if normalized_state_symbol not in symbols or not isinstance(symbol_state, dict):
            continue
        bucket = by_symbol.setdefault(
            normalized_state_symbol,
            {name: [] for name in (*STATE_RECORD_LISTS, *STATE_ID_LISTS)},
        )
        for list_name in STATE_RECORD_LISTS:
            for record in symbol_state.get(list_name) or []:
                if not isinstance(record, dict):
                    continue
                if record_symbol(record, normalized_state_symbol) != normalized_state_symbol:
                    continue
                if not record_in_window(record, window) and not impossible_price_reasons(record):
                    continue
                slim = slim_record(record, list_name, window)
                bucket[list_name].append(slim)
                matched_ids.update(record_ids(record))
                if slim.get("_suspicious_reasons"):
                    suspicious.append(slim)
        for list_name in STATE_ID_LISTS:
            values = [str(value) for value in symbol_state.get(list_name) or [] if id_matches_symbol(value, symbols)]
            bucket[list_name].extend(values)
            matched_ids.update(values)
    return by_symbol, matched_ids, suspicious


def collect_records_from_events(
    records: list[dict[str, Any]],
    symbols: set[str],
    window: Window,
    source: str,
) -> tuple[list[dict[str, Any]], set[str], list[dict[str, Any]]]:
    matched: list[dict[str, Any]] = []
    matched_ids: set[str] = set()
    suspicious: list[dict[str, Any]] = []
    for record in records:
        symbol = record_symbol(record)
        if symbol not in symbols:
            continue
        if not record_in_window(record, window) and not impossible_price_reasons(record):
            continue
        slim = slim_record(record, source, window)
        matched.append(slim)
        matched_ids.update(record_ids(record))
        if slim.get("_suspicious_reasons"):
            suspicious.append(slim)
    return matched, matched_ids, suspicious


def collect_monitor_ids(monitor: dict[str, Any], symbols: set[str], matched_ids: set[str]) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    needles = {item.upper() for item in matched_ids if item}
    for list_name in MONITOR_ID_LISTS:
        values: list[str] = []
        for item in monitor.get(list_name) or []:
            text = str(item)
            upper = text.upper()
            if id_matches_symbol(text, symbols) or any(needle and needle in upper for needle in needles):
                values.append(text)
        out[list_name] = values
    return out


def build_summary(payload: dict[str, Any], symbols: list[str]) -> dict[str, dict[str, int]]:
    summary: dict[str, dict[str, int]] = {}
    events = payload.get("events") or []
    monitor_records = payload.get("monitor", {}).get("records") or []
    suspicious = payload.get("suspicious") or []
    for symbol in symbols:
        state_bucket = payload.get("state", {}).get(symbol, {})
        symbol_events = [item for item in events if item.get("_symbol") == symbol]
        symbol_monitor = [item for item in monitor_records if item.get("_symbol") == symbol]
        all_event_like = [*symbol_events, *symbol_monitor]
        summary[symbol] = {
            "fills": sum(1 for item in all_event_like if str(item.get("event_type", "")).lower() == "fill"),
            "closes": sum(1 for item in all_event_like if str(item.get("event_type", "")).lower() == "close"),
            "open_positions": len(state_bucket.get("open_positions") or []),
            "invalid_positions": len(state_bucket.get("audit_invalid_positions") or []),
            "invalid_closes": len(state_bucket.get("audit_invalid_closes") or []),
            "state_ids": sum(len(state_bucket.get(name) or []) for name in STATE_ID_LISTS),
            "monitor_ids": sum(len(payload.get("monitor", {}).get("ids", {}).get(name) or []) for name in MONITOR_ID_LISTS),
            "suspicious": sum(1 for item in suspicious if item.get("_symbol") == symbol),
        }
    return summary


def build_audit(
    *,
    symbols: list[str],
    window: Window,
    paper_state_file: Path,
    monitor_state_file: Path | None,
    events_file: Path | None,
) -> dict[str, Any]:
    symbol_set = set(symbols)
    state = safe_load_json(paper_state_file)
    monitor = safe_load_json(monitor_state_file)
    events = load_jsonl(events_file)

    state_records, state_ids, state_suspicious = collect_state_records(state, symbol_set, window)
    jsonl_records, event_ids, event_suspicious = collect_records_from_events(events, symbol_set, window, "events_jsonl")

    monitor_records: list[dict[str, Any]] = []
    monitor_ids: set[str] = set()
    monitor_suspicious: list[dict[str, Any]] = []
    for list_name in MONITOR_RECORD_LISTS:
        records = monitor.get(list_name) if isinstance(monitor, dict) else None
        if not isinstance(records, list):
            continue
        matched, ids, suspicious = collect_records_from_events(records, symbol_set, window, f"monitor_{list_name}")
        monitor_records.extend(matched)
        monitor_ids.update(ids)
        monitor_suspicious.extend(suspicious)

    all_ids = set().union(state_ids, event_ids, monitor_ids)
    payload: dict[str, Any] = {
        "generated_at": format_time(datetime.now()),
        "symbols": symbols,
        "window": {"start": format_time(window.start), "end": format_time(window.end)},
        "paper_state_file": str(paper_state_file),
        "monitor_state_file": str(monitor_state_file) if monitor_state_file else "",
        "events_file": str(events_file) if events_file else "",
        "state": state_records,
        "events": jsonl_records,
        "monitor": {
            "ids": collect_monitor_ids(monitor, symbol_set, all_ids),
            "records": monitor_records,
        },
        "suspicious": [*state_suspicious, *event_suspicious, *monitor_suspicious],
    }
    payload["summary"] = build_summary(payload, symbols)
    return payload


def resolve_window(args: argparse.Namespace) -> Window:
    if args.around:
        around = parse_time(args.around)
        if around is None:
            raise ValueError(f"invalid --around time: {args.around}")
        hours = float(args.hours)
        delta = timedelta(hours=hours)
        return Window(around - delta, around + delta)
    start = parse_time(args.start)
    end = parse_time(args.end)
    if start is None or end is None:
        raise ValueError("provide either --around or both --start and --end")
    if end < start:
        raise ValueError("--end must be >= --start")
    return Window(start, end)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Read-only audit for simulated futures state after corrupt CSV events.")
    parser.add_argument("--symbol", "--symbols", dest="symbols", required=True, help="Comma-separated futures symbols.")
    parser.add_argument("--start", default="", help="Corrupt window start time.")
    parser.add_argument("--end", default="", help="Corrupt window end time.")
    parser.add_argument("--around", default="", help="Center of corrupt window.")
    parser.add_argument("--hours", default=12.0, type=float, help="Hours before and after --around.")
    parser.add_argument("--paper-state-file", default=Path("runtime/fengji_futures/state_futures_v2.json"), type=Path)
    parser.add_argument("--monitor-state-file", default=Path("runtime/fengji_pending_orders/futures_pending_state.json"), type=Path)
    parser.add_argument("--events-file", default=Path("runtime/fengji_pending_orders/events.jsonl"), type=Path)
    parser.add_argument("--out", default=None, type=Path, help="Optional JSON audit output path.")
    return parser


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    symbols = split_symbols(args.symbols)
    if not symbols:
        raise SystemExit("no valid symbols")
    window = resolve_window(args)
    payload = build_audit(
        symbols=symbols,
        window=window,
        paper_state_file=args.paper_state_file,
        monitor_state_file=args.monitor_state_file,
        events_file=args.events_file,
    )

    if args.out:
        write_json(args.out, payload)

    for symbol in symbols:
        item = payload["summary"][symbol]
        print(
            f"state_audit symbol={symbol} window={window.text()} fills={item['fills']} "
            f"closes={item['closes']} open_positions={item['open_positions']} "
            f"invalid_closes={item['invalid_closes']} suspicious={item['suspicious']}"
        )
    if args.out:
        print(f"audit={args.out}")
    print("read_only=1")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
