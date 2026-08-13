#!/usr/bin/env python3
"""Audit that src/quant is only a compatibility shim over fengji_core.

The project historically used both src/quant and packages/fengji_core import
paths. This read-only audit prevents accidental drift by checking that local
src/quant modules re-export fengji_core modules instead of carrying strategy
logic, and that the domestic deploy script still syncs package core files into
the remote compatibility path.
"""
from __future__ import annotations

import argparse
import ast
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]

EXPECTED_SHIMS = {
    "__init__": ["fengji_core", "fengji_core.__version__"],
    "data": ["fengji_core.data"],
    "ds01": ["fengji_core.ds01"],
    "ds02": ["fengji_core.ds02"],
    "ds03": ["fengji_core.ds03"],
    "ds04": ["fengji_core.ds04"],
    "ds05": ["fengji_core.ds05"],
    "ds06": ["fengji_core.ds06"],
    "ds07": ["fengji_core.ds07"],
    "ds08": ["fengji_core.ds08"],
    "ds09": ["fengji_core.ds09"],
    "futures_specs": ["fengji_core.futures_specs"],
    "metrics": ["fengji_core.metrics"],
    "os_engine": ["fengji_core.os_engine"],
    "strategies": ["fengji_core.strategies"],
}

DOMESTIC_CORE_REMOTE_MAP = {
    "ds01": "$RemoteRoot/src/quant/ds01.py",
    "ds03": "$RemoteRoot/src/quant/ds03.py",
    "ds05": "$RemoteRoot/src/quant/ds05.py",
    "ds07": "$RemoteRoot/src/quant/ds07.py",
    "ds09": "$RemoteRoot/src/quant/ds09.py",
    "os_engine": "$RemoteRoot/src/quant/os_engine.py",
    "os_state_store": "$RemoteRoot/src/quant/os_state_store.py",
}


@dataclass(frozen=True)
class CheckResult:
    name: str
    ok: bool
    detail: str

    def as_dict(self) -> dict[str, Any]:
        return {"name": self.name, "ok": self.ok, "detail": self.detail}


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")


def imported_modules(tree: ast.Module) -> list[str]:
    imports: list[str] = []
    for node in tree.body:
        if isinstance(node, ast.ImportFrom):
            module = str(node.module or "")
            for alias in node.names:
                if module == "fengji_core" and alias.name == "__version__":
                    imports.append("fengji_core.__version__")
                elif alias.name == "*":
                    imports.append(module)
                else:
                    imports.append(f"{module}.{alias.name}")
    return imports


def disallowed_logic_nodes(tree: ast.Module) -> list[str]:
    blocked = (
        ast.FunctionDef,
        ast.AsyncFunctionDef,
        ast.ClassDef,
        ast.Assign,
        ast.AnnAssign,
        ast.AugAssign,
        ast.For,
        ast.While,
        ast.If,
        ast.Try,
        ast.With,
    )
    out: list[str] = []
    for node in tree.body:
        if isinstance(node, blocked):
            out.append(type(node).__name__)
    return out


def check_src_quant_shims(root: Path) -> CheckResult:
    src_dir = root / "src" / "quant"
    missing: list[str] = []
    unexpected_files: list[str] = []
    bad_imports: dict[str, dict[str, Any]] = {}
    logic_nodes: dict[str, list[str]] = {}

    expected_files = {f"{name}.py" for name in EXPECTED_SHIMS}
    actual_files = {path.name for path in src_dir.glob("*.py")}
    for name in sorted(expected_files - actual_files):
        missing.append(name)
    for name in sorted(actual_files - expected_files):
        unexpected_files.append(name)

    for module, expected_imports in sorted(EXPECTED_SHIMS.items()):
        path = src_dir / f"{module}.py"
        if not path.exists():
            continue
        tree = ast.parse(read_text(path), filename=str(path))
        imports = imported_modules(tree)
        if imports != expected_imports:
            bad_imports[module] = {"expected": expected_imports, "actual": imports}
        blocked = disallowed_logic_nodes(tree)
        if blocked:
            logic_nodes[module] = blocked

    ok = not missing and not unexpected_files and not bad_imports and not logic_nodes
    detail = (
        f"modules={len(EXPECTED_SHIMS)} missing={missing} unexpected={unexpected_files} "
        f"bad_imports={bad_imports} logic_nodes={logic_nodes}"
    )
    return CheckResult("src_quant_import_shims_only", ok, detail)


def check_package_core_modules_exist(root: Path) -> CheckResult:
    package_dir = root / "packages" / "fengji_core" / "fengji_core"
    missing = []
    for module in sorted(EXPECTED_SHIMS):
        if module == "__init__":
            path = package_dir / "__init__.py"
        else:
            path = package_dir / f"{module}.py"
        if not path.is_file():
            missing.append(str(path.relative_to(root)))
    return CheckResult(
        "fengji_core_source_modules_exist",
        not missing,
        "missing=" + ",".join(missing) if missing else "ok",
    )


def check_domestic_deploy_uses_package_core(root: Path) -> CheckResult:
    text = read_text(root / "scripts" / "sync_deploy_domestic.ps1").replace("\\", "/")
    missing: list[str] = []
    for module, remote in sorted(DOMESTIC_CORE_REMOTE_MAP.items()):
        local_token = f"$Core/{module}.py"
        remote_token = remote.replace("\\", "/")
        if local_token not in text or remote_token not in text:
            missing.append(module)
    return CheckResult(
        "domestic_sync_uses_package_core_source",
        not missing,
        "missing=" + ",".join(missing) if missing else "ok",
    )


def check_deploy_manifest_boundary(root: Path) -> CheckResult:
    text = read_text(root / "scripts" / "fengji_domestic_deploy_manifest.txt").replace("\\", "/")
    required = [
        "packages/fengji_core/fengji_core/os_engine.py",
        "packages/fengji_core/fengji_core/ds01.py",
        "packages/fengji_core/fengji_core/ds03.py",
        "packages/fengji_core/fengji_core/ds05.py",
        "packages/fengji_core/fengji_core/ds07.py",
        "packages/fengji_core/fengji_core/ds09.py",
    ]
    forbidden = [
        "src/quant/os_engine.py",
        "src/quant/ds01.py",
        "src/quant/ds03.py",
        "src/quant/ds05.py",
        "src/quant/ds07.py",
        "src/quant/ds09.py",
    ]
    missing = [item for item in required if item not in text]
    forbidden_present = [item for item in forbidden if item in text]
    ok = not missing and not forbidden_present
    return CheckResult(
        "domestic_manifest_core_source_boundary",
        ok,
        f"missing={missing} forbidden_present={forbidden_present}",
    )


def run_checks(root: Path = ROOT) -> list[CheckResult]:
    return [
        check_src_quant_shims(root),
        check_package_core_modules_exist(root),
        check_domestic_deploy_uses_package_core(root),
        check_deploy_manifest_boundary(root),
    ]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit src/quant compatibility shim boundary.")
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
