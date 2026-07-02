"""美股 OHLCV 下载：优先 Yahoo Chart API（免 Key），yfinance 作备用。"""
from __future__ import annotations

import json
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote as url_quote
from urllib.request import Request, urlopen

import pandas as pd

YAHOO_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
YAHOO_CHART = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"


def normalize_ticker(value: str) -> str:
    import re

    text = str(value).strip().upper().replace(".", "-")
    return re.sub(r"[^A-Z0-9-]", "", text)


def _filter_dates(frame: pd.DataFrame, start: str, end: str) -> pd.DataFrame:
    out = frame.copy()
    if start:
        start_dt = pd.to_datetime(start, errors="coerce")
        if not pd.isna(start_dt):
            out = out[out["date"] >= start_dt]
    if end:
        end_dt = pd.to_datetime(end, errors="coerce")
        if not pd.isna(end_dt):
            out = out[out["date"] <= end_dt]
    return out.reset_index(drop=True)


def _normalize_ohlcv(frame: pd.DataFrame, source: str, ticker: str) -> pd.DataFrame:
    if frame.empty:
        raise ValueError(f"{source} kline empty for {ticker}")
    out = frame.copy()
    if "date" not in out.columns:
        raise ValueError(f"{source} missing date for {ticker}")
    out["date"] = pd.to_datetime(out["date"], errors="coerce")
    for col in ["open", "high", "low", "close", "volume"]:
        if col not in out.columns:
            out[col] = 0.0 if col == "volume" else float("nan")
        out[col] = pd.to_numeric(out[col], errors="coerce")
    out = out[["date", "open", "high", "low", "close", "volume"]]
    out = out.dropna(subset=["date", "open", "high", "low", "close"])
    out = out.drop_duplicates("date").sort_values("date").reset_index(drop=True)
    if out.empty:
        raise ValueError(f"{source} empty after clean for {ticker}")
    return out


def fetch_yahoo_chart_kline(
    ticker: str,
    interval: str,
    start: str,
    end: str,
    *,
    pause_seconds: float = 0.8,
) -> pd.DataFrame:
    """Yahoo Chart API：interval=1d 或 60m；无需 API Key。"""
    symbol = url_quote(normalize_ticker(ticker), safe="-")
    yahoo_interval = "60m" if interval in {"1h", "60m", "h1"} else "1d"
    start_dt = pd.to_datetime(start, errors="coerce")
    end_dt = pd.to_datetime(end, errors="coerce")
    if pd.isna(start_dt):
        start_dt = pd.Timestamp("2018-01-01")
    if pd.isna(end_dt):
        end_dt = pd.Timestamp.now()

    period1 = int(start_dt.timestamp())
    period2 = min(int(end_dt.timestamp()), int(pd.Timestamp.now().timestamp()))
    if yahoo_interval == "60m":
        url = f"{YAHOO_CHART.format(symbol=symbol)}?range=730d&interval=60m&includePrePost=false"
    else:
        url = f"{YAHOO_CHART.format(symbol=symbol)}?period1={period1}&period2={period2}&interval=1d&includePrePost=false"

    last_exc: Exception | None = None
    for attempt in range(6):
        if attempt > 0:
            wait = min(60, 2 * (2**attempt))
            print(f"{ticker}: yahoo_chart retry {attempt}/5 after {wait}s ({last_exc})")
            time.sleep(wait)
        try:
            req = Request(url, headers={"User-Agent": YAHOO_UA})
            payload = json.loads(urlopen(req, timeout=45).read())
            result = (payload.get("chart") or {}).get("result") or []
            if not result:
                last_exc = RuntimeError("empty chart result")
                continue
            block = result[0]
            ts = block.get("timestamp") or []
            quote_block = (block.get("indicators") or {}).get("quote") or [{}]
            q = quote_block[0] if quote_block else {}
            rows = []
            for i, t in enumerate(ts):
                if t is None:
                    continue
                close = (q.get("close") or [None])[i] if i < len(q.get("close") or []) else None
                if close is None:
                    continue
                rows.append(
                    {
                        "date": pd.to_datetime(int(t), unit="s"),
                        "open": (q.get("open") or [None])[i],
                        "high": (q.get("high") or [None])[i],
                        "low": (q.get("low") or [None])[i],
                        "close": close,
                        "volume": (q.get("volume") or [0])[i] or 0,
                    }
                )
            frame = _normalize_ohlcv(pd.DataFrame(rows), f"yahoo_chart:{yahoo_interval}", ticker)
            if pause_seconds > 0:
                time.sleep(pause_seconds)
            return frame
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError, ValueError) as exc:
            last_exc = exc
            msg = str(exc).lower()
            if "429" in msg or "too many" in msg or "rate" in msg or "empty" in msg:
                continue
            raise
    raise RuntimeError(f"yahoo_chart failed for {ticker}: {last_exc}") from last_exc


def fetch_yfinance_kline_fallback(
    ticker: str,
    interval: str,
    start: str,
    end: str,
) -> pd.DataFrame:
    import yfinance as yf

    yf_interval = "1h" if interval in {"1h", "60m", "h1"} else "1d"
    raw = yf.download(
        normalize_ticker(ticker),
        start=pd.to_datetime(start, errors="coerce"),
        end=pd.to_datetime(end, errors="coerce"),
        interval=yf_interval,
        auto_adjust=True,
        progress=False,
        threads=False,
    )
    if raw is None or raw.empty:
        raw = yf.Ticker(normalize_ticker(ticker)).history(
            start=start,
            end=end,
            interval=yf_interval,
            auto_adjust=True,
        )
    out = raw.reset_index()
    rename = {}
    for col in out.columns:
        low = str(col).lower()
        if low in {"date", "datetime", "index"}:
            rename[col] = "date"
        elif low in {"open", "high", "low", "close", "volume"}:
            rename[col] = low
    out = out.rename(columns=rename)
    return _normalize_ohlcv(out, f"yfinance:{yf_interval}", ticker)


def fetch_us_kline(
    ticker: str,
    interval: str,
    start: str,
    end: str,
    cache_path: Path,
    *,
    source: str = "auto",
    refresh: bool = False,
    pause_seconds: float = 0.8,
) -> pd.DataFrame:
    """下载并缓存美股 K 线。source: auto | yahoo_chart | yfinance"""
    if cache_path.exists() and not refresh:
        frame = pd.read_csv(cache_path)
        if not frame.empty:
            frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
            frame = frame.dropna(subset=["date"])
            if len(frame) > 50:
                return _filter_dates(frame, start, end)

    sources = []
    mode = source.strip().lower()
    if mode == "auto":
        sources = ["yahoo_chart", "yfinance"]
    else:
        sources = [mode]

    last_exc: Exception | None = None
    for name in sources:
        try:
            if name == "yahoo_chart":
                frame = fetch_yahoo_chart_kline(
                    ticker, interval, start, end, pause_seconds=pause_seconds if name == sources[-1] else 0.0
                )
            elif name == "yfinance":
                frame = fetch_yfinance_kline_fallback(ticker, interval, start, end)
            else:
                raise ValueError(f"unknown source: {name}")
            frame = _filter_dates(frame, start, end)
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            frame.to_csv(cache_path, index=False, encoding="utf-8-sig")
            return frame
        except Exception as exc:
            last_exc = exc
            print(f"{ticker}: {name} failed: {exc}")
    raise RuntimeError(f"all US data sources failed for {ticker}: {last_exc}") from last_exc
