#!/usr/bin/env python3
"""Read-only audit for core DS logic deployment on domestic/overseas servers.

The audit checks hashes and coarse feature tokens for DS01/DS03/DS05/DS07
deployment. It does not print source code or secrets.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
TEXT_SUFFIXES = {".py", ".ps1", ".bat", ".cmd", ".md", ".txt", ".json", ".yaml", ".yml"}

CORE_FEATURES = {
    "packages/fengji_core/fengji_core/ds01.py": [
        "def ds01_left_filter_pass(",
        "lookback: int = 30",
        "max_lines: int = 2",
        "return left_count <= max_lines, left_count",
        "def ds01_os_defense_missing(",
        'row.get("active_low")',
        'row.get("active_high")',
    ],
    "packages/fengji_core/fengji_core/ds03.py": [
        "def make_peak_trade_key(",
        "consumed_peak_keys",
        'trigger_source="fake_peak"',
        'row, "last_failed_high_idx"',
        'row, "last_failed_low_idx"',
        "def resolve_ds03_attack(",
    ],
    "packages/fengji_core/fengji_core/ds05.py": [
        "k2_possible_extreme",
        "camp_k2 != camp_k3",
        "def has_price_gap_with_prev(",
        'float(df["low"].iloc[k2_idx - 3 : k2_idx + 1].min())',
        'float(df["high"].iloc[k2_idx - 3 : k2_idx + 1].max())',
    ],
    "packages/fengji_core/fengji_core/ds07.py": [
        "resolve_ds03_attack(df, i)",
        "LONG_CONTINUE",
        "SHORT_CONTINUE",
        "DS07 D1 Red + H1 Red DS03",
        "DS07 D1 Blue + H1 Blue DS03",
        "D1 camp_confirmed",
    ],
    "src/fengji_total_radar.py": [
        "ds01_left_filter_pass",
        "left_count=",
        "resolve_ds03_attack",
        "make_ds07_signal",
        "add_ds07",
    ],
}

REMOTE_PROFILES = {
    "domestic": {
        "host": "domestic-quant",
        "root": "C:/Users/Administrator/quant_futures",
        "python": "python",
    },
    "overseas": {
        "host": "overseas-quant",
        "root": "/home/ubuntu/quant_crypto",
        "python": ".venv/bin/python",
    },
}


@dataclass(frozen=True)
class CheckResult:
    name: str
    ok: bool
    detail: str

    def as_dict(self) -> dict[str, Any]:
        return {"name": self.name, "ok": self.ok, "detail": self.detail}


def normalized_bytes(path: Path) -> bytes:
    data = path.read_bytes()
    if path.suffix.lower() in TEXT_SUFFIXES:
        return data.replace(b"\r\n", b"\n")
    return data


def sha16_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()[:16]


def local_file_snapshot(root: Path, rel: str) -> dict[str, Any]:
    path = root / rel
    if not path.is_file():
        return {"exists": False, "hash": "MISSING", "missing_tokens": CORE_FEATURES[rel]}
    data = normalized_bytes(path)
    text = data.decode("utf-8-sig", errors="replace")
    missing_tokens = [token for token in CORE_FEATURES[rel] if token not in text]
    return {"exists": True, "hash": sha16_bytes(data), "missing_tokens": missing_tokens}


def local_snapshot(root: Path = ROOT) -> dict[str, dict[str, Any]]:
    return {rel: local_file_snapshot(root, rel) for rel in CORE_FEATURES}


def check_local_features(root: Path = ROOT) -> CheckResult:
    snapshot = local_snapshot(root)
    bad = {
        rel: {"exists": item["exists"], "missing_tokens": item["missing_tokens"]}
        for rel, item in snapshot.items()
        if not item["exists"] or item["missing_tokens"]
    }
    return CheckResult("local_core_feature_tokens", not bad, "bad=" + json.dumps(bad, ensure_ascii=False) if bad else "ok")


REMOTE_PROGRAM = r"""
import base64
import hashlib
import json
import pathlib
import sys

cfg = json.loads(base64.b64decode(sys.argv[1]).decode("utf-8"))
root = pathlib.Path(cfg["root"])
features = cfg["features"]
text_suffixes = set(cfg["text_suffixes"])
out = {}
for rel, tokens in features.items():
    path = root / rel
    if not path.is_file():
        out[rel] = {"exists": False, "hash": "MISSING", "missing_tokens": tokens}
        continue
    data = path.read_bytes()
    if path.suffix.lower() in text_suffixes:
        data = data.replace(bytes.fromhex("0d0a"), bytes.fromhex("0a"))
    text = data.decode("utf-8-sig", errors="replace")
    out[rel] = {
        "exists": True,
        "hash": hashlib.sha256(data).hexdigest()[:16],
        "missing_tokens": [token for token in tokens if token not in text],
    }
print(json.dumps(out, ensure_ascii=False))
"""


def remote_command(profile: dict[str, str], payload_b64: str, program_b64: str) -> str:
    root = profile["root"].replace("'", "''")
    python = profile["python"]
    return (
        f"cd '{root}'; {python} -c "
        "\"import base64,sys;program=sys.argv[1];payload=sys.argv[2];"
        "sys.argv=[sys.argv[0],payload];exec(base64.b64decode(program).decode())\" "
        f"{program_b64} {payload_b64}"
    )


def remote_snapshot(profile_name: str, *, timeout: int = 90) -> dict[str, dict[str, Any]]:
    profile = REMOTE_PROFILES[profile_name]
    payload = {
        "root": profile["root"],
        "features": CORE_FEATURES,
        "text_suffixes": sorted(TEXT_SUFFIXES),
    }
    payload_b64 = base64.b64encode(json.dumps(payload, ensure_ascii=False).encode("utf-8")).decode("ascii")
    program_b64 = base64.b64encode(REMOTE_PROGRAM.encode("utf-8")).decode("ascii")
    proc = subprocess.run(
        [
            "ssh",
            "-o",
            "BatchMode=yes",
            "-o",
            "ConnectTimeout=20",
            profile["host"],
            remote_command(profile, payload_b64, program_b64),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
    )
    if proc.returncode != 0:
        raise RuntimeError((proc.stderr or proc.stdout or "").strip())
    lines = [line for line in (proc.stdout or "").splitlines() if line.strip()]
    if not lines:
        raise RuntimeError("remote audit returned no output")
    return json.loads(lines[-1])


def compare_snapshots(local: dict[str, dict[str, Any]], remote: dict[str, dict[str, Any]]) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    mismatches = 0
    for rel in CORE_FEATURES:
        local_item = local.get(rel, {})
        remote_item = remote.get(rel, {})
        match = (
            bool(local_item.get("exists"))
            and bool(remote_item.get("exists"))
            and local_item.get("hash") == remote_item.get("hash")
            and not remote_item.get("missing_tokens")
        )
        if not match:
            mismatches += 1
        rows.append(
            {
                "file": rel,
                "local": local_item.get("hash", "MISSING"),
                "remote": remote_item.get("hash", "MISSING"),
                "match": match,
                "remote_missing_tokens": remote_item.get("missing_tokens", CORE_FEATURES[rel]),
            }
        )
    return {"mismatches": mismatches, "rows": rows}


def run_checks(root: Path = ROOT) -> list[CheckResult]:
    return [check_local_features(root)]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit core DS logic deployment on servers.")
    parser.add_argument("--root", default=str(ROOT))
    parser.add_argument(
        "--remote",
        choices=["none", "domestic", "overseas", "all"],
        default="none",
        help="live SSH remote audit target",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = Path(args.root).resolve()
    checks = run_checks(root)
    local = local_snapshot(root)
    remotes: dict[str, Any] = {}
    failures = [check for check in checks if not check.ok]
    targets = [] if args.remote == "none" else (["domestic", "overseas"] if args.remote == "all" else [args.remote])
    for target in targets:
        try:
            remote = remote_snapshot(target)
            comparison = compare_snapshots(local, remote)
            remotes[target] = comparison
            if comparison["mismatches"]:
                failures.append(
                    CheckResult(
                        f"{target}_core_deploy_match",
                        False,
                        f"mismatches={comparison['mismatches']}",
                    )
                )
        except Exception as exc:
            remotes[target] = {"error": str(exc)}
            failures.append(CheckResult(f"{target}_core_deploy_match", False, str(exc)))
    payload = {
        "checks": [check.as_dict() for check in checks],
        "failures": len(failures),
        "local": local,
        "remotes": remotes,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
