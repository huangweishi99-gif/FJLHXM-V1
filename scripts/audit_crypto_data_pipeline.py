#!/usr/bin/env python3
"""Audit overseas crypto data source, refresh, fallback, and freshness contracts."""
from __future__ import annotations

import argparse
import csv
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]

EXPECTED_BINANCE_SYMBOLS = {
    "BTCUSDT",
    "ETHUSDT",
    "SOLUSDT",
    "AVAXUSDT",
    "TRUMPUSDT",
    "RENDERUSDT",
    "IOUSDT",
    "TAOUSDT",
    "DASHUSDT",
    "LTCUSDT",
    "DOGEUSDT",
    "ADAUSDT",
    "APTUSDT",
    "LINKUSDT",
    "BNBUSDT",
    "ZECUSDT",
}
EXPECTED_OKX_FALLBACK_SYMBOLS = {"HYPEUSDT", "ATHUSDT"}
EXPECTED_TIMEFRAME_FOLDERS = {"15m", "1h", "1d"}


@dataclass(frozen=True)
class CheckResult:
    name: str
    ok: bool
    detail: str

    def as_dict(self) -> dict[str, Any]:
        return {"name": self.name, "ok": self.ok, "detail": self.detail}


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def normalized(text: str) -> str:
    return text.replace("\\", "/")


def check_contains(name: str, text: str, expected: list[str]) -> CheckResult:
    body = normalized(text)
    missing = [item for item in expected if normalized(item) not in body]
    return CheckResult(name, not missing, "missing=" + ",".join(missing) if missing else "ok")


def extract_quoted_symbols(text: str) -> set[str]:
    return {match.group(1).upper() for match in re.finditer(r"['\"]([A-Z0-9]+USDT)['\"]", text)}


def check_binance_data_manager(root: Path) -> CheckResult:
    text = read_text(root / "data_manager.py")
    symbols = extract_quoted_symbols(text)
    missing = sorted(EXPECTED_BINANCE_SYMBOLS - symbols)
    unexpected_okx = sorted(EXPECTED_OKX_FALLBACK_SYMBOLS & symbols)
    required = [
        "from binance.client import Client",
        "KLINE_INTERVAL_1DAY",
        "KLINE_INTERVAL_1HOUR",
        "KLINE_INTERVAL_15MINUTE",
        "read_existing_klines",
        "atomic_save_csv",
        "get_historical_klines",
        "time.sleep(600)",
    ]
    missing_tokens = [item for item in required if item not in text]
    ok = not missing and not unexpected_okx and not missing_tokens
    detail = (
        f"symbols={len(EXPECTED_BINANCE_SYMBOLS)} missing={missing} "
        f"unexpected_okx={unexpected_okx} missing_tokens={missing_tokens}"
    )
    return CheckResult("crypto_binance_data_manager_contract", ok, detail)


def check_okx_fallback_sync(root: Path) -> CheckResult:
    text = read_text(root / "scripts" / "sync_missing_crypto_15m.py")
    missing = []
    for symbol in EXPECTED_OKX_FALLBACK_SYMBOLS:
        if symbol not in text:
            missing.append(symbol)
    for token in [
        "OKX_ONLY_SYMBOLS",
        '"M15"',
        '"D1"',
        '"H1"',
        "default_days",
        "ingest_crypto_timeframe_csv",
        "BinanceAPIException",
        "Invalid symbol",
        "update_manifest",
        "--force-okx",
        "--fix-os",
        "rebuild_one",
    ]:
        if token not in text:
            missing.append(token)
    return CheckResult("crypto_okx_fallback_sync_contract", not missing, "missing=" + ",".join(missing) if missing else "ok")


def check_okx_ingest(root: Path) -> CheckResult:
    text = read_text(root / "services" / "crypto_ingest.py")
    missing = []
    for token in [
        "https://www.okx.com/api/v5/market/history-candles",
        "TIMEFRAME_CONFIG",
        '"D1"',
        '"H1"',
        '"M15"',
        "BAR_MAX_LAG_SECONDS",
        "validate_okx_freshness",
        "utc_now()",
        "_atomic_write_csv",
        "refuse to save empty crypto frame",
    ]:
        if token not in text:
            missing.append(token)
    return CheckResult("crypto_okx_ingest_contract", not missing, "missing=" + ",".join(missing) if missing else "ok")


def check_okx_freshness_script(root: Path) -> CheckResult:
    text = read_text(root / "scripts" / "check_okx_csv_freshness.py")
    missing = []
    for token in [
        "OKX_ONLY_SYMBOLS",
        "HYPEUSDT",
        "ATHUSDT",
        '("15m", "15m")',
        '("1h", "1H")',
        '("1d", "1D")',
        "BAR_MAX_LAG_SECONDS",
        "status = \"ok\" if lag <= max_lag else \"stale\"",
    ]:
        if token not in text:
            missing.append(token)
    return CheckResult("crypto_okx_freshness_contract", not missing, "missing=" + ",".join(missing) if missing else "ok")


def check_overseas_watchdog(root: Path) -> CheckResult:
    text = read_text(root / "scripts" / "watchdog_overseas.sh")
    return check_contains(
        "crypto_overseas_watchdog_data_contract",
        text,
        [
            'DATA_STALE_LIMIT="${WATCHDOG_DATA_STALE_LIMIT:-1800}"',
            'OKX_15M_INTERVAL="${WATCHDOG_OKX_15M_INTERVAL:-600}"',
            "run_okx_15m_sync",
            "sync_missing_crypto_15m.py",
            "--symbols HYPEUSDT,ATHUSDT",
            "--timeframes M15,D1,H1",
            "--force-okx",
            "--fix-os",
            "check_okx_csv_freshness.py",
            "data_stale",
            "newest_mtime_in",
            "data/15m",
            "CMD_DATA",
            "data_manager.py",
        ],
    )


def check_overseas_runtime_script(root: Path) -> CheckResult:
    path = root / "scripts" / "check_overseas_runtime_status.ps1"
    if not path.exists():
        return CheckResult(
            "crypto_overseas_runtime_check_contract",
            True,
            "skipped: local SSH helper is not deployed on this host",
        )
    return check_contains(
        "crypto_overseas_runtime_check_contract",
        read_text(path),
        [
            "find data -maxdepth 2 -type f -name '*.csv'",
            "FENGJI_MARKET=${FENGJI_MARKET:-crypto}",
            "summarize_pending_effective_status.py",
            "runtime/fengji_radar/radar.json",
            "runtime/fengji_pending_orders/pending_orders.json",
        ],
    )


def parse_last_timestamp(path: Path) -> datetime | None:
    if not path.is_file():
        return None
    last: dict[str, str] | None = None
    try:
        with path.open(encoding="utf-8", newline="") as f:
            for row in csv.DictReader(f):
                last = row
    except Exception:
        return None
    if not last:
        return None
    text = str(last.get("timestamp") or last.get("date") or "").strip()
    if not text:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(text[:19] if fmt.endswith("%S") else text[:10], fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def csv_freshness_snapshot(root: Path) -> dict[str, Any]:
    data_dir = root / "data"
    rows: list[dict[str, Any]] = []
    now = datetime.now(timezone.utc)
    symbols = sorted(EXPECTED_BINANCE_SYMBOLS | EXPECTED_OKX_FALLBACK_SYMBOLS)
    for folder in sorted(EXPECTED_TIMEFRAME_FOLDERS):
        for symbol in symbols:
            path = data_dir / folder / f"{symbol}.csv"
            last_dt = parse_last_timestamp(path)
            if last_dt is None:
                rows.append({"symbol": symbol, "tf": folder, "available": False})
                continue
            rows.append(
                {
                    "symbol": symbol,
                    "tf": folder,
                    "available": True,
                    "last": last_dt.strftime("%Y-%m-%d %H:%M:%S"),
                    "lag_sec": int(now.timestamp() - last_dt.timestamp()),
                }
            )
    available = [row for row in rows if row.get("available")]
    by_tf = {}
    for folder in sorted(EXPECTED_TIMEFRAME_FOLDERS):
        tf_rows = [row for row in rows if row["tf"] == folder]
        lags = [int(row["lag_sec"]) for row in tf_rows if row.get("available") and "lag_sec" in row]
        by_tf[folder] = {
            "available": sum(1 for row in tf_rows if row.get("available")),
            "expected": len(symbols),
            "max_lag_sec": max(lags) if lags else None,
        }
    return {
        "symbols_expected": len(symbols),
        "rows_checked": len(rows),
        "available_total": len(available),
        "by_tf": by_tf,
        "missing_sample": [row for row in rows if not row.get("available")][:10],
        "stale_top": sorted(
            [row for row in rows if row.get("available") and "lag_sec" in row],
            key=lambda row: int(row["lag_sec"]),
            reverse=True,
        )[:10],
    }


def run_checks(root: Path = ROOT) -> list[CheckResult]:
    return [
        check_binance_data_manager(root),
        check_okx_fallback_sync(root),
        check_okx_ingest(root),
        check_okx_freshness_script(root),
        check_overseas_watchdog(root),
        check_overseas_runtime_script(root),
    ]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit overseas crypto data pipeline contracts.")
    parser.add_argument("--root", default=str(ROOT))
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = Path(args.root).resolve()
    checks = run_checks(root)
    failures = [check for check in checks if not check.ok]
    payload = {
        "checks": [check.as_dict() for check in checks],
        "failures": len(failures),
        "runtime": csv_freshness_snapshot(root),
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
