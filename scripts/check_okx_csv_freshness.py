#!/usr/bin/env python3
"""Verify OKX-only crypto CSVs (HYPE/ATH) are not lagging behind UTC now."""
from __future__ import annotations

import argparse
import csv
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services"))

from crypto_ingest import BAR_MAX_LAG_SECONDS, utc_now  # noqa: E402

OKX_ONLY_SYMBOLS = ("HYPEUSDT", "ATHUSDT")
CHECKS = (
    ("15m", "15m"),
    ("1h", "1H"),
    ("1d", "1D"),
)


def _parse_last_ts(text: str) -> datetime:
    text = text.strip()
    if len(text) <= 10:
        return datetime.strptime(text, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    return datetime.strptime(text, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)


def _read_last_timestamp(path: Path) -> datetime | None:
    if not path.is_file():
        return None
    last_row: dict[str, str] | None = None
    with path.open(encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            last_row = row
    if not last_row:
        return None
    key = "timestamp" if "timestamp" in last_row else "date"
    return _parse_last_ts(str(last_row[key]))


def check_symbol(symbol: str, *, data_dir: Path) -> list[dict]:
    sym = symbol.upper()
    out: list[dict] = []
    for folder, bar in CHECKS:
        path = data_dir / folder / f"{sym}.csv"
        last_dt = _read_last_timestamp(path)
        max_lag = BAR_MAX_LAG_SECONDS.get(bar, 86400)
        if last_dt is None:
            out.append({"symbol": sym, "tf": folder, "status": "missing", "path": str(path)})
            continue
        lag = int(utc_now().timestamp() - last_dt.timestamp())
        status = "ok" if lag <= max_lag else "stale"
        out.append(
            {
                "symbol": sym,
                "tf": folder,
                "status": status,
                "last": last_dt.strftime("%Y-%m-%d %H:%M:%S"),
                "lag_sec": lag,
                "max_lag_sec": max_lag,
                "path": str(path),
            }
        )
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="Check OKX-only crypto CSV freshness.")
    parser.add_argument("--root", default=str(ROOT))
    parser.add_argument("--symbols", default=",".join(OKX_ONLY_SYMBOLS))
    args = parser.parse_args()
    data_dir = Path(args.root) / "data"
    rows: list[dict] = []
    failed = 0
    for item in args.symbols.split(","):
        sym = item.strip()
        if not sym:
            continue
        for row in check_symbol(sym, data_dir=data_dir):
            rows.append(row)
            print(row)
            if row["status"] in {"missing", "stale"}:
                failed += 1
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
