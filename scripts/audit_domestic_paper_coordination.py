#!/usr/bin/env python3
"""Audit domestic futures/A-stock paper runtime coordination.

This is a read-only contract audit for the domestic runtime entry points. It
checks that the start factory, data pump, paper entry, radar loop, and pending
monitor agree on paths and runtime state files.
"""
from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class CheckResult:
    name: str
    ok: bool
    detail: str

    def as_dict(self) -> dict[str, Any]:
        return {"name": self.name, "ok": self.ok, "detail": self.detail}


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def norm(text: str) -> str:
    return text.replace("\\", "/").lower()


def first_manifest_name(root: Path) -> str:
    manifest = root / "scripts" / "domestic_paper_manifest.txt"
    if not manifest.exists():
        return ""
    for line in manifest.read_text(encoding="utf-8").splitlines():
        value = line.strip()
        if value and not value.startswith("#"):
            return value
    return ""


def check_contains(name: str, text: str, expected: list[str]) -> CheckResult:
    body = norm(text)
    missing = [item for item in expected if norm(item) not in body]
    return CheckResult(name, not missing, "missing=" + ",".join(missing) if missing else "ok")


def check_paper_manifest_source(root: Path) -> CheckResult:
    name = first_manifest_name(root)
    candidates = [root / name, root / "remote_domestic_optimize" / name] if name else []
    exists = any(path.is_file() for path in candidates)
    detail = f"name={name!r} candidates={[str(path) for path in candidates]} exists={exists}"
    return CheckResult("domestic_paper_manifest_source", bool(name) and exists, detail)


def check_paper_resolver(root: Path) -> CheckResult:
    return check_contains(
        "domestic_paper_resolver_contract",
        read_text(root / "scripts" / "resolve_domestic_paper.ps1"),
        [
            "domestic_paper_manifest.txt",
            "Get-Content",
            "-Encoding UTF8",
            "Test-Path -LiteralPath",
            "*01-08*",
            "Domestic paper script not found",
        ],
    )


def check_paper_deploy(root: Path) -> CheckResult:
    return check_contains(
        "domestic_paper_deploy_contract",
        read_text(root / "scripts" / "deploy_domestic_paper_feishu.ps1"),
        [
            "remote_domestic_optimize",
            "domestic_paper_manifest.txt",
            "runtime/_deploy_domestic_paper_tmp.py",
            "Copy-Item",
            "Join-Path $r $n",
        ],
    )


def check_start_factory(root: Path) -> CheckResult:
    return check_contains(
        "domestic_start_factory_components",
        read_text(root / "scripts" / "start_factory_ascii.bat"),
        [
            "run_data_manager_futures.cmd",
            "run_futures_astock_paper.ps1",
            "scripts\\run_futures_radar_loop.cmd",
            "scripts\\run_futures_pending_monitor.cmd",
            "Dash.py",
            "data_manager_futures|01-08|Dash.py|run_data_manager_futures|run_futures_astock_paper|fengji_radar_order_loop|fengji_futures_pending_order_monitor",
        ],
    )


def check_data_manager_entry(root: Path) -> CheckResult:
    combined = read_text(root / "run_data_manager_futures.cmd") + "\n" + read_text(root / "run_data_manager_futures.ps1")
    return check_contains(
        "domestic_data_manager_entry",
        combined,
        [
            "data_manager_futures.py",
            "runtime\\logs",
            "data_manager_futures_run.log",
            "data_manager_futures_err.log",
            "PYTHONIOENCODING",
            "PYTHONUTF8",
        ],
    )


def check_paper_entry(root: Path) -> CheckResult:
    return check_contains(
        "domestic_paper_entry",
        read_text(root / "run_futures_astock_paper.ps1"),
        [
            "resolve_domestic_paper.ps1",
            "Get-DomesticPaperScript",
            "futures_astock_paper_run.log",
            "futures_astock_paper_err.log",
            "PYTHONUNBUFFERED",
        ],
    )


def check_paper_state_lock(root: Path) -> CheckResult:
    name = first_manifest_name(root)
    candidates = [root / "remote_domestic_optimize" / name, root / name] if name else []
    paper = next((path for path in candidates if path.is_file()), None)
    if paper is None:
        return CheckResult("domestic_paper_state_lock", False, "paper source unavailable")
    combined = read_text(paper) + "\n" + read_text(root / "scripts" / "fengji_domestic_deploy_manifest.txt")
    return check_contains(
        "domestic_paper_state_lock",
        combined,
        [
            "from fengji_core.state_lock import update_state_file",
            "prepare_symbol_scan",
            "commit_symbol_scan",
            "dispatch_effects",
            "packages/fengji_core/fengji_core/state_lock.py",
        ],
    )


def check_radar_entry(root: Path) -> CheckResult:
    return check_contains(
        "domestic_radar_entry",
        read_text(root / "scripts" / "run_futures_radar_loop.cmd"),
        [
            "fengji_radar_order_loop.py",
            "--market futures",
            "--data-dir data",
            "--radar-dir runtime\\fengji_radar",
            "--pending-dir runtime\\fengji_pending_orders",
            "--monitor-state runtime\\fengji_pending_orders\\futures_pending_state.json",
            "--include-triggered",
            "--loop-seconds 600",
            "--m15-tail 960",
        ],
    )


def check_pending_entry(root: Path) -> CheckResult:
    return check_contains(
        "domestic_pending_entry",
        read_text(root / "scripts" / "run_futures_pending_monitor.ps1"),
        [
            "load_feishu_webhook.ps1",
            "FENGJI_MARKET = \"futures\"",
            "--orders-file",
            "runtime\\fengji_pending_orders\\pending_orders.json",
            "--out-dir",
            "runtime\\fengji_pending_orders",
            "--state-file",
            "runtime\\fengji_pending_orders\\futures_pending_state.json",
            "--paper-state-file",
            "runtime\\fengji_futures\\state_futures_v2.json",
            "--trade-csv",
            "runtime\\fengji_futures\\trades_futures_astock.csv",
            "--data-dir",
            "data",
            "--price-timeframes",
            "15m,1h,1d",
            "--enforce-valid-until",
        ],
    )


def check_restart_runtime(root: Path) -> CheckResult:
    return check_contains(
        "domestic_restart_runtime_components",
        read_text(root / "scripts" / "restart_domestic_futures_runtime.ps1"),
        [
            "resolve_domestic_paper.ps1",
            "Get-DomesticPaperScript",
            "restart_domestic_data_manager.ps1",
            "fengji_radar_order_loop.py",
            "fengji_futures_pending_order_monitor.py",
            "--monitor-state",
            "runtime\\fengji_pending_orders\\futures_pending_state.json",
            "--include-triggered",
            "--paper-state-file runtime\\fengji_futures\\state_futures_v2.json",
            "--trade-csv runtime\\fengji_futures\\trades_futures_astock.csv",
        ],
    )


def check_watchdog(root: Path) -> CheckResult:
    return check_contains(
        "domestic_watchdog_components",
        read_text(root / "scripts" / "watchdog_domestic.ps1"),
        [
            "resolve_domestic_paper.ps1",
            "Get-DomesticPaperScript",
            "$cmdData",
            "$cmdPaper",
            "$cmdRadar",
            "$cmdPending",
            "data_manager_futures.py",
            "fengji_radar_order_loop.py",
            "fengji_futures_pending_order_monitor.py",
            "fill_supervision",
        ],
    )


def check_sync_manifest(root: Path) -> CheckResult:
    sync = read_text(root / "scripts" / "sync_deploy_domestic.ps1")
    manifest = read_text(root / "scripts" / "fengji_domestic_deploy_manifest.txt")
    expected = [
        "run_data_manager_futures.cmd",
        "run_data_manager_futures.ps1",
        "run_futures_astock_paper.ps1",
        "scripts\\start_factory_ascii.bat",
        "scripts\\run_futures_radar_loop.cmd",
        "scripts\\run_futures_pending_monitor.cmd",
        "scripts\\run_futures_astock_paper_ascii.cmd",
    ]
    return check_contains("domestic_sync_manifest_entries", sync + "\n" + manifest, expected)


def check_no_literal_webhook(root: Path) -> CheckResult:
    files = [
        root / "scripts" / "run_futures_pending_monitor.ps1",
        root / "scripts" / "restart_domestic_futures_runtime.ps1",
        root / "scripts" / "watchdog_domestic.ps1",
        root / "run_futures_astock_paper.ps1",
        root / "scripts" / "start_factory_ascii.bat",
    ]
    offenders = [str(path.relative_to(root)) for path in files if "https://open.feishu.cn" in read_text(path)]
    return CheckResult("domestic_no_literal_webhook_url", not offenders, "offenders=" + ",".join(offenders) if offenders else "ok")


def runtime_snapshot(root: Path) -> dict[str, Any]:
    name = first_manifest_name(root)
    paths = {
        "manifest": root / "scripts" / "domestic_paper_manifest.txt",
        "paper_root": root / name if name else root / "__missing__",
        "paper_staged": root / "remote_domestic_optimize" / name if name else root / "__missing__",
        "data_manager": root / "data_manager_futures.py",
        "orders": root / "runtime" / "fengji_pending_orders" / "pending_orders.json",
        "pending_state": root / "runtime" / "fengji_pending_orders" / "futures_pending_state.json",
        "paper_state": root / "runtime" / "fengji_futures" / "state_futures_v2.json",
        "trade_csv": root / "runtime" / "fengji_futures" / "trades_futures_astock.csv",
        "data_dir": root / "data",
    }
    return {
        "paper_manifest_name": name,
        "available": {key: path.exists() for key, path in paths.items()},
    }


def run_checks(root: Path = ROOT) -> list[CheckResult]:
    return [
        check_paper_manifest_source(root),
        check_paper_resolver(root),
        check_paper_deploy(root),
        check_start_factory(root),
        check_data_manager_entry(root),
        check_paper_entry(root),
        check_paper_state_lock(root),
        check_radar_entry(root),
        check_pending_entry(root),
        check_restart_runtime(root),
        check_watchdog(root),
        check_sync_manifest(root),
        check_no_literal_webhook(root),
    ]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit domestic paper runtime coordination.")
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
        "runtime": runtime_snapshot(root),
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
