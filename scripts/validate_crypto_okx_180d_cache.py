#!/usr/bin/env python3
"""Guard: crypto_okx *_180d.csv must not exceed expected row counts (memory safety)."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# 180 calendar days upper bounds (generous slack)
LIMITS = {
    "1D": 200,
    "1H": 4500,
    "15m": 20000,
    "5m": 55000,
}


def check_file(path: Path, limits: dict[str, int]) -> list[str]:
    errors: list[str] = []
    name = path.name
    if "_180d" not in name and "_1825d" not in name:
        return errors
    for tf, cap in limits.items():
        token = f"_{tf}_"
        if token not in name:
            continue
        try:
            rows = sum(1 for _ in path.open(encoding="utf-8", errors="replace")) - 1
        except OSError as exc:
            errors.append(f"{path.name}: read error {exc}")
            return errors
        if rows > cap:
            errors.append(f"{path.name}: rows={rows} > cap={cap} ({tf})")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate crypto_okx 180d cache row counts.")
    parser.add_argument("--dir", default="data/crypto_okx")
    parser.add_argument("--max-15m-rows", type=int, default=LIMITS["15m"])
    args = parser.parse_args()
    limits = dict(LIMITS)
    limits["15m"] = args.max_15m_rows
    root = Path(args.dir)
    if not root.is_dir():
        print(f"SKIP: missing {root}")
        return 0
    all_errors: list[str] = []
    for path in sorted(root.glob("*_180d.csv")):
        all_errors.extend(check_file(path, limits))
    if all_errors:
        print("CRYPTO_180D_CACHE_FAIL")
        for line in all_errors:
            print(line)
        return 1
    print(f"CRYPTO_180D_CACHE_OK files={len(list(root.glob('*_180d.csv')))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
