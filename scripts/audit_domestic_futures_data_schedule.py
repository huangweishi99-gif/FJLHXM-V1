#!/usr/bin/env python3
"""Audit domestic futures Tianqin data schedule and watchdog contracts.

This script is read-only. It parses the data pump source and deployment scripts
without importing Tianqin dependencies, then reports whether the domestic data
source, day/night windows, pre-open catchup, idle behavior, and watchdog checks
match the frozen operational contract.
"""
from __future__ import annotations

import argparse
import ast
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]

EXPECTED_SYMBOLS = {
    "SA",
    "FG",
    "CJ",
    "OI",
    "SH",
    "SR",
    "SF",
    "MA",
    "TA",
    "UR",
    "CF",
    "RB",
    "FU",
    "SP",
    "NI",
    "AO",
    "RU",
    "BR",
    "AU",
    "AG",
    "PG",
    "LH",
    "JD",
    "PP",
    "EB",
    "EG",
    "JM",
    "M",
    "P",
    "V",
    "SI",
    "LC",
    "EC",
    "SC",
}
EXPECTED_TIMEFRAMES = {"1d": 86400, "1h": 3600, "15m": 900, "5m": 300}
EXPECTED_DATA_LENGTH_DEFAULTS = {"1d": 800, "1h": 2600, "15m": 8000, "5m": 6000}
EXPECTED_FUTURES_WINDOWS = [
    {"start": "08:30:00", "end": "11:35:00", "days": [0, 1, 2, 3, 4]},
    {"start": "13:00:00", "end": "15:15:00", "days": [0, 1, 2, 3, 4]},
    {"start": "20:30:00", "end": "23:59:59", "days": [0, 1, 2, 3, 4]},
    {"start": "00:00:00", "end": "02:35:00", "days": [1, 2, 3, 4, 5]},
]
EXPECTED_A_STOCK_WINDOWS = [
    {"start": "09:00:00", "end": "11:35:00", "days": [0, 1, 2, 3, 4]},
    {"start": "12:30:00", "end": "15:05:00", "days": [0, 1, 2, 3, 4]},
]
EXPECTED_NIGHT_END_GROUPS = {
    "23:00": {"SA", "FG", "CJ", "OI", "SH", "SR", "SF", "MA", "TA", "UR", "CF", "PG", "LH", "JD", "PP", "EB", "EG", "JM", "M", "P", "V", "SI", "LC"},
    "23:30": {"RB", "FU", "SP", "RU", "BR"},
    "01:00": {"NI", "AO", "EC"},
    "02:30": {"AU", "AG", "SC"},
}


@dataclass(frozen=True)
class CheckResult:
    name: str
    ok: bool
    detail: str

    def as_dict(self) -> dict[str, Any]:
        return {"name": self.name, "ok": self.ok, "detail": self.detail}


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def parse_source(path: Path) -> tuple[str, ast.Module]:
    text = read_text(path)
    return text, ast.parse(text, filename=str(path))


def assigned_node(tree: ast.Module, name: str) -> ast.AST | None:
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        if any(isinstance(target, ast.Name) and target.id == name for target in node.targets):
            return node.value
    return None


def function_text(text: str, tree: ast.Module, name: str) -> str:
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return ast.get_source_segment(text, node) or ""
    return ""


def constant_int(value: ast.AST | None) -> int | None:
    if isinstance(value, ast.Constant) and isinstance(value.value, int):
        return int(value.value)
    return None


def getenv_int_default(value: ast.AST) -> int | None:
    if not isinstance(value, ast.Call):
        return None
    if not (isinstance(value.func, ast.Name) and value.func.id == "int"):
        return None
    if not value.args or not isinstance(value.args[0], ast.Call):
        return None
    getenv = value.args[0]
    if not (
        isinstance(getenv.func, ast.Attribute)
        and getenv.func.attr == "getenv"
        and len(getenv.args) >= 2
        and isinstance(getenv.args[1], ast.Constant)
    ):
        return None
    try:
        return int(str(getenv.args[1].value))
    except ValueError:
        return None


def dict_string_map(value: ast.AST | None) -> dict[str, str]:
    if not isinstance(value, ast.Dict):
        return {}
    out: dict[str, str] = {}
    for key, item in zip(value.keys, value.values):
        if isinstance(key, ast.Constant) and isinstance(item, ast.Constant):
            out[str(key.value)] = str(item.value)
    return out


def dict_int_map(value: ast.AST | None) -> dict[str, int]:
    if not isinstance(value, ast.Dict):
        return {}
    out: dict[str, int] = {}
    for key, item in zip(value.keys, value.values):
        if not isinstance(key, ast.Constant):
            continue
        if isinstance(item, ast.Constant) and isinstance(item.value, int):
            out[str(key.value)] = int(item.value)
        else:
            default = getenv_int_default(item)
            if default is not None:
                out[str(key.value)] = default
    return out


def time_call(value: ast.AST) -> str | None:
    if not (
        isinstance(value, ast.Call)
        and isinstance(value.func, ast.Name)
        and value.func.id == "dt_time"
        and value.args
    ):
        return None
    parts = []
    for idx in range(3):
        if idx < len(value.args) and isinstance(value.args[idx], ast.Constant):
            parts.append(int(value.args[idx].value))
        else:
            parts.append(0)
    return f"{parts[0]:02d}:{parts[1]:02d}:{parts[2]:02d}"


def window_list(value: ast.AST | None) -> list[dict[str, Any]]:
    if not isinstance(value, ast.Tuple):
        return []
    windows: list[dict[str, Any]] = []
    for item in value.elts:
        if not isinstance(item, ast.Tuple) or len(item.elts) != 3:
            continue
        start = time_call(item.elts[0])
        end = time_call(item.elts[1])
        days_node = item.elts[2]
        if start is None or end is None or not isinstance(days_node, ast.Set):
            continue
        days = sorted(int(day.value) for day in days_node.elts if isinstance(day, ast.Constant))
        windows.append({"start": start, "end": end, "days": days})
    return windows


def check_tq_sdk_and_credentials(root: Path) -> CheckResult:
    text, _tree = parse_source(root / "data_manager_futures.py")
    required = [
        "from tqsdk import TqApi, TqAuth",
        "except ImportError:",
        "from tqsdk2 import TqApi, TqAuth",
        'os.getenv("TQ_PHONE"',
        'os.getenv("TQ_PASS"',
        "TqApi(auth=TqAuth(phone, pwd))",
    ]
    missing = [token for token in required if token not in text]
    risky_literals = []
    for token in ("TQ_PHONE =", "TQ_PASS =", "webhook"):
        if token in text:
            risky_literals.append(token)
    ok = not missing and not risky_literals
    return CheckResult(
        "tq_sdk_env_only_credentials",
        ok,
        f"missing={missing} risky_literals={risky_literals}" if not ok else "ok",
    )


def check_symbol_map(root: Path) -> CheckResult:
    _text, tree = parse_source(root / "data_manager_futures.py")
    symbols = dict_string_map(assigned_node(tree, "TQ_SYMBOL_MAP"))
    missing = sorted(EXPECTED_SYMBOLS - set(symbols))
    extra = sorted(set(symbols) - EXPECTED_SYMBOLS)
    bad_codes = {symbol: code for symbol, code in symbols.items() if not code.startswith("KQ.m@")}
    ok = not missing and not extra and not bad_codes and len(symbols) == len(EXPECTED_SYMBOLS)
    detail = f"count={len(symbols)} missing={missing} extra={extra} bad_codes={bad_codes}"
    return CheckResult("domestic_futures_34_symbol_tq_map", ok, detail)


def check_timeframes_and_lengths(root: Path) -> CheckResult:
    text, tree = parse_source(root / "data_manager_futures.py")
    timeframes = dict_int_map(assigned_node(tree, "TIMEFRAMES"))
    lengths = dict_int_map(assigned_node(tree, "DATA_LENGTHS"))
    missing_dirs = [tf for tf in EXPECTED_TIMEFRAMES if f'for d in ["1d", "1h", "15m", "5m"]' not in text and tf not in text]
    ok = timeframes == EXPECTED_TIMEFRAMES and lengths == EXPECTED_DATA_LENGTH_DEFAULTS and not missing_dirs
    detail = f"timeframes={timeframes} lengths={lengths} missing_dirs={missing_dirs}"
    return CheckResult("domestic_futures_timeframes_lengths", ok, detail)


def check_market_windows(root: Path) -> CheckResult:
    text, tree = parse_source(root / "data_manager_futures.py")
    futures = window_list(assigned_node(tree, "FUTURES_WINDOWS"))
    astock = window_list(assigned_node(tree, "A_STOCK_WINDOWS"))
    poll = constant_int(assigned_node(tree, "POLL_INTERVAL_SECONDS"))
    idle = constant_int(assigned_node(tree, "IDLE_SLEEP_SECONDS"))
    missing_tokens = [
        token
        for token in [
            'os.getenv("MARKET_MODE", "futures")',
            "return A_STOCK_WINDOWS",
            "return FUTURES_WINDOWS",
            "is_market_update_time",
            "seconds_until_next_window",
        ]
        if token not in text
    ]
    ok = (
        futures == EXPECTED_FUTURES_WINDOWS
        and astock == EXPECTED_A_STOCK_WINDOWS
        and poll == 300
        and idle == 60
        and not missing_tokens
    )
    detail = f"futures={futures} astock={astock} poll={poll} idle={idle} missing={missing_tokens}"
    return CheckResult("domestic_futures_day_night_windows", ok, detail)


def check_main_loop_idle_and_reuse(root: Path) -> CheckResult:
    text, tree = parse_source(root / "data_manager_futures.py")
    body = function_text(text, tree, "main")
    required = [
        "not is_market_update_time() and not needs_stale_catchup()",
        "api.close()",
        "api = None",
        'write_heartbeat("idle")',
        "time.sleep(min(wait_seconds, IDLE_SLEEP_SECONDS))",
        "if api is None:",
        "api = connect_api()",
        'write_heartbeat("connected")',
        "fetch_all_data(api)",
        "write_heartbeat(f\"poll ok={success_count} fail={fail_count}\")",
        "time.sleep(POLL_INTERVAL_SECONDS)",
    ]
    missing = [token for token in required if token not in body]
    return CheckResult(
        "domestic_futures_connection_idle_reuse",
        not missing,
        "missing=" + ",".join(missing) if missing else "ok",
    )


def check_watchdog_contract(root: Path) -> CheckResult:
    path = root / "scripts" / "watchdog_domestic.ps1"
    text = read_text(path)
    required = [
        "$HeartbeatMaxAgeSec = 420",
        "$DataStaleLimitSec = 1500",
        "data_manager_heartbeat.txt",
        "Get-Latest15mDataAge",
        "Test-DataManagerAlive",
        "Ensure-DataManager",
        "Ensure-SingleDataManager",
        "data_manager_futures.py",
        "connect_retry|connect",
    ]
    missing = [token for token in required if token not in text]
    return CheckResult("domestic_watchdog_data_manager_contract", not missing, "missing=" + ",".join(missing) if missing else "ok")


def check_market_boundary_doc(root: Path) -> CheckResult:
    text = read_text(root / "docs" / "MARKET_COVERAGE_BOUNDARIES.md")
    required = [
        "FUTURES_WINDOWS",
        "08:30",
        "11:35",
        "13:00",
        "15:15",
        "20:30",
        "23:59",
        "00:00",
        "02:35",
        "IDLE_SLEEP_SECONDS=60",
        "MARKET_MODE=astock",
        "A_STOCK_WINDOWS",
        "09:00",
        "12:30",
        "15:05",
        "23:00",
        "23:30",
        "01:00",
        "02:30",
    ]
    missing_tokens = [token for token in required if token not in text]
    missing_groups = []
    for end_time, symbols in EXPECTED_NIGHT_END_GROUPS.items():
        if end_time not in text:
            missing_groups.append(end_time)
            continue
        for symbol in symbols:
            if symbol not in text:
                missing_groups.append(f"{end_time}:{symbol}")
    covered = set().union(*EXPECTED_NIGHT_END_GROUPS.values())
    missing_symbols = sorted(EXPECTED_SYMBOLS - covered)
    extra_symbols = sorted(covered - EXPECTED_SYMBOLS)
    ok = not missing_tokens and not missing_groups and not missing_symbols and not extra_symbols
    detail = (
        f"missing_tokens={missing_tokens} missing_groups={missing_groups} "
        f"night_symbols={len(covered)} missing_symbols={missing_symbols} extra_symbols={extra_symbols}"
    )
    return CheckResult("market_coverage_doc_schedule_table", ok, detail)


def runtime_snapshot(root: Path) -> dict[str, Any]:
    data_dir = root / "data"
    log_dir = root / "runtime" / "logs"
    heartbeat = log_dir / "data_manager_heartbeat.txt"
    now = time.time()
    timeframe_counts: dict[str, int] = {}
    newest: dict[str, Any] = {}
    for tf in EXPECTED_TIMEFRAMES:
        folder = data_dir / tf
        files = list(folder.glob("*.csv")) if folder.is_dir() else []
        timeframe_counts[tf] = len(files)
        if files:
            latest = max(files, key=lambda path: path.stat().st_mtime)
            newest[tf] = {
                "path": str(latest.relative_to(root)) if latest.is_relative_to(root) else str(latest),
                "mtime": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(latest.stat().st_mtime)),
                "age_sec": int(now - latest.stat().st_mtime),
            }
    hb_age = None
    hb_note = None
    if heartbeat.is_file():
        hb_age = int(now - heartbeat.stat().st_mtime)
        try:
            hb_note = heartbeat.read_text(encoding="utf-8").strip()
        except OSError:
            hb_note = None
    return {
        "data_dir": str(data_dir),
        "timeframe_file_counts": timeframe_counts,
        "newest_csv": newest,
        "heartbeat_exists": heartbeat.is_file(),
        "heartbeat_age_sec": hb_age,
        "heartbeat_note": hb_note,
    }


def run_checks(root: Path = ROOT) -> list[CheckResult]:
    return [
        check_tq_sdk_and_credentials(root),
        check_symbol_map(root),
        check_timeframes_and_lengths(root),
        check_market_windows(root),
        check_main_loop_idle_and_reuse(root),
        check_watchdog_contract(root),
        check_market_boundary_doc(root),
    ]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit domestic futures Tianqin data schedule contracts.")
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
