"""WEB-CUSTOM-002: on-demand D1 ingest for FUTURES / A_STOCK / US_STOCK custom requests."""
from __future__ import annotations

import os
import shutil
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DATA_A_STOCK = ROOT / "data" / "a_stock"
DATA_US_STOCK = ROOT / "data" / "us_stock"
DATA_FUTURES_1D = ROOT / "data" / "futures" / "1d"
MIN_D1_ROWS = 30


def _prepare_futures_env() -> None:
    if not os.getenv("FUTURES_DATA_DIR"):
        os.environ["FUTURES_DATA_DIR"] = str(ROOT / "data" / "futures")
    if not os.getenv("FUTURES_LOG_DIR"):
        os.environ["FUTURES_LOG_DIR"] = str(ROOT / "runtime" / "logs" / "futures_ingest")


def _years_to_bounds(years: int) -> tuple[str, str]:
    yrs = max(1, min(int(years), 10))
    end = datetime.now(timezone.utc).date()
    start = end - timedelta(days=yrs * 365)
    return start.strftime("%Y%m%d"), end.strftime("%Y%m%d")


def _row_count(path: Path) -> int:
    if not path.exists() or path.stat().st_size <= 5:
        return 0
    try:
        import pandas as pd

        frame = pd.read_csv(path)
        return len(frame.dropna(how="all"))
    except Exception:
        return 0


def ingest_a_stock_d1(symbol: str, *, years: int = 5) -> dict[str, Any]:
    from backtest_a_stock_fengji import fetch_kline_with_fallback, normalize_code

    code = normalize_code(symbol)
    start, end = _years_to_bounds(years)
    out_path = DATA_A_STOCK / f"{code}_1D_qfq.csv"
    frame, source = fetch_kline_with_fallback(
        code,
        eastmoney_klt=101,
        sina_scale=240,
        start=start,
        end=end,
        fqt=1,
        cache_path=out_path,
        refresh=True,
    )
    rows = len(frame)
    if rows < MIN_D1_ROWS:
        raise ValueError(f"A-share D1 too short for {code}: {rows} rows")
    return {
        "market": "A_STOCK",
        "symbol": code,
        "timeframe": "D1",
        "rows": rows,
        "start": str(frame["date"].iloc[0]),
        "end": str(frame["date"].iloc[-1]),
        "source": source,
        "path": str(out_path),
    }


def ingest_us_stock_d1(symbol: str, *, years: int = 5) -> dict[str, Any]:
    from us_stock_data import fetch_us_kline, normalize_ticker

    ticker = normalize_ticker(symbol.replace("_", "."))
    file_key = ticker.replace(".", "_")
    start = (datetime.now(timezone.utc).date() - timedelta(days=max(1, int(years)) * 365)).strftime("%Y-%m-%d")
    end = (datetime.now(timezone.utc).date() + timedelta(days=1)).strftime("%Y-%m-%d")
    out_path = DATA_US_STOCK / f"{file_key}_1D.csv"
    frame = fetch_us_kline(
        ticker,
        "1d",
        start,
        end,
        out_path,
        source="auto",
        refresh=True,
        pause_seconds=0.8,
    )
    rows = len(frame)
    if rows < MIN_D1_ROWS:
        raise ValueError(f"US stock D1 too short for {ticker}: {rows} rows")
    return {
        "market": "US_STOCK",
        "symbol": file_key,
        "timeframe": "D1",
        "rows": rows,
        "start": str(frame["date"].iloc[0]),
        "end": str(frame["date"].iloc[-1]),
        "source": "yahoo_chart|yfinance",
        "path": str(out_path),
    }


def ingest_futures_d1(symbol: str) -> dict[str, Any]:
    _prepare_futures_env()
    import data_manager_futures as dm

    short_code = str(symbol or "").strip().upper()
    tq_code = dm.TQ_SYMBOL_MAP.get(short_code)
    if not tq_code:
        supported = ", ".join(sorted(dm.TQ_SYMBOL_MAP.keys())[:12])
        raise ValueError(
            f"futures symbol '{short_code}' is not in domestic TQ map; "
            f"custom ingest currently supports mapped symbols only (e.g. {supported}…)"
        )

    api = dm.connect_api()
    try:
        ok = dm.fetch_symbol(api, short_code, tq_code)
    finally:
        api.close()

    if not ok:
        raise RuntimeError(f"天勤抓取 {short_code} 失败，请检查 TQ 账号或品种映射")

    DATA_FUTURES_1D.mkdir(parents=True, exist_ok=True)
    source_path = dm.DATA_DIR / "1d" / f"{short_code}.csv"
    if not source_path.exists():
        source_path = dm.DATA_DIR / "1d" / f"{short_code}USDT.csv"
    if not source_path.exists():
        raise FileNotFoundError(f"futures ingest finished but csv missing for {short_code}")

    dest_path = DATA_FUTURES_1D / f"{short_code}.csv"
    shutil.copy2(source_path, dest_path)
    rows = _row_count(dest_path)
    if rows < MIN_D1_ROWS:
        raise ValueError(f"futures D1 too short for {short_code}: {rows} rows")

    manifest_path = dm.MAIN_CONTRACT_MANIFEST
    data_contract = ""
    if manifest_path.exists():
        try:
            import json

            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            entry = (manifest.get("symbols") or {}).get(short_code) or {}
            data_contract = str(entry.get("data_contract") or entry.get("underlying_symbol") or "")
        except Exception:
            data_contract = ""

    return {
        "market": "FUTURES",
        "symbol": short_code,
        "timeframe": "D1",
        "rows": rows,
        "source": "tq_actual_main_contract",
        "tq_code": tq_code,
        "data_contract": data_contract,
        "path": str(dest_path),
    }


def ingest_custom_market_d1(market: str, symbol: str, *, years: int = 1) -> dict[str, Any]:
    mkt = str(market or "").strip().upper()
    if mkt in {"A_STOCK", "ASTOCK"}:
        return ingest_a_stock_d1(symbol, years=years)
    if mkt in {"US_STOCK", "USSTOCK"}:
        return ingest_us_stock_d1(symbol, years=years)
    if mkt in {"FUTURES", "CN_FUTURES"}:
        return ingest_futures_d1(symbol)
    raise ValueError(f"unsupported custom ingest market: {market}")
