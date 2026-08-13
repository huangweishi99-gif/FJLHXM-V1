#!/usr/bin/env python
"""Wave 1 D4a: HTTP smoke for backtest symbol-summary + chart-bundle (four markets)."""
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

DEFAULT_SAMPLES = {
    "A_STOCK": {"symbol": "000021", "strategy_id": "DS01"},
    "FUTURES": {"symbol": "RB", "strategy_id": "DS01"},
    "CRYPTO": {"symbol": "SOLUSDT", "strategy_id": "DS03"},
    "US_STOCK": {"symbol": "NVDA", "strategy_id": "DS01"},
}


def get_json(base: str, path: str, params: dict | None = None, timeout: float = 15.0) -> tuple[int, object]:
    url = base.rstrip("/") + path
    if params:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8")
            return resp.status, json.loads(body) if body else {}
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        try:
            detail = json.loads(body)
        except json.JSONDecodeError:
            detail = body[:500]
        return exc.code, detail


def main() -> int:
    parser = argparse.ArgumentParser(description="Backtest page API smoke (4 markets).")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--base-url", default="")
    args = parser.parse_args()
    base = args.base_url or f"http://127.0.0.1:{args.port}"

    health_status, health = get_json(base, "/api/v1/health")
    if health_status != 200:
        print(f"FAIL health status={health_status} body={health}")
        return 1
    print(f"OK health {health}")

    failures = 0
    for market, sample in DEFAULT_SAMPLES.items():
        st, summary = get_json(
            base,
            "/api/v1/backtests/symbol-summary",
            {"market": market, "limit": 50, "include_chart_catalog": "true"},
        )
        if st != 200 or not isinstance(summary, list):
            print(f"FAIL symbol-summary {market} status={st} body={summary}")
            failures += 1
            continue
        print(f"OK symbol-summary {market} rows={len(summary)}")
        if len(summary) == 0:
            print(f"FAIL symbol-summary {market} empty list")
            failures += 1
            continue

        sym = sample["symbol"]
        st2, bundle = get_json(
            base,
            "/api/v1/backtests/chart-bundle",
            {"symbol": sym, "market": market, "strategy_id": sample["strategy_id"], "years": 3},
        )
        if st2 != 200 or not isinstance(bundle, dict) or not bundle.get("bars"):
            print(f"FAIL chart-bundle {market}/{sym} status={st2} body={str(bundle)[:300]}")
            failures += 1
            continue
        bars = len(bundle.get("bars") or [])
        trades = (bundle.get("metrics") or {}).get("trades", "?")
        print(f"OK chart-bundle {market}/{sym} bars={bars} trades={trades}")

    if failures:
        print(f"D4a FAIL failures={failures}")
        return 1
    print("D4a OK all markets")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
