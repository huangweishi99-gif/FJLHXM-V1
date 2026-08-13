from __future__ import annotations

import argparse
import json
import math
import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

import pandas as pd
from sqlalchemy import select
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

ROOT = Path(__file__).resolve().parents[1]
for rel in ("services", "packages/fengji_core", "src"):
    path = str(ROOT / rel)
    if path not in sys.path:
        sys.path.insert(0, path)

from db.models import ContextBucketStat, TradeContextSnapshot  # noqa: E402
from db.session import get_database_url, get_engine  # noqa: E402
from fengji_core.context_stats import build_bucket_key, score_snapshot  # noqa: E402


DEFAULT_SAMPLE_PLAN = "A_STOCK=4,CRYPTO=3,FUTURES=3,US_STOCK=3"
COMPARE_KEYS = (
    "trade_id",
    "strategy_id",
    "market",
    "symbol",
    "setup_key",
    "entry_time",
    "net_pnl",
    "r_multiple",
    "bucket_key",
    "signal_tier",
    "bucket_count",
    "bucket_win_rate_smoothed",
    "signal_score",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Smoke-check PG snapshots against HTTP /signals/{trade_id}/strength API.",
    )
    parser.add_argument("--base-url", default="", help="Existing API base URL. If omitted, start local uvicorn.")
    parser.add_argument("--port", type=int, default=8022, help="Temporary uvicorn port when --base-url is omitted.")
    parser.add_argument("--sample-plan", default=DEFAULT_SAMPLE_PLAN, help="Comma list like A_STOCK=4,CRYPTO=3,FUTURES=3.")
    parser.add_argument("--connect-timeout", type=float, default=3.0, help="Socket/API connect timeout seconds.")
    parser.add_argument("--startup-timeout", type=float, default=20.0, help="Temporary API startup timeout seconds.")
    parser.add_argument("--float-tolerance", type=float, default=1e-9, help="Float comparison tolerance.")
    return parser.parse_args()


def parse_sample_plan(raw: str) -> list[tuple[str, int]]:
    plan: list[tuple[str, int]] = []
    for chunk in raw.split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        if "=" not in chunk:
            raise ValueError(f"invalid sample-plan part: {chunk}")
        market, count = chunk.split("=", 1)
        plan.append((market.strip().upper(), int(count)))
    if not plan:
        raise ValueError("sample-plan cannot be empty")
    return plan


def assert_database_port_reachable(timeout: float) -> None:
    url = make_url(get_database_url())
    host = url.host or "localhost"
    port = int(url.port or 5432)
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return
    except OSError as exc:
        raise RuntimeError(
            f"database is not reachable at {host}:{port}; run `docker compose up -d` first"
        ) from exc


def fetch_samples(plan: list[tuple[str, int]]) -> list[TradeContextSnapshot]:
    engine = get_engine()
    samples: list[TradeContextSnapshot] = []
    with Session(engine) as session:
        for market, count in plan:
            rows = session.scalars(
                select(TradeContextSnapshot)
                .where(TradeContextSnapshot.market == market)
                .order_by(TradeContextSnapshot.entry_time.desc().nullslast(), TradeContextSnapshot.trade_id)
                .limit(count)
            ).all()
            if len(rows) < count:
                raise RuntimeError(f"not enough samples for {market}: expected {count}, got {len(rows)}")
            samples.extend(rows)
    return samples


def snapshot_expected(session: Session, snap: TradeContextSnapshot) -> dict[str, Any]:
    context = snap.context_json if isinstance(snap.context_json, dict) else json.loads(snap.context_json or "{}")
    row = {
        "trade_id": snap.trade_id,
        "strategy_id": snap.strategy_id,
        "market": snap.market,
        "symbol": snap.symbol,
        **context,
    }
    stats_rows = session.scalars(
        select(ContextBucketStat).where(
            ContextBucketStat.strategy_id == snap.strategy_id,
            ContextBucketStat.market == snap.market,
        )
    ).all()
    stats_df = pd.DataFrame(
        [
            {
                "strategy_id": r.strategy_id,
                "market": r.market,
                "bucket_key": r.bucket_key,
                "count": r.count,
                "wins": r.wins,
                "win_rate_smoothed": r.win_rate_smoothed,
                "avg_r_smoothed": r.avg_r_smoothed,
                "signal_score": r.signal_score,
                "signal_tier": r.signal_tier,
            }
            for r in stats_rows
        ]
    )
    scored = (
        score_snapshot(row, stats_df)
        if not stats_df.empty
        else {
            "bucket_key": build_bucket_key(row, snap.strategy_id, snap.market),
            "signal_score": None,
            "signal_tier": "INSUFFICIENT_DATA",
            "bucket_count": 0,
            "bucket_win_rate_smoothed": None,
        }
    )
    return {
        "trade_id": snap.trade_id,
        "strategy_id": snap.strategy_id,
        "market": snap.market,
        "symbol": snap.symbol,
        "setup_key": snap.setup_key,
        "entry_time": snap.entry_time.isoformat() if snap.entry_time else None,
        "net_pnl": float(snap.net_pnl) if snap.net_pnl is not None else None,
        "r_multiple": float(snap.r_multiple) if snap.r_multiple is not None else None,
        **scored,
    }


def api_get_json(base_url: str, path: str, timeout: float) -> dict[str, Any]:
    url = base_url.rstrip("/") + path
    with urllib.request.urlopen(url, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def wait_for_api(base_url: str, timeout: float, startup_timeout: float) -> None:
    deadline = time.time() + startup_timeout
    last_error: Exception | None = None
    while time.time() < deadline:
        try:
            data = api_get_json(base_url, "/api/v1/health", timeout)
            if data.get("status") == "ok":
                return
        except Exception as exc:  # noqa: BLE001 - smoke script should report last health error
            last_error = exc
            time.sleep(0.5)
    raise RuntimeError(f"API did not become ready at {base_url}; last_error={last_error}")


def start_uvicorn(port: int) -> tuple[subprocess.Popen[str], str]:
    logs = ROOT / "runtime" / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    stdout = logs / "api_smoke_pg_consistency_stdout.log"
    stderr = logs / "api_smoke_pg_consistency_stderr.log"
    env = os.environ.copy()
    env["PYTHONPATH"] = "src;packages/fengji_core;services"
    proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "services.api.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
        ],
        cwd=str(ROOT),
        env=env,
        stdout=stdout.open("w", encoding="utf-8"),
        stderr=stderr.open("w", encoding="utf-8"),
        text=True,
    )
    return proc, f"http://127.0.0.1:{port}"


def values_equal(expected: Any, actual: Any, tolerance: float) -> bool:
    if expected is None or actual is None:
        return expected is None and actual is None
    if isinstance(expected, (float, int)) or isinstance(actual, (float, int)):
        try:
            exp = float(expected)
            got = float(actual)
        except (TypeError, ValueError):
            return False
        if math.isnan(exp) or math.isnan(got):
            return math.isnan(exp) and math.isnan(got)
        return abs(exp - got) <= tolerance
    return expected == actual


def compare_rows(expected: dict[str, Any], actual: dict[str, Any], tolerance: float) -> list[str]:
    errors: list[str] = []
    for key in COMPARE_KEYS:
        if not values_equal(expected.get(key), actual.get(key), tolerance):
            errors.append(f"{key}: expected={expected.get(key)!r} actual={actual.get(key)!r}")
    return errors


def main() -> int:
    args = parse_args()
    plan = parse_sample_plan(args.sample_plan)
    assert_database_port_reachable(args.connect_timeout)

    samples = fetch_samples(plan)
    proc: subprocess.Popen[str] | None = None
    base_url = args.base_url.rstrip("/")
    if not base_url:
        proc, base_url = start_uvicorn(args.port)

    try:
        wait_for_api(base_url, args.connect_timeout, args.startup_timeout)
        failures: list[str] = []
        checked = 0
        by_market: dict[str, int] = {}
        with Session(get_engine()) as session:
            for snap in samples:
                expected = snapshot_expected(session, snap)
                encoded_trade_id = urllib.parse.quote(snap.trade_id, safe="")
                if "+" in encoded_trade_id:
                    failures.append(f"path encoding contains '+': trade_id={snap.trade_id!r}")
                    continue
                try:
                    actual = api_get_json(
                        base_url,
                        f"/api/v1/signals/{encoded_trade_id}/strength",
                        args.connect_timeout,
                    )
                except urllib.error.HTTPError as exc:
                    failures.append(f"{snap.trade_id}: HTTP {exc.code} {exc.reason}")
                    continue
                row_errors = compare_rows(expected, actual, args.float_tolerance)
                if row_errors:
                    failures.append(f"{snap.trade_id}: " + "; ".join(row_errors))
                    continue
                checked += 1
                by_market[snap.market] = by_market.get(snap.market, 0) + 1

        if failures:
            print("PG_API_CONSISTENCY_FAILED")
            for item in failures:
                print(item)
            return 1
        print(f"PG_API_CONSISTENCY_OK={checked}/{len(samples)}")
        for market in sorted(by_market):
            print(f"{market}={by_market[market]}")
        print(f"base_url={base_url}")
        return 0
    finally:
        if proc is not None and proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=5)


if __name__ == "__main__":
    raise SystemExit(main())
