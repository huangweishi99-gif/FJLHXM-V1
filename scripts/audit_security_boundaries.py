#!/usr/bin/env python3
"""Audit repo safety boundaries without printing secret values."""
from __future__ import annotations

import argparse
import json
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CODE_SUFFIXES = {".py", ".ps1", ".sh", ".bat", ".cmd"}
SKIP_PARTS = {"data", "runtime", "results", "test-results", ".git", "archives"}

FAIL_PATTERNS = {
    "complete_webhook_url": re.compile(
        r"https://[A-Za-z0-9.-]+/[^\s\"']*(?:webhook|hook|bot)[^\s\"']*",
        re.IGNORECASE,
    ),
    "openai_key_literal": re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9_-]{20,}\b"),
    "aws_access_key": re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    "ccxt_create_order": re.compile(r"\.create_order\s*\("),
    "binance_create_order": re.compile(r"(?<!\.)\b(?:futures_)?create_order\s*\("),
    "okx_place_order": re.compile(r"\b(?:place_order|TradeAPI)\b", re.IGNORECASE),
    "tq_insert_order": re.compile(r"\binsert_order\s*\("),
}

WARN_PATTERNS = {
    "secret_like_assignment": re.compile(
        r"(?i)\b(api[_-]?key|secret|token|password|passwd|webhook)\b\s*[:=]\s*[\"'][^\"']{8,}[\"']"
    ),
}


@dataclass(frozen=True)
class Finding:
    severity: str
    label: str
    path: str
    line: int

    def as_dict(self) -> dict[str, object]:
        return {
            "severity": self.severity,
            "label": self.label,
            "path": self.path,
            "line": self.line,
        }


def tracked_files(root: Path) -> list[Path]:
    proc = subprocess.run(
        ["git", "ls-files"],
        cwd=root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=True,
    )
    rels = {line.strip() for line in proc.stdout.splitlines() if line.strip()}
    rels.add("scripts/audit_security_boundaries.py")
    return [root / rel for rel in sorted(rels)]


def candidate_files(root: Path) -> list[Path]:
    paths: list[Path] = []
    for path in tracked_files(root):
        if not path.exists() or path.suffix.lower() not in CODE_SUFFIXES:
            continue
        rel_parts = path.relative_to(root).parts
        if any(part in SKIP_PARTS for part in rel_parts):
            continue
        paths.append(path)
    return paths


def warning_allowed(path: str, line: str) -> bool:
    stripped = line.strip()
    if "${" in stripped or "os.getenv" in stripped or "getenv(" in stripped:
        return True
    if "secrets.token" in stripped or "uuid.uuid" in stripped:
        return True
    if path.startswith("tests/"):
        return True
    if path.startswith("scripts/smoke_") or path.startswith("scripts/verify_v11_"):
        return "password" in stripped.lower()
    return False


def scan_file(path: Path, root: Path) -> list[Finding]:
    rel = path.relative_to(root).as_posix()
    findings: list[Finding] = []
    text = path.read_text(encoding="utf-8", errors="replace")
    for line_no, line in enumerate(text.splitlines(), 1):
        if rel == "scripts/audit_security_boundaries.py" and "re.compile(" in line:
            continue
        line_failed = False
        for label, pattern in FAIL_PATTERNS.items():
            if pattern.search(line):
                findings.append(Finding("fail", label, rel, line_no))
                line_failed = True
        if line_failed:
            continue
        for label, pattern in WARN_PATTERNS.items():
            if pattern.search(line) and not warning_allowed(rel, line):
                findings.append(Finding("warn", label, rel, line_no))
    return findings


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Audit hardcoded secrets and real-order API calls without printing values."
    )
    parser.add_argument("--json", action="store_true", help="print machine-readable JSON")
    args = parser.parse_args()

    findings: list[Finding] = []
    for path in candidate_files(ROOT):
        findings.extend(scan_file(path, ROOT))

    failures = [f for f in findings if f.severity == "fail"]
    warnings = [f for f in findings if f.severity == "warn"]
    payload = {
        "files_scanned": len(candidate_files(ROOT)),
        "failures": len(failures),
        "warnings": len(warnings),
        "findings": [f.as_dict() for f in findings],
    }
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(
            f"SECURITY_BOUNDARY_AUDIT files={payload['files_scanned']} "
            f"failures={payload['failures']} warnings={payload['warnings']}"
        )
        for finding in findings:
            print(
                f"{finding.severity.upper()} {finding.label} "
                f"{finding.path}:{finding.line}"
            )
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
