#!/usr/bin/env python
"""W14 D4c: backtest trades API smoke — exit_price + net PnL ratio sanity."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

TRADE_SAMPLES = [
    {"market": "A_STOCK", "symbol": "000021", "strategy_id": "DS01"},
    {"market": "FUTURES", "symbol": "沪金", "strategy_id": "DS01"},
    {"market": "CRYPTO", "symbol": "SOLUSDT", "strategy_id": "DS01"},
    {"market": "US_STOCK", "symbol": "NVDA", "strategy_id": "DS01"},
]


def get_json(base: str, path: str, params: dict | None = None, timeout: float = 30.0) -> tuple[int, object]:
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


def is_short_side(side: object) -> bool:
    if side in (-1, "-1", "short"):
        return True
    try:
        return int(side) < 0
    except (TypeError, ValueError):
        return str(side or "").lower() in {"short", "-1"}


def trade_return_ratio(trade: dict) -> float | None:
    try:
        entry = float(trade.get("entry_price") or trade.get("avg_entry_price") or 0)
        exit_p = float(trade.get("exit_price") or 0)
    except (TypeError, ValueError):
        entry = exit_p = 0.0
    if entry > 0 and exit_p > 0:
        return (entry - exit_p) / entry if is_short_side(trade.get("side")) else (exit_p - entry) / entry
    try:
        return float(trade.get("net_pnl")) / 100_000.0
    except (TypeError, ValueError):
        return None


def analyze_trades(rows: list[dict]) -> dict[str, object]:
    if not rows:
        return {"count": 0, "with_exit_price": 0, "fake_hundred": 0, "examples": []}
    with_exit = 0
    fake: list[str] = []
    for row in rows:
        if row.get("exit_price") not in (None, "", 0):
            with_exit += 1
        ratio = trade_return_ratio(row)
        if ratio is not None and abs(abs(ratio) - 1.0) < 1e-9:
            fake.append(str(row.get("trade_id") or ""))
    return {
        "count": len(rows),
        "with_exit_price": with_exit,
        "fake_hundred": len(fake),
        "examples": fake[:3],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Backtest trades exit_price / PnL smoke")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--base-url", default="")
    parser.add_argument("--limit", type=int, default=80)
    parser.add_argument("--ssh-tunnel", default="", help="SSH alias, e.g. domestic-quant")
    parser.add_argument("--local-port", type=int, default=8045)
    parser.add_argument("--remote-port", type=int, default=8000)
    parser.add_argument("--wait-seconds", type=float, default=3.0)
    args = parser.parse_args()

    tunnel_proc: subprocess.Popen[bytes] | None = None
    try:
        base = args.base_url
        if args.ssh_tunnel:
            base = f"http://127.0.0.1:{args.local_port}"
            tunnel_proc = subprocess.Popen(
                [
                    "ssh",
                    "-o",
                    "BatchMode=yes",
                    "-N",
                    "-L",
                    f"{args.local_port}:127.0.0.1:{args.remote_port}",
                    args.ssh_tunnel,
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            time.sleep(args.wait_seconds)
        if not base:
            base = f"http://127.0.0.1:{args.port}"

        st, health = get_json(base, "/api/v1/health")
        if st != 200:
            print(f"FAIL health status={st} body={health}")
            return 1

        failures = 0
        report: list[dict] = []
        for sample in TRADE_SAMPLES:
            market = sample["market"]
            sym = sample["symbol"]
            sid = sample["strategy_id"]
            st2, rows = get_json(
                base,
                "/api/v1/backtests/trades",
                {"market": market, "symbol": sym, "strategy_id": sid, "limit": args.limit},
            )
            if st2 != 200 or not isinstance(rows, list):
                print(f"FAIL trades {market}/{sym}/{sid} status={st2} body={str(rows)[:300]}")
                failures += 1
                continue
            stats = analyze_trades(rows)
            stats.update({"market": market, "symbol": sym, "strategy_id": sid})
            report.append(stats)
            exit_rate = (stats["with_exit_price"] / stats["count"]) if stats["count"] else 0.0
            ok = stats["count"] > 0 and exit_rate >= 0.8 and stats["fake_hundred"] <= max(1, stats["count"] // 20)
            if not ok:
                failures += 1
            print(
                f"{'OK' if ok else 'FAIL'} trades {market}/{sym}/{sid} "
                f"count={stats['count']} exit_price={stats['with_exit_price']} "
                f"fake100={stats['fake_hundred']}"
            )

        out = ROOT / "runtime" / "web_validation" / "w14_backtest_trade_pnl_smoke.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(
            json.dumps({"base_url": base, "failures": failures, "markets": report}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        if failures:
            print(f"D4c FAIL failures={failures}")
            return 1
        print("D4c OK all trade PnL samples")
        return 0
    finally:
        if tunnel_proc is not None:
            tunnel_proc.terminate()
            try:
                tunnel_proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                tunnel_proc.kill()


if __name__ == "__main__":
    raise SystemExit(main())
