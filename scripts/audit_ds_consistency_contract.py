#!/usr/bin/env python3
"""Read-only audit for DS01/DS03/DS05/DS07 consistency contracts.

This script does not evaluate strategy signals. It checks that the current
canonical tokens still appear across the core package, radar, pending monitor,
fill supervision, and sandbox review entry points, so old interpretations are
less likely to re-enter through a secondary path.
"""
from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class Contract:
    name: str
    path: str
    required_tokens: tuple[str, ...]
    forbidden_tokens: tuple[str, ...] = ()


@dataclass(frozen=True)
class CheckResult:
    name: str
    ok: bool
    detail: str

    def as_dict(self) -> dict[str, Any]:
        return {"name": self.name, "ok": self.ok, "detail": self.detail}


CONTRACTS: tuple[Contract, ...] = (
    Contract(
        name="ds01_core_left30_contract",
        path="packages/fengji_core/fengji_core/ds01.py",
        required_tokens=(
            "def ds01_left_filter_pass(",
            "lookback: int = 30",
            "max_lines: int = 2",
            "return left_count <= max_lines, left_count",
            "def ds01_os_defense_missing(",
            'row.get("active_low")',
            'row.get("active_high")',
        ),
    ),
    Contract(
        name="ds03_core_failed_peak_low_contract",
        path="packages/fengji_core/fengji_core/ds03.py",
        required_tokens=(
            "def resolve_ds03_attack(",
            'row, "last_failed_high_idx"',
            'row, "last_failed_low_idx"',
            'trigger_source="fake_peak"',
            "consumed_peak_keys",
            "active_high",
            "active_low",
        ),
    ),
    Contract(
        name="ds05_core_k2_possible_extreme_contract",
        path="packages/fengji_core/fengji_core/ds05.py",
        required_tokens=(
            "k2_possible_extreme",
            "camp_k2 != camp_k3",
            "def has_price_gap_with_prev(",
            'float(df["low"].iloc[k2_idx - 3 : k2_idx + 1].min())',
            'float(df["high"].iloc[k2_idx - 3 : k2_idx + 1].max())',
            'initial_stop=float(k2["low"])',
            'initial_stop=float(k2["high"])',
        ),
    ),
    Contract(
        name="ds07_core_new_resonance_contract",
        path="packages/fengji_core/fengji_core/ds07.py",
        required_tokens=(
            "from fengji_core.ds03 import resolve_ds03_attack",
            "camp_confirmed",
            "resolve_ds03_attack(df, i)",
            "LONG_CONTINUE",
            "SHORT_CONTINUE",
            "DS07 D1 Red + H1 Red DS03",
            "DS07 D1 Blue + H1 Blue DS03",
        ),
    ),
    Contract(
        name="radar_uses_canonical_ds_contracts",
        path="src/fengji_total_radar.py",
        required_tokens=(
            "from quant.ds01 import ds01_left_filter_pass, ds01_os_defense_missing",
            "from quant.ds03 import resolve_ds03_attack",
            "from quant.ds05 import make_ds05_signal",
            "from quant.ds07 import attach_os_detail, make_ds07_signal, map_d1_to_h1_future",
            "left_count=",
            "resolve_ds03_attack(d1, i)",
            "K2 possible extreme",
            "make_ds07_signal(cur, i, set(), symbol=symbol, prev_row=prev, df=mapped)",
        ),
    ),
    Contract(
        name="pending_monitor_fill_and_conflict_contract",
        path="src/fengji_pending_order_monitor.py",
        required_tokens=(
            "from fengji_core.ds03_pending_fill import resolve_ds03_pending_fill",
            "def should_skip_for_position(",
            'strategy == "DS01"',
            "entries < max_ds01_entries",
            "try_fill_ds03_order(args, order, symbol, price)",
            "consume_ds03_setup_key",
            "filled_setup_keys",
            "cancelled_setup_keys",
            '"cancel_reason": "conflict_after_fill"',
        ),
    ),
    Contract(
        name="paper_monitor_pending_managed_contract",
        path="src/overseas_paper_monitor.py",
        required_tokens=(
            'PENDING_MANAGED_STRATEGIES = {"DS01", "DS03", "DS05", "DS07", "DS08"}',
            "DIRECT_OPEN_STRATEGIES = set(TOTAL_PATTERN_STRATEGIES) - PENDING_MANAGED_STRATEGIES",
            "跳过主程序直接开仓",
            "开仓入口: DS01/DS03/DS05/DS07/DS08 由挂单监控触发",
        ),
    ),
    Contract(
        name="fill_supervision_reaudits_pending_managed_ds",
        path="packages/fengji_core/fengji_core/fill_supervision.py",
        required_tokens=(
            "def audit_ds01_fill(",
            "ds01_left_filter_pass(visible, i, left_price, is_add)",
            "def audit_ds03_fill(",
            "resolve_ds03_attack(os_df, idx)",
            "def audit_ds05_fill(",
            "def audit_ds07_fill(",
            'if strategy == "DS07":',
            "pending fill OK",
        ),
    ),
    Contract(
        name="fill_sandbox_review_supports_core_pending_ds",
        path="scripts/generate_fill_sandbox_review.py",
        required_tokens=(
            'SUPPORTED_STRATEGIES = {"DS01", "DS03", "DS04", "DS05", "DS07", "DS08", "DS09"}',
            "plot_crypto_ds01_trade_sandbox.py",
            "plot_live_ds03_sandbox.py",
            "plot_live_ds05_sandbox.py",
            "plot_live_ds07_sandbox.py",
            "find_ds05_trade_no",
            "missing DS07 trigger time",
        ),
    ),
    Contract(
        name="ds03_sandbox_uses_os_line_and_camp",
        path="src/plot_ds03_sandbox.py",
        required_tokens=(
            "draw_camp_background",
            "hardened_fengji_line",
            "run_ds03_backtest",
            "entry_ref",
            "initial_stop",
        ),
    ),
    Contract(
        name="ds07_sandbox_uses_d1_h1_os_lines_and_camps",
        path="src/plot_ds07_sandbox.py",
        required_tokens=(
            "draw_camp_background",
            "H1 hardened_fengji_line",
            "D1 hardened_fengji_line",
            "D1 strategic OS",
            "D1/H1=",
        ),
    ),
)


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")


def check_contract(root: Path, contract: Contract) -> CheckResult:
    path = root / contract.path
    if not path.is_file():
        return CheckResult(contract.name, False, f"missing_file={contract.path}")
    text = read_text(path)
    missing = [token for token in contract.required_tokens if token not in text]
    forbidden = [token for token in contract.forbidden_tokens if token in text]
    ok = not missing and not forbidden
    detail = "ok" if ok else json.dumps({"missing": missing, "forbidden": forbidden}, ensure_ascii=False)
    return CheckResult(contract.name, ok, detail)


def run_checks(root: Path = ROOT) -> list[CheckResult]:
    return [check_contract(root, contract) for contract in CONTRACTS]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit DS01/DS03/DS05/DS07 consistency contracts.")
    parser.add_argument("--root", default=str(ROOT))
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = Path(args.root).resolve()
    checks = run_checks(root)
    failures = [check for check in checks if not check.ok]
    payload = {"checks": [check.as_dict() for check in checks], "failures": len(failures)}
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
