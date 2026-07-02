"""Discover tradable/chartable symbols from local CSV caches (merge with PG context stats)."""
from __future__ import annotations

import re
from pathlib import Path

from fengji_core.symbol_names import FUTURES_CN_NAMES, a_stock_name, normalize_a_stock_symbol

ROOT = Path(__file__).resolve().parents[1]
FUTURES_CN_TO_CODE = {cn: code for code, cn in FUTURES_CN_NAMES.items()}
FUTURES_SHORT_CODES = frozenset(FUTURES_CN_NAMES.keys())


def _unique_sorted(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        key = item.strip().upper()
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(key)
    return sorted(out)


def list_a_stock_csv_symbols() -> list[str]:
    folder = ROOT / "data" / "a_stock"
    if not folder.is_dir():
        return []
    codes: list[str] = []
    for path in folder.glob("*_1D_qfq.csv"):
        m = re.match(r"^(\d{6})_", path.name)
        if m:
            codes.append(m.group(1))
    return _unique_sorted(codes)


def list_futures_csv_symbols() -> list[str]:
    names: list[str] = []
    for folder in (ROOT / "data" / "futures" / "1d", ROOT / "data" / "futures_lc" / "1d", ROOT / "data" / "1d"):
        if not folder.is_dir():
            continue
        for path in folder.glob("*.csv"):
            stem = path.stem.strip()
            if not stem:
                continue
            # data/1d/*USDT.csv 是 crypto 或国内期货误标，不得进入期货目录
            if stem.upper().endswith("USDT"):
                continue
            if "corrupt" in stem.lower():
                continue
            names.append(stem)
    return _unique_sorted(names)


def _futures_match_key(symbol: str) -> str:
    text = str(symbol or "").strip()
    upper = text.upper().replace("USDT", "")
    if upper in FUTURES_CN_NAMES:
        return upper
    if text in FUTURES_CN_TO_CODE:
        return FUTURES_CN_TO_CODE[text]
    return upper or text


def list_crypto_csv_symbols() -> list[str]:
    codes: list[str] = []
    overseas = ROOT / "data" / "overseas_1d"
    if overseas.is_dir():
        for path in overseas.glob("*.csv"):
            sym = path.stem.upper()
            if sym.endswith("USDT"):
                codes.append(sym)
    okx = ROOT / "data" / "crypto_okx"
    if okx.is_dir():
        for path in okx.glob("*_1825d.csv"):
            base = path.name.split("_")[0].upper().replace("-", "")
            if base and not base.endswith("USDT"):
                base = f"{base}USDT"
            codes.append(base)
    legacy = ROOT / "data" / "1d"
    if legacy.is_dir():
        for path in legacy.glob("*USDT.csv"):
            base = path.stem.upper().removesuffix("USDT")
            # 国内期货短代码误写成 AGUSDT/BRUSDT/ECUSDT 等，不是 crypto
            if base in FUTURES_SHORT_CODES:
                continue
            codes.append(path.stem.upper())
    return _unique_sorted(codes)


def list_us_stock_csv_symbols() -> list[str]:
    folder = ROOT / "data" / "us_stock"
    if not folder.is_dir():
        return []
    codes: list[str] = []
    for path in folder.glob("*_1D.csv"):
        codes.append(path.stem.replace("_1D", "").upper())
    return _unique_sorted(codes)


def list_local_chart_symbols(market: str) -> list[str]:
    mkt = market.strip().upper()
    if mkt in {"A_STOCK", "ASTOCK"}:
        return list_a_stock_csv_symbols()
    if mkt in {"FUTURES", "CN_FUTURES"}:
        return list_futures_csv_symbols()
    if mkt == "CRYPTO":
        return list_crypto_csv_symbols()
    if mkt in {"US_STOCK", "USSTOCK"}:
        return list_us_stock_csv_symbols()
    return []


def _symbol_match_key(market: str, symbol: str) -> str:
    mkt = market.strip().upper()
    sym = str(symbol or "").strip()
    if mkt in {"A_STOCK", "ASTOCK"} and sym.isdigit():
        return normalize_a_stock_symbol(sym)
    if mkt in {"FUTURES", "CN_FUTURES"}:
        return _futures_match_key(sym)
    return sym.upper()


def _enrich_display_fields(market: str, symbol: str) -> tuple[str, str]:
    mkt = market.strip().upper()
    sym = str(symbol or "").strip()
    if mkt in {"A_STOCK", "ASTOCK"} and sym.isdigit():
        display = normalize_a_stock_symbol(sym)
        return display, a_stock_name(display) or ""
    if mkt in {"FUTURES", "CN_FUTURES"}:
        code = _futures_match_key(sym)
        cn = FUTURES_CN_NAMES.get(code) or sym
        short = f"{cn}({code})" if cn and code and cn != code else (cn or code)
        return short, cn
    return sym.upper(), ""


def merge_symbol_summary(pg_rows: list[dict], market: str, *, chart_symbols: list[str] | None = None) -> list[dict]:
    """Merge PG context stats with local CSV catalog; PG rows win on stats."""
    mkt = market.strip().upper()
    symbols = chart_symbols if chart_symbols is not None else list_local_chart_symbols(mkt)
    by_key: dict[str, dict] = {}

    for row in pg_rows:
        item = dict(row)
        key = _symbol_match_key(mkt, str(item.get("symbol", "")))
        item.setdefault("has_pg_context", True)
        by_key[key] = item

    for sym in symbols:
        key = _symbol_match_key(mkt, sym)
        display, name = _enrich_display_fields(mkt, sym)
        if key in by_key:
            existing = by_key[key]
            if mkt in {"A_STOCK", "ASTOCK"}:
                existing.setdefault("display_symbol", display)
                if name and not existing.get("symbol_name"):
                    existing["symbol_name"] = name
            elif mkt in {"FUTURES", "CN_FUTURES"}:
                existing["display_symbol"] = display
                if name:
                    existing["symbol_name"] = name
            continue
        # Chart-only: futures/A股 keep CSV/PG 惯用 symbol（期货中文名、A 股 6 位码）
        api_symbol = sym
        if mkt in {"A_STOCK", "ASTOCK"}:
            api_symbol = normalize_a_stock_symbol(sym)
        row = {
            "market": mkt,
            "symbol": api_symbol,
            "display_symbol": display,
            "symbol_name": name,
            "trade_count": 0,
            "strategy_count": 0,
            "first_entry_time": None,
            "last_entry_time": None,
            "has_pg_context": False,
        }
        by_key[key] = row

    def sort_key(row: dict) -> tuple:
        tc = int(row.get("trade_count") or 0)
        label = str(row.get("display_symbol") or row.get("symbol") or "")
        return (0 if tc > 0 else 1, -tc, label)

    return sorted(by_key.values(), key=sort_key)
