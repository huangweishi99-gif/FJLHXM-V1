"""PVC search must hit futures PVC, not US stock V."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

FUTURES_CN_NAMES = {
    "V": "PVC",
    "M": "豆粕",
}


def _futures_code_from_alias(text: str) -> str:
    sym = text.strip().upper()
    if not sym:
        return ""
    if sym in FUTURES_CN_NAMES:
        return sym
    for code, name in FUTURES_CN_NAMES.items():
        if name.strip().upper() == sym:
            return code
    return ""


def _is_futures_market(market: str) -> bool:
    return market.strip().upper() in {"FUTURES", "CN_FUTURES"}


def _catalog_row_search_score(row: dict, query: str) -> int:
    q = query.strip().upper()
    if not q:
        return 0
    sym = str(row.get("symbol") or "").strip().upper()
    market = str(row.get("market") or "").strip().upper()
    name = str(row.get("symbol_name") or "").strip().upper()
    display = str(row.get("display_symbol") or sym).strip().upper()
    alias_code = _futures_code_from_alias(q)

    if sym == q:
        return 1000
    if name == q:
        return 980
    if display == q:
        return 960
    if _is_futures_market(market):
        if alias_code and sym == alias_code and FUTURES_CN_NAMES.get(sym, "").upper() == q:
            return 950
        if sym == q or name == q:
            return 940
        if alias_code and (sym == alias_code or sym == q):
            return 930
        if FUTURES_CN_NAMES.get(sym, "").upper() == q:
            return 920
    if display.startswith(q):
        return 800
    if sym.startswith(q):
        return 780
    if name.startswith(q):
        return 760
    if q in display:
        return 600
    if q in name:
        return 580
    if q in sym:
        return 560
    return 0


def _catalog_row_matches_query(row: dict, query: str) -> bool:
    q = query.strip().upper()
    if not q:
        return True
    if _catalog_row_search_score(row, q) <= 0:
        return False
    code = str(row.get("symbol") or "").strip().upper()
    alias_code = _futures_code_from_alias(q)
    if alias_code and code == alias_code and q != alias_code:
        return _is_futures_market(str(row.get("market") or ""))
    return True


def test_pvc_query_matches_futures_not_us_stock_v() -> None:
    fut_pvc = {
        "market": "FUTURES",
        "symbol": "PVC",
        "display_symbol": "PVC(V)",
        "symbol_name": "PVC",
    }
    us_v = {
        "market": "US_STOCK",
        "symbol": "V",
        "display_symbol": "V",
        "symbol_name": "",
    }
    assert _catalog_row_matches_query(fut_pvc, "pvc")
    assert not _catalog_row_matches_query(us_v, "pvc")
    assert _catalog_row_search_score(fut_pvc, "PVC") > _catalog_row_search_score(us_v, "PVC")


def test_app_js_exports_sort_catalog_rows_by_query() -> None:
    js = (ROOT / "web" / "js" / "app.js").read_text(encoding="utf-8")
    assert "sortCatalogRowsByQuery" in js
    assert "isFuturesMarket" in js
