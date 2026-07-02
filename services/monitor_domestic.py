"""国内模拟实盘监测：读取 paper_state，返回最新开仓列表与 K 线 overlay。"""
from __future__ import annotations

import csv
import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEMO_PATH = ROOT / "web" / "data" / "demo_domestic_monitor.json"
MAIN_CONTRACT_SOURCES_PATHS = (
    Path(os.getenv("DOMESTIC_MAIN_CONTRACT_SOURCES_PATH", "")).expanduser()
    if os.getenv("DOMESTIC_MAIN_CONTRACT_SOURCES_PATH", "").strip()
    else None,
    ROOT / "runtime" / "domestic_futures_main_contract_sources.json",
    ROOT / "runtime" / "logs" / "futures_main_contract_sources.json",
)
PENDING_ORDER_PATHS = (
    Path(os.getenv("DOMESTIC_PENDING_ORDERS_PATH", "")).expanduser()
    if os.getenv("DOMESTIC_PENDING_ORDERS_PATH", "").strip()
    else None,
    ROOT / "runtime" / "fengji_pending_orders" / "pending_orders.csv",
    ROOT / "runtime" / "remote_domestic_pending" / "pending_orders.csv",
)
PENDING_ACTIVE_STATUSES = {"ACTIVE", "READY_TRIGGERED", "TRIGGERED"}

FUTURES_MAIN_CONTRACT_FALLBACK = {
    "SA": "KQ.m@CZCE.SA", "FG": "KQ.m@CZCE.FG", "CJ": "KQ.m@CZCE.CJ", "OI": "KQ.m@CZCE.OI",
    "SH": "KQ.m@CZCE.SH", "SR": "KQ.m@CZCE.SR", "SF": "KQ.m@CZCE.SF", "MA": "KQ.m@CZCE.MA",
    "TA": "KQ.m@CZCE.TA", "UR": "KQ.m@CZCE.UR", "CF": "KQ.m@CZCE.CF",
    "RB": "KQ.m@SHFE.rb", "FU": "KQ.m@SHFE.fu", "SP": "KQ.m@SHFE.sp", "NI": "KQ.m@SHFE.ni",
    "AO": "KQ.m@SHFE.ao", "RU": "KQ.m@SHFE.ru", "BR": "KQ.m@SHFE.br", "AU": "KQ.m@SHFE.au", "AG": "KQ.m@SHFE.ag",
    "PG": "KQ.m@DCE.pg", "LH": "KQ.m@DCE.lh", "JD": "KQ.m@DCE.jd", "PP": "KQ.m@DCE.pp",
    "EB": "KQ.m@DCE.eb", "EG": "KQ.m@DCE.eg", "JM": "KQ.m@DCE.jm", "M": "KQ.m@DCE.m",
    "P": "KQ.m@DCE.p", "V": "KQ.m@DCE.v",
    "SI": "KQ.m@GFEX.si", "LC": "KQ.m@GFEX.lc",
    "EC": "KQ.m@INE.ec", "SC": "KQ.m@INE.sc",
}


def _load_main_contract_map() -> dict[str, dict[str, str]]:
    for path in MAIN_CONTRACT_SOURCES_PATHS:
        if path is None or not path.is_file():
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        symbols = data.get("symbols") if isinstance(data, dict) else None
        if not isinstance(symbols, dict):
            continue
        out: dict[str, dict[str, str]] = {}
        for code, meta in symbols.items():
            if not isinstance(meta, dict):
                continue
            tq_code = str(meta.get("tq_code") or "").strip()
            if tq_code.startswith("KQ.m@"):
                actual = str(meta.get("display_contract") or meta.get("underlying_symbol") or "").strip()
                if actual == tq_code:
                    actual = ""
                out[str(code).upper()] = {
                    "tq_code": tq_code,
                    "actual_contract": actual,
                    "display_contract": actual or tq_code,
                }
        if out:
            return out
    return {
        code: {"tq_code": tq_code, "actual_contract": "", "display_contract": tq_code}
        for code, tq_code in FUTURES_MAIN_CONTRACT_FALLBACK.items()
    }


def _main_contract_info(code: str, market: str) -> dict[str, str]:
    if market != "FUTURES":
        return {"tq_code": "", "actual_contract": "", "display_contract": ""}
    return _load_main_contract_map().get(
        str(code).upper(),
        {"tq_code": "", "actual_contract": "", "display_contract": ""},
    )


def _parse_time(value: str) -> datetime:
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%Y/%m/%d %H:%M:%S"):
        try:
            return datetime.strptime(str(value).strip()[:19], fmt)
        except ValueError:
            continue
    return datetime.min


def _normalize_symbol(symbol: str) -> str:
    text = str(symbol or "").strip().upper().replace("-", "").replace("_", "")
    if text and not text.endswith("USDT") and not text.isdigit():
        text += "USDT"
    return text


def _to_china_time_text(value: Any) -> str:
    """Domestic futures paper_state stores Tianqin bar time as UTC wall time."""
    text = str(value or "").strip()
    if not text:
        return ""
    parsed = _parse_time(text)
    if parsed == datetime.min:
        return text
    return (parsed + timedelta(hours=8)).strftime("%Y-%m-%d %H:%M:%S")


def _futures_display(symbol: str) -> str:
    try:
        from fengji_core.symbol_names import futures_display

        return futures_display(symbol)
    except Exception:
        clean = str(symbol).upper().replace("USDT", "")
        return clean


def _infer_market(symbol: str) -> str:
    sym = str(symbol).upper()
    if sym.isdigit() or (len(sym) == 6 and sym[:6].isdigit()):
        return "A_STOCK"
    if sym.endswith("USDT") or sym in {"LC", "MA", "CJ", "SA", "FG"}:
        return "FUTURES"
    return "FUTURES"


def _normalize_position(raw: dict[str, Any], symbol: str) -> dict[str, Any]:
    side = raw.get("direction") or raw.get("side")
    if side in {1, "1", "long", "LONG", "多", "buy"}:
        direction = "long"
    elif side in {-1, "-1", "short", "SHORT", "空", "sell"}:
        direction = "short"
    else:
        direction = str(side or "long").lower()

    entry_price = float(raw.get("entry_price") or raw.get("trigger_price") or 0)
    stop = float(raw.get("current_stop") or raw.get("initial_stop") or raw.get("stop_price") or 0)
    lots = raw.get("lots")
    margin = raw.get("margin")
    notional = raw.get("notional")
    multiplier = int(raw.get("multiplier") or 1)

    amount: float | None = None
    if lots is not None:
        amount = float(lots) * entry_price * multiplier
    elif notional is not None:
        amount = float(notional)
    elif margin is not None:
        amount = float(margin)

    market = _infer_market(symbol)
    code = symbol.upper().replace("USDT", "") if market == "FUTURES" else str(symbol).zfill(6)
    main_contract = _main_contract_info(code, market)
    entry_contract = str(raw.get("entry_data_contract") or "").strip()
    current_contract = main_contract["display_contract"]

    raw_entry_time = str(raw.get("entry_time") or raw.get("created_at") or "")

    return {
        "position_id": str(raw.get("key") or raw.get("order_id") or raw.get("trade_key") or f"{symbol}-{raw.get('entry_time', '')}"),
        "symbol": symbol,
        "code": code,
        "display_name": _futures_display(symbol) if market == "FUTURES" else f"A股({str(symbol).zfill(6)})",
        "market": market,
        "main_contract_code": main_contract["tq_code"],
        "main_contract_actual": main_contract["actual_contract"],
        "main_contract_display": main_contract["display_contract"],
        "main_contract_label": f"主力合约 {main_contract['display_contract']}" if main_contract["display_contract"] else "",
        "entry_data_contract": entry_contract or (current_contract if market == "FUTURES" else ""),
        "current_data_contract": current_contract if market == "FUTURES" else "",
        "strategy_id": str(raw.get("strategy_id") or "TOTAL").upper(),
        "direction": direction,
        "direction_label": "做多" if direction == "long" else "做空",
        "entry_time": _to_china_time_text(raw_entry_time) if market == "FUTURES" else raw_entry_time,
        "entry_time_raw": raw_entry_time,
        "entry_price": entry_price,
        "current_stop": stop,
        "lots": int(lots) if lots is not None else None,
        "multiplier": multiplier,
        "amount_cny": amount,
        "setup": raw.get("setup") or "",
        "timeframe": raw.get("timeframe") or "1d",
        "trade_id": str(raw.get("trade_id") or raw.get("trade_key") or ""),
    }


def _is_valid_monitor_position(position: dict[str, Any]) -> bool:
    entry_time = _parse_time(str(position.get("entry_time") or ""))
    if entry_time == datetime.min:
        return False
    if entry_time.year < 2000:
        return False
    if entry_time > datetime.now() + timedelta(days=1):
        return False
    try:
        return float(position.get("entry_price") or 0) > 0
    except (TypeError, ValueError):
        return False


def _pending_order_candidates() -> list[Path]:
    seen: set[Path] = set()
    out: list[Path] = []
    for path in PENDING_ORDER_PATHS:
        if path is not None and path.is_file() and path not in seen:
            seen.add(path)
            out.append(path)
    runtime = ROOT / "runtime"
    if runtime.is_dir():
        discovered = [
            path for path in runtime.rglob("pending_orders.csv")
            if path.is_file() and path not in seen
        ]
        discovered.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        out.extend(discovered[:8])
    return out


def _load_current_pending_sides() -> dict[str, dict[str, Any]]:
    current: dict[str, dict[str, Any]] = {}
    for path in _pending_order_candidates():
        try:
            with path.open("r", newline="", encoding="utf-8-sig") as fh:
                rows = list(csv.DictReader(fh))
        except Exception:
            continue
        for row in rows:
            status = str(row.get("status") or row.get("radar_status") or "").strip().upper()
            if status not in PENDING_ACTIVE_STATUSES:
                continue
            side = str(row.get("side") or "").strip().lower()
            if side not in {"long", "short"}:
                continue
            symbol = _normalize_symbol(str(row.get("symbol") or ""))
            if not symbol:
                continue
            latest = _parse_time(str(row.get("latest_time") or row.get("created_at") or ""))
            old = current.get(symbol)
            if old is None or latest >= old.get("latest_time", datetime.min):
                current[symbol] = {
                    "side": side,
                    "os_camp": str(row.get("os_camp") or "").strip().lower(),
                    "latest_time": latest,
                    "source": path.name,
                }
    return current


def _filter_positions_against_pending(positions: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], int]:
    current = _load_current_pending_sides()
    if not current:
        return positions, 0
    kept: list[dict[str, Any]] = []
    filtered = 0
    for position in positions:
        symbol = _normalize_symbol(str(position.get("symbol") or ""))
        pending = current.get(symbol)
        if pending is None:
            kept.append(position)
            continue
        entry_time = _parse_time(str(position.get("entry_time") or position.get("entry_time_raw") or ""))
        pending_time = pending.get("latest_time", datetime.min)
        direction = str(position.get("direction") or "").lower()
        if (
            direction in {"long", "short"}
            and pending["side"] in {"long", "short"}
            and direction != pending["side"]
            and pending_time != datetime.min
            and entry_time != datetime.min
            and pending_time.date() >= entry_time.date()
        ):
            filtered += 1
            continue
        kept.append(position)
    return kept, filtered


def _extract_from_paper_state(data: dict[str, Any]) -> list[dict[str, Any]]:
    positions: list[dict[str, Any]] = []
    invalid_count = 0
    symbols = data.get("symbols") or {}
    if isinstance(symbols, dict):
        for sym, st in symbols.items():
            if not isinstance(st, dict):
                continue
            for pos in st.get("open_positions") or []:
                if isinstance(pos, dict):
                    normalized = _normalize_position(pos, str(pos.get("symbol") or sym))
                    if _is_valid_monitor_position(normalized):
                        positions.append(normalized)
                    else:
                        invalid_count += 1
            single = st.get("open_position")
            if isinstance(single, dict):
                normalized = _normalize_position(single, str(single.get("symbol") or sym))
                if _is_valid_monitor_position(normalized):
                    positions.append(normalized)
                else:
                    invalid_count += 1
    for ev in data.get("events") or []:
        if not isinstance(ev, dict) or str(ev.get("event_type", "")).lower() != "open":
            continue
        if ev.get("market") not in {None, "FUTURES", "A_STOCK", "CN_FUTURES"}:
            continue
        sym = str(ev.get("symbol") or "")
        if sym and not any(p["symbol"] == sym for p in positions):
            normalized = _normalize_position(ev, sym)
            if _is_valid_monitor_position(normalized):
                positions.append(normalized)
            else:
                invalid_count += 1
    positions, conflict_count = _filter_positions_against_pending(positions)
    positions.sort(key=lambda p: _parse_time(p["entry_time"]), reverse=True)
    for pos in positions:
        pos["invalid_positions_filtered"] = invalid_count
        pos["pending_conflicts_filtered"] = conflict_count
    return positions[:7]


def load_paper_state_path() -> Path | None:
    env = os.getenv("DOMESTIC_PAPER_STATE_PATH", "").strip()
    if env:
        p = Path(env)
        if p.is_file():
            return p
    for candidate in (
        ROOT / "runtime" / "domestic_paper_state.json",
        ROOT / "runtime" / "futures_paper_state.json",
        ROOT / "data" / "domestic_paper_state.json",
    ):
        if candidate.is_file():
            return candidate
    return None


def load_latest_opens() -> dict[str, Any]:
    path = load_paper_state_path()
    if path is not None:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            positions = _extract_from_paper_state(data)
            return {
                "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "source": "paper_state",
                "state_path": str(path.name),
                "positions": positions,
            }
        except Exception as exc:
            return {
                "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "source": "error",
                "error": str(exc),
                "positions": [],
            }

    if DEMO_PATH.is_file():
        demo = json.loads(DEMO_PATH.read_text(encoding="utf-8"))
        demo["source"] = "demo"
        return demo

    return {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "source": "empty",
        "positions": [],
    }


def overlay_position_on_bundle(bundle: dict[str, Any], position: dict[str, Any]) -> dict[str, Any]:
    """在 chart-bundle 上叠加当前持仓的买入点与守护点。"""
    out = dict(bundle)
    entry_t = str(position.get("entry_time", ""))[:10]
    entry_price = float(position.get("entry_price") or 0)
    stop = float(position.get("current_stop") or 0)
    direction = position.get("direction") or "long"

    markers = list(out.get("markers") or [])
    markers.append(
        {
            "t": entry_t,
            "kind": "entry",
            "side": direction,
            "price": entry_price,
            "trade_no": 0,
            "strategy_id": position.get("strategy_id"),
            "label": "买入",
        }
    )
    if stop > 0:
        markers.append(
            {
                "t": entry_t,
                "kind": "stop",
                "side": direction,
                "price": stop,
                "trade_no": 0,
                "label": "守护点",
            }
        )
    out["markers"] = markers
    out["live_position"] = position
    out["stop_line"] = {"price": stop, "label": "守护点"} if stop > 0 else None
    return out
