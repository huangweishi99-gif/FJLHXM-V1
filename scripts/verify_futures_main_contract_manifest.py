#!/usr/bin/env python3
"""Audit domestic futures main-contract manifest (actual month, no KQ.m@ in CSV sources)."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

MAIN_CONTINUOUS_PREFIX = "KQ.m@"


def audit_manifest(payload: dict[str, Any]) -> tuple[list[dict[str, str]], dict[str, Any]]:
    issues: list[dict[str, str]] = []
    symbols = payload.get("symbols") or {}
    if not isinstance(symbols, dict) or not symbols:
        issues.append({"code": "NO_SYMBOLS", "message": "manifest has no symbols"})
        return issues, {}

    if payload.get("mode") != "tq_actual_main_contract":
        issues.append(
            {
                "code": "BAD_MODE",
                "message": f"expected mode=tq_actual_main_contract, got {payload.get('mode')!r}",
            }
        )

    ok_actual = 0
    bad_actual: list[str] = []
    bad_source: list[str] = []
    stale_tf: list[str] = []

    for code, entry in sorted(symbols.items()):
        if not isinstance(entry, dict):
            issues.append({"code": "BAD_ENTRY", "message": f"{code} entry is not an object"})
            continue
        tq_code = str(entry.get("tq_code") or "")
        underlying = str(entry.get("underlying_symbol") or "").strip()
        data_contract = str(entry.get("data_contract") or "").strip()
        is_actual = bool(entry.get("data_contract_is_actual"))

        if not tq_code.startswith(MAIN_CONTINUOUS_PREFIX):
            issues.append({"code": "BAD_TQ_CODE", "message": f"{code} tq_code={tq_code!r}"})
        if not underlying:
            bad_actual.append(code)
            issues.append({"code": "MISSING_UNDERLYING", "message": f"{code} missing underlying_symbol"})
        elif data_contract != underlying:
            bad_actual.append(code)
            issues.append(
                {
                    "code": "DATA_CONTRACT_MISMATCH",
                    "message": f"{code} data_contract={data_contract!r} != underlying={underlying!r}",
                }
            )
        elif not is_actual:
            bad_actual.append(code)
            issues.append({"code": "NOT_ACTUAL", "message": f"{code} data_contract_is_actual=False"})
        else:
            ok_actual += 1

        timeframes = entry.get("timeframes") or {}
        if not timeframes:
            stale_tf.append(code)
            issues.append({"code": "NO_TIMEFRAMES", "message": f"{code} has no timeframe rows yet"})
            continue
        for tf, meta in timeframes.items():
            if not isinstance(meta, dict):
                continue
            src_syms = meta.get("source_symbols") or []
            main_in_src = [s for s in src_syms if str(s).startswith(MAIN_CONTINUOUS_PREFIX)]
            if main_in_src:
                bad_source.append(code)
                issues.append(
                    {
                        "code": "MAIN_CONTINUOUS_IN_CSV",
                        "message": f"{code}/{tf} source_symbols contains main continuous: {main_in_src}",
                    }
                )
            tf_contract = str(meta.get("data_contract") or "").strip()
            if underlying and tf_contract and tf_contract != underlying:
                issues.append(
                    {
                        "code": "TF_CONTRACT_MISMATCH",
                        "message": f"{code}/{tf} data_contract={tf_contract!r} != underlying={underlying!r}",
                    }
                )

    summary = {
        "symbol_count": len(symbols),
        "ok_actual": ok_actual,
        "bad_actual_count": len(set(bad_actual)),
        "bad_source_count": len(set(bad_source)),
        "no_timeframes_count": len(stale_tf),
        "updated_at": payload.get("updated_at"),
        "mode": payload.get("mode"),
    }
    return issues, summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--manifest",
        default="runtime/logs/futures_main_contract_sources.json",
        help="Path to futures_main_contract_sources.json",
    )
    parser.add_argument("--json-out", default="", help="Optional report JSON path")
    args = parser.parse_args()

    path = Path(args.manifest)
    if not path.exists():
        print(f"FAIL manifest missing: {path}")
        return 1

    payload = json.loads(path.read_text(encoding="utf-8"))
    issues, summary = audit_manifest(payload)

    print(f"MANIFEST_AUDIT manifest={path}")
    print(f"  symbols={summary.get('symbol_count')} ok_actual={summary.get('ok_actual')} mode={summary.get('mode')}")
    print(f"  updated_at={summary.get('updated_at')}")
    print(f"  bad_actual={summary.get('bad_actual_count')} bad_source={summary.get('bad_source_count')} no_tf={summary.get('no_timeframes_count')}")

    for issue in issues[:20]:
        print(f"  - [{issue['code']}] {issue['message']}")
    if len(issues) > 20:
        print(f"  ... and {len(issues) - 20} more")

    report = {"ok": not issues, "summary": summary, "issues": issues}
    if args.json_out:
        out = Path(args.json_out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    if issues:
        print(f"FAIL issues={len(issues)}")
        return 1
    print("PASS manifest audit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
