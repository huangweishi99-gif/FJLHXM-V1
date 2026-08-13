#!/usr/bin/env python3
"""Regression audit for the unified FengJi ledger contract.

This audit uses synthetic candidates and temporary output directories only. It
checks that the unified whitelist ledger still accepts/rejects candidates as a
portfolio ledger, and that futures/crypto batch scorers emit the expected
summary artifacts.
"""
from __future__ import annotations

import argparse
import json
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from batch_unified_crypto_whitelist import score_crypto_results  # noqa: E402
from batch_unified_whitelist_engine import score_futures_results  # noqa: E402
from unified_whitelist_engine import merge_candidates  # noqa: E402


@dataclass(frozen=True)
class CheckResult:
    name: str
    ok: bool
    detail: str

    def as_dict(self) -> dict[str, Any]:
        return {"name": self.name, "ok": self.ok, "detail": self.detail}


def candidate(
    candidate_id: str,
    *,
    strategy_id: str,
    entry_time: str,
    side: int,
    direction: str,
    priority: int,
    exit_time: str = "2026-01-01 10:00:00",
    net: float = 10.0,
) -> dict[str, Any]:
    return {
        "candidate_id": candidate_id,
        "symbol": "BTCUSDT",
        "strategy_id": strategy_id,
        "direction": direction,
        "side": side,
        "entry_time": entry_time,
        "exit_time": exit_time,
        "entry_price": 100.0,
        "exit_price": 110.0,
        "strategy_priority": priority,
        "net": net,
        "exit_reason": "take_profit",
    }


def check_merge_candidates_contract() -> CheckResult:
    candidates = pd.DataFrame(
        [
            candidate("c1", strategy_id="DS01", entry_time="2026-01-01 09:00:00", side=1, direction="long", priority=10),
            candidate("c2", strategy_id="DS03", entry_time="2026-01-01 09:01:00", side=1, direction="long", priority=30),
            candidate("c3", strategy_id="DS05", entry_time="2026-01-01 09:02:00", side=1, direction="long", priority=50),
            candidate("c4", strategy_id="DS07", entry_time="2026-01-01 09:03:00", side=1, direction="long", priority=70),
            candidate("c5", strategy_id="DS08", entry_time="2026-01-01 09:04:00", side=-1, direction="short", priority=80),
            candidate("missing", strategy_id="DS09", entry_time="", side=1, direction="long", priority=90),
        ]
    )

    merged = merge_candidates(candidates, max_same_direction_entries=3)
    accepted = merged["accepted_trades"]
    rejected = merged["rejected_orders"]
    events = merged["ledger_events"]
    reasons = set(rejected.get("reject_reason", pd.Series(dtype=str)).astype(str))
    event_types = set(events.get("event_type", pd.Series(dtype=str)).astype(str))
    ok = (
        len(accepted) == 3
        and len(rejected) == 3
        and reasons == {"same_direction_entry_limit", "opposite_position_blocked", "missing_entry_time"}
        and {"open", "reject", "close"}.issubset(event_types)
        and list(accepted["portfolio_trade_no"]) == [1, 2, 3]
    )
    detail = f"accepted={len(accepted)} rejected={len(rejected)} reasons={sorted(reasons)} events={sorted(event_types)}"
    return CheckResult("unified_merge_candidates_contract", ok, detail)


def write_common_csvs(symbol_dir: Path) -> None:
    pd.DataFrame(
        [
            {
                "portfolio_trade_no": 1,
                "strategy_id": "DS01",
                "entry_time": "2026-01-01 09:00:00",
                "exit_time": "2026-01-01 10:00:00",
                "entry_price": 100.0,
                "exit_price": 110.0,
                "direction": "long",
                "side": 1,
                "net": 10.0,
            },
            {
                "portfolio_trade_no": 2,
                "strategy_id": "DS03",
                "entry_time": "2026-01-01 11:00:00",
                "exit_time": "2026-01-01 12:00:00",
                "entry_price": 110.0,
                "exit_price": 100.0,
                "direction": "long",
                "side": 1,
                "net": -5.0,
            },
        ]
    ).to_csv(symbol_dir / "accepted_trades.csv", index=False, encoding="utf-8-sig")
    pd.DataFrame([{"candidate_id": "r1", "reject_reason": "same_direction_entry_limit"}]).to_csv(
        symbol_dir / "rejected_orders.csv",
        index=False,
        encoding="utf-8-sig",
    )
    pd.DataFrame(columns=["candidate_id", "reason"]).to_csv(
        symbol_dir / "strategy_bad_trades.csv",
        index=False,
        encoding="utf-8-sig",
    )


def check_futures_scoring_contract() -> CheckResult:
    with tempfile.TemporaryDirectory(prefix="fengji_unified_futures_") as tmp:
        symbol_dir = Path(tmp)
        write_common_csvs(symbol_dir)
        summary = score_futures_results(symbol_dir, initial_cash=1000.0)
        required_files = [
            symbol_dir / "futures_scored_accepted_trades.csv",
            symbol_dir / "futures_by_strategy.csv",
        ]
        ok = (
            summary["trades"] == 2
            and summary["wins"] == 1
            and summary["accepted"] == 2
            and summary["rejected"] == 1
            and summary["bad_audits"] == 0
            and all(path.is_file() for path in required_files)
        )
        detail = f"summary={summary} files={[path.name for path in required_files if path.is_file()]}"
        return CheckResult("futures_unified_scoring_contract", ok, detail)


def check_crypto_scoring_contract() -> CheckResult:
    with tempfile.TemporaryDirectory(prefix="fengji_unified_crypto_") as tmp:
        symbol_dir = Path(tmp)
        write_common_csvs(symbol_dir)
        summary = score_crypto_results(
            symbol_dir,
            initial_cash=1000.0,
            margin=100.0,
            leverage=2.0,
            fee_rate=0.0005,
            slippage_rate=0.0002,
            maintenance_margin_rate=0.005,
        )
        required_files = [
            symbol_dir / "crypto_scored_accepted_trades.csv",
            symbol_dir / "crypto_by_strategy.csv",
        ]
        ok = (
            summary["trades"] == 2
            and summary["accepted"] == 2
            and summary["rejected"] == 1
            and summary["bad_audits"] == 0
            and all(path.is_file() for path in required_files)
        )
        detail = f"summary={summary} files={[path.name for path in required_files if path.is_file()]}"
        return CheckResult("crypto_unified_scoring_contract", ok, detail)


def check_static_output_contract(root: Path) -> CheckResult:
    text = "\n".join(
        [
            (root / "src" / "unified_whitelist_engine.py").read_text(encoding="utf-8"),
            (root / "src" / "batch_unified_whitelist_engine.py").read_text(encoding="utf-8"),
            (root / "src" / "batch_unified_crypto_whitelist.py").read_text(encoding="utf-8"),
        ]
    )
    tokens = [
        '"accepted_trades"',
        '"rejected_orders"',
        '"ledger_events"',
        "accepted_trades.csv",
        "rejected_orders.csv",
        "strategy_bad_trades.csv",
        "futures_scored_accepted_trades.csv",
        "crypto_scored_accepted_trades.csv",
        "by_strategy.csv",
    ]
    missing = [token for token in tokens if token not in text]
    return CheckResult(
        "unified_static_output_contract",
        not missing,
        "missing=" + ",".join(missing) if missing else "ok",
    )


def run_checks(root: Path = ROOT) -> list[CheckResult]:
    return [
        check_static_output_contract(root),
        check_merge_candidates_contract(),
        check_futures_scoring_contract(),
        check_crypto_scoring_contract(),
    ]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit unified ledger regression contract.")
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
        "policy": {
            "scope": "synthetic ledger regression only; no market data, no strategy reimplementation",
            "outputs": "accepted/rejected/ledger events plus futures and crypto scored summaries",
        },
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
