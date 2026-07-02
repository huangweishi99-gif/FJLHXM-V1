from __future__ import annotations

import copy
import csv
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SERVICES = ROOT / "services"
SRC = ROOT / "src"
FENGJI_CORE = ROOT / "packages" / "fengji_core"
if str(SERVICES) not in sys.path:
    sys.path.insert(0, str(SERVICES))
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
if str(FENGJI_CORE) not in sys.path:
    sys.path.insert(0, str(FENGJI_CORE))

from chart_bundle import ChartBundleRequest, build_chart_bundle
from crypto_ingest import crypto_timeframe_csv_path, normalize_timeframe
from fengji_core.symbol_names import FUTURES_CN_NAMES

WATCHLIST_RUNTIME_TIMEFRAMES_BY_MARKET = {
    "CRYPTO": ["D1", "H1", "M15"],
    "A_STOCK": ["D1"],
    "FUTURES": ["D1"],
    "US_STOCK": ["D1"],
}
WATCHLIST_RUNTIME_PREFERRED_TIMEFRAMES = ["M15", "H1", "D1"]
WATCHLIST_PREVIEW_STRATEGY = "TOTAL"
WATCHLIST_PREVIEW_YEARS = 1
WATCHLIST_SIGNAL_PREVIEW_CACHE_TTL_SECONDS = 300
_SIGNAL_PREVIEW_CACHE: dict[str, tuple[float, dict[str, Any]]] = {}


def _normalize_watchlist_market(market: str) -> str:
    key = str(market or "").strip().upper()
    aliases = {
        "ASTOCK": "A_STOCK",
        "CN_STOCK": "A_STOCK",
        "CN_FUTURES": "FUTURES",
        "USSTOCK": "US_STOCK",
    }
    return aliases.get(key, key)


def _clean_symbol(symbol: str) -> str:
    return str(symbol or "").strip().upper().replace("-", "").replace("_", "").replace("/", "")


def _dedupe_paths(paths: list[Path]) -> list[Path]:
    seen: set[str] = set()
    out: list[Path] = []
    for path in paths:
        key = str(path)
        if key in seen:
            continue
        seen.add(key)
        out.append(path)
    return out


def runtime_timeframe_csv_candidates(symbol: str, market: str, timeframe: str) -> list[Path]:
    """Return local CSV candidates for a watchlist runtime market/timeframe."""
    mkt = _normalize_watchlist_market(market)
    tf = normalize_timeframe(timeframe)
    sym = _clean_symbol(symbol)
    if mkt == "CRYPTO":
        return [crypto_timeframe_csv_path(sym, tf)]
    if tf != "D1":
        raise ValueError(f"{mkt} watchlist runtime currently supports D1 only")
    if mkt == "A_STOCK":
        code = sym.zfill(6) if sym.isdigit() else sym
        return _dedupe_paths(
            [
                ROOT / "data" / "a_stock" / f"{code}_1D_qfq.csv",
                ROOT / "data" / "a_stock" / f"{code}_1D.csv",
                ROOT / "data" / "a_stock" / f"{code}.csv",
            ]
        )
    if mkt == "FUTURES":
        base = sym.removesuffix("USDT")
        cn_name = FUTURES_CN_NAMES.get(base)
        names = [item for item in [cn_name, base, f"{base}USDT", sym] if item]
        roots = [
            ROOT / "data" / "futures" / "1d",
            ROOT / "data" / "futures_lc" / "1d",
            ROOT / "data" / "1d",
        ]
        return _dedupe_paths([root / f"{name}.csv" for root in roots for name in names])
    if mkt == "US_STOCK":
        base = sym.replace(".", "_")
        return _dedupe_paths(
            [
                ROOT / "data" / "us_stock" / f"{base}_1D.csv",
                ROOT / "data" / "us_stock" / f"{base}.csv",
            ]
        )
    raise ValueError(f"unsupported watchlist market: {market}")


def runtime_timeframe_csv_path(symbol: str, market: str, timeframe: str) -> Path:
    candidates = runtime_timeframe_csv_candidates(symbol, market, timeframe)
    for path in candidates:
        if path.exists():
            return path
    return candidates[0]


def _read_latest_bar(path: Path) -> dict[str, Any]:
    latest: dict[str, Any] | None = None
    rows = 0
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for raw in reader:
            rows += 1
            try:
                row = {
                    "timestamp": str(raw.get("timestamp") or raw.get("date") or raw.get("datetime") or ""),
                    "open": float(raw["open"]),
                    "high": float(raw["high"]),
                    "low": float(raw["low"]),
                    "close": float(raw["close"]),
                    "volume": float(raw.get("volume") or 0),
                }
            except (KeyError, TypeError, ValueError):
                continue
            if row["high"] < max(row["open"], row["close"]) or row["low"] > min(row["open"], row["close"]):
                continue
            latest = row
    if latest is None:
        raise ValueError(f"no valid OHLC rows in {path}")
    latest["rows"] = rows
    return latest


def _latest_entry_marker(markers: list[dict[str, Any]]) -> dict[str, Any] | None:
    entries = [m for m in markers or [] if str(m.get("kind") or "").lower() == "entry"]
    if not entries:
        return None
    return entries[-1]


def clear_watchlist_signal_preview_cache() -> None:
    _SIGNAL_PREVIEW_CACHE.clear()


def _signal_preview_cache_key(d1_path: Path) -> str:
    stat = d1_path.stat()
    return "|".join(
        [
            str(d1_path.resolve()),
            str(stat.st_mtime_ns),
            str(stat.st_size),
            WATCHLIST_PREVIEW_STRATEGY,
            str(WATCHLIST_PREVIEW_YEARS),
        ]
    )


def _build_watchlist_signal_preview_uncached(d1_path: Path) -> dict[str, Any]:
    stat = d1_path.stat()
    bundle = build_chart_bundle(
        ChartBundleRequest(
            csv_path=d1_path,
            strategy_id=WATCHLIST_PREVIEW_STRATEGY,
            years=WATCHLIST_PREVIEW_YEARS,
            futures_mode=False,
        )
    )
    markers = list(bundle.get("markers") or [])
    metrics = dict(bundle.get("metrics") or {})
    latest_entry = _latest_entry_marker(markers)
    preview: dict[str, Any] = {
        "mode": "read_only_signal_preview",
        "strategy_id": bundle.get("strategy_id") or WATCHLIST_PREVIEW_STRATEGY,
        "engine_version": bundle.get("engine_version"),
        "data_version": {
            "path": str(d1_path),
            "mtime_ns": stat.st_mtime_ns,
            "size": stat.st_size,
        },
        "years": bundle.get("years") or WATCHLIST_PREVIEW_YEARS,
        "bars": len(bundle.get("bars") or []),
        "markers": len(markers),
        "cache": {
            "status": "miss",
            "ttl_seconds": WATCHLIST_SIGNAL_PREVIEW_CACHE_TTL_SECONDS,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        },
        "metrics": {
            "trades": metrics.get("trades", 0),
            "win_rate": metrics.get("win_rate", 0.0),
            "total_return": metrics.get("total_return", 0.0),
            "bad_audits": metrics.get("bad_audits", 0),
        },
        "latest_signal": None,
    }
    if latest_entry:
        preview["latest_signal"] = {
            "time": latest_entry.get("t"),
            "side": latest_entry.get("side"),
            "price": latest_entry.get("price"),
            "strategy_id": latest_entry.get("strategy_id") or preview["strategy_id"],
            "trade_no": latest_entry.get("trade_no"),
        }
    return preview


def build_watchlist_signal_preview(d1_path: Path) -> dict[str, Any]:
    key = _signal_preview_cache_key(d1_path)
    now = time.time()
    cached = _SIGNAL_PREVIEW_CACHE.get(key)
    if cached and now - cached[0] <= WATCHLIST_SIGNAL_PREVIEW_CACHE_TTL_SECONDS:
        preview = copy.deepcopy(cached[1])
        cache_meta = dict(preview.get("cache") or {})
        cache_meta["status"] = "hit"
        preview["cache"] = cache_meta
        return preview
    preview = _build_watchlist_signal_preview_uncached(d1_path)
    _SIGNAL_PREVIEW_CACHE[key] = (now, copy.deepcopy(preview))
    return copy.deepcopy(preview)


def build_watchlist_runtime_snapshot(entry: dict[str, Any], *, include_signal_preview: bool = False) -> dict[str, Any]:
    market = _normalize_watchlist_market(str(entry.get("market") or ""))
    symbol = str(entry.get("symbol") or "").upper()
    strategies = list(entry.get("strategies") or ["TOTAL"])
    timeframes = WATCHLIST_RUNTIME_TIMEFRAMES_BY_MARKET.get(market)
    snapshot: dict[str, Any] = {
        "watchlist_id": entry.get("id"),
        "request_id": entry.get("request_id"),
        "user_id": entry.get("user_id"),
        "market": market,
        "symbol": symbol,
        "name": entry.get("name"),
        "strategies": strategies,
        "watchlist_status": entry.get("status"),
        "runtime_status": "unsupported_market" if timeframes is None else "checking",
        "mode": "read_only_observation",
        "timeframes": {},
        "current_price": None,
        "latest_time": None,
        "signal_preview": None,
        "signals": [],
    }
    if timeframes is None:
        snapshot["signals"].append(
            {
                "type": "runtime_binding",
                "severity": "blocked",
                "message": "watchlist runtime does not support this market yet",
            }
        )
        return snapshot

    missing: list[str] = []
    latest_by_tf: dict[str, dict[str, Any]] = {}
    for tf in timeframes:
        key = normalize_timeframe(tf)
        path = runtime_timeframe_csv_path(symbol, market, key)
        if not path.exists():
            missing.append(key)
            snapshot["timeframes"][key] = {"ok": False, "path": str(path), "error": "missing_csv"}
            continue
        try:
            latest = _read_latest_bar(path)
            latest_by_tf[key] = latest
            snapshot["timeframes"][key] = {
                "ok": True,
                "path": str(path),
                "rows": latest["rows"],
                "latest_bar": {k: v for k, v in latest.items() if k != "rows"},
            }
        except Exception as exc:  # noqa: BLE001 - caller displays user-visible diagnostic
            missing.append(key)
            snapshot["timeframes"][key] = {"ok": False, "path": str(path), "error": str(exc)}

    preferred = next((latest_by_tf[tf] for tf in WATCHLIST_RUNTIME_PREFERRED_TIMEFRAMES if tf in latest_by_tf), None)
    if preferred:
        snapshot["current_price"] = preferred["close"]
        snapshot["latest_time"] = preferred["timestamp"]

    if missing:
        snapshot["runtime_status"] = "data_missing"
        snapshot["signals"].append(
            {
                "type": "runtime_binding",
                "severity": "blocked",
                "message": "missing required CSV timeframes",
                "missing_timeframes": missing,
            }
        )
    else:
        snapshot["runtime_status"] = "ready"
        if include_signal_preview and market == "CRYPTO":
            d1_path = runtime_timeframe_csv_path(symbol, market, "D1")
            try:
                snapshot["signal_preview"] = build_watchlist_signal_preview(d1_path)
                snapshot["signals"].append(
                    {
                        "type": "signal_preview",
                        "severity": "info",
                        "message": "read-only D1 signal preview attached; no paper_state writes or order triggers",
                    }
                )
            except Exception as exc:  # noqa: BLE001 - user-visible diagnostics only
                snapshot["signals"].append(
                    {
                        "type": "signal_preview",
                        "severity": "warn",
                        "message": "read-only signal preview unavailable",
                        "error": f"{type(exc).__name__}: {exc}",
                    }
                )
        elif include_signal_preview and market != "CRYPTO":
            snapshot["signals"].append(
                {
                    "type": "signal_preview",
                    "severity": "info",
                    "message": "signal preview not attached for this market yet",
                }
            )
        snapshot["signals"].append(
            {
                "type": "runtime_binding",
                "severity": "info",
                "message": f"{'/'.join(timeframes)} data ready for read-only observation",
            }
        )
    return snapshot


def build_watchlist_runtime_snapshots(
    entries: list[dict[str, Any]],
    *,
    include_signal_preview: bool = False,
) -> list[dict[str, Any]]:
    return [
        build_watchlist_runtime_snapshot(entry, include_signal_preview=include_signal_preview)
        for entry in entries
    ]
