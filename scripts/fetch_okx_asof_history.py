#!/usr/bin/env python
"""Fetch an OKX historical candle window ending at a fixed as-of time."""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import pandas as pd


def fetch_okx_asof(inst_id: str, bar: str, days: int, end: pd.Timestamp, out: Path) -> pd.DataFrame:
    url = "https://www.okx.com/api/v5/market/history-candles"
    end_utc = pd.Timestamp(end).tz_localize("UTC") if pd.Timestamp(end).tzinfo is None else pd.Timestamp(end).tz_convert("UTC")
    start = end_utc - pd.Timedelta(days=days)
    rows: list[list[str]] = []
    cursor = str(int(end_utc.timestamp() * 1000))

    while True:
        params = {"instId": inst_id, "bar": bar, "limit": "300", "after": cursor}
        last_exc: Exception | None = None
        for attempt in range(4):
            try:
                request = Request(f"{url}?{urlencode(params)}", headers={"User-Agent": "Mozilla/5.0"})
                with urlopen(request, timeout=30) as response:
                    payload = json.loads(response.read().decode("utf-8"))
                last_exc = None
                break
            except Exception as exc:
                last_exc = exc
                time.sleep(0.8 * (attempt + 1))
        if last_exc is not None:
            raise last_exc
        if payload.get("code") != "0":
            raise ValueError(f"OKX error for {inst_id} {bar}: {payload}")
        batch = payload.get("data", [])
        if not batch:
            break
        rows.extend(batch)
        oldest_date = pd.to_datetime(int(batch[-1][0]), unit="ms")
        cursor = batch[-1][0]
        if oldest_date <= start or len(batch) < 300:
            break
        time.sleep(0.08)

    if not rows:
        raise ValueError(f"No OKX rows downloaded for {inst_id} {bar}")
    frame = pd.DataFrame(
        rows,
        columns=["ts", "open", "high", "low", "close", "volume", "vol_ccy", "vol_ccy_quote", "confirm"],
    )
    frame["date"] = pd.to_datetime(pd.to_numeric(frame["ts"]), unit="ms", utc=True)
    for col in ["open", "high", "low", "close", "volume"]:
        frame[col] = pd.to_numeric(frame[col], errors="coerce")
    # Use an open-left interval so a 180d as-of window starts at the next full bar,
    # matching the monitor cache generated at that time.
    frame = frame[(frame["date"] > start) & (frame["date"] <= end_utc)]
    frame = (
        frame[["date", "open", "high", "low", "close", "volume"]]
        .dropna()
        .drop_duplicates("date")
        .sort_values("date")
        .reset_index(drop=True)
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(out, index=False, encoding="utf-8")
    return frame


def main() -> int:
    parser = argparse.ArgumentParser(description="Fetch OKX bars as they would have existed at a fixed end time.")
    parser.add_argument("--symbol", required=True, help="OKX instId, e.g. XRP-USDT")
    parser.add_argument("--bar", default="15m")
    parser.add_argument("--days", type=int, default=180)
    parser.add_argument("--end", required=True, help="UTC-like naive timestamp, e.g. 2026-05-20 03:45:00")
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    frame = fetch_okx_asof(args.symbol, args.bar, args.days, pd.Timestamp(args.end), Path(args.out))
    print(f"saved {len(frame)} rows -> {args.out}")
    if not frame.empty:
        print(f"range {frame['date'].iloc[0]} -> {frame['date'].iloc[-1]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
