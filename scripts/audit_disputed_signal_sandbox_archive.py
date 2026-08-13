#!/usr/bin/env python3
"""Inventory disputed signal sandbox review artifacts.

The audit is intentionally read-only for strategy logic: it does not recalculate
signals or render charts. It inventories existing PNG/SVG/MD/JSON artifacts and
writes a small index that separates "visual archived" from "report only, chart
still missing".
"""
from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT_DIR = ROOT / "results" / "disputed_signal_sandbox_archive_20260712"
VISUAL_SUFFIXES = {".png", ".svg"}


@dataclass(frozen=True)
class ArtifactCase:
    case_id: str
    label: str
    strategy_id: str
    visual_patterns: tuple[str, ...]
    report_patterns: tuple[str, ...] = ()
    note: str = ""
    d4_symbol: str = ""


CASES: tuple[ArtifactCase, ...] = (
    ArtifactCase(
        "render_ds01_left30",
        "RENDERUSDT DS01 左30",
        "DS01",
        ("results/ds01_three_coin_review_20260618/RENDERUSDT_DS01_short.png",),
        ("results/ds01_three_coin_review_20260618/RENDERUSDT_DS01.md",),
    ),
    ArtifactCase(
        "io_ds01_left30",
        "IOUSDT DS01 左30",
        "DS01",
        (
            "results/ds01_three_coin_review_20260618/IOUSDT_DS01_short.png",
            "results/iousdt_latest_trade_audit_20260618/IOUSDT_DS01_short_latest.png",
        ),
        ("results/ds01_three_coin_review_20260618/IOUSDT_DS01.md",),
    ),
    ArtifactCase(
        "doge_ds01_left30",
        "DOGEUSDT DS01 左30",
        "DS01",
        ("results/ds01_three_coin_review_20260618/DOGEUSDT_DS01_short.png",),
        ("results/ds01_three_coin_review_20260618/DOGEUSDT_DS01.md",),
    ),
    ArtifactCase(
        "io_ds03_failed_peak",
        "IOUSDT DS03 假峰/真峰",
        "DS03",
        (
            "results/sandbox/io_ds03_20260528/IOUSDT_DS03_long_20260526.png",
            "results/sandbox/overseas_20260528/IOUSDT_DS03_long*.png",
            "results/sandbox/IOUSDT_DS03_20260527_long.svg",
        ),
        ("results/sandbox/d4_phase2_20260707/SUMMARY.md",),
    ),
    ArtifactCase(
        "eth_ds03_blue_short",
        "ETHUSDT DS03 蓝阵营空头",
        "DS03",
        ("results/sandbox/ETHUSDT_DS03_20260527_short.svg",),
        ("results/sandbox/d4_phase2_20260707/SUMMARY.md",),
        note="Current archived visual is SVG, not PNG.",
    ),
    ArtifactCase(
        "render_camp_d1",
        "RENDERUSDT D1 阵营图",
        "OS",
        ("results/crypto_camp_sandbox_review_20260618/RENDERUSDT_D1_camp_review.png",),
        ("results/crypto_camp_sandbox_review_20260618/SUMMARY.md",),
    ),
    ArtifactCase(
        "io_camp_d1",
        "IOUSDT D1 阵营图",
        "OS",
        ("results/crypto_camp_sandbox_review_20260618/IOUSDT_D1_camp_review.png",),
        ("results/crypto_camp_sandbox_review_20260618/SUMMARY.md",),
    ),
    ArtifactCase(
        "doge_camp_d1",
        "DOGEUSDT D1 阵营图",
        "OS",
        ("results/crypto_camp_sandbox_review_20260618/DOGEUSDT_D1_camp_review.png",),
        ("results/crypto_camp_sandbox_review_20260618/SUMMARY.md",),
    ),
    ArtifactCase(
        "ltc_camp_d1",
        "LTCUSDT D1 阵营图",
        "OS",
        ("results/crypto_camp_sandbox_review_20260618/LTCUSDT_D1_camp_review.png",),
        ("results/crypto_camp_sandbox_review_20260618/SUMMARY.md",),
    ),
    ArtifactCase(
        "cj_ds05_k2_extreme",
        "红枣 CJ DS05 K2 可能极",
        "DS05",
        ("results/sandbox/d4_phase2_*/CJ*DS05*.png", "results/sandbox/d4_phase2_*/*红枣*DS05*.png"),
        ("results/sandbox/d4_phase2_*/SUMMARY.md", "results/sandbox/d4_phase2_*/d4_report.json"),
        d4_symbol="CJ",
    ),
    ArtifactCase(
        "fg_ds05_k2_extreme",
        "玻璃 FG DS05 K2 可能极",
        "DS05",
        ("results/sandbox/d4_phase2_*/FG*DS05*.png", "results/sandbox/d4_phase2_*/*玻璃*DS05*.png"),
        ("results/sandbox/d4_phase2_*/SUMMARY.md", "results/sandbox/d4_phase2_*/d4_report.json"),
        d4_symbol="FG",
    ),
    ArtifactCase(
        "sa_ds05_k2_extreme",
        "纯碱 SA DS05 K2 可能极",
        "DS05",
        ("results/sandbox/d4_phase2_*/SA*DS05*.png", "results/sandbox/d4_phase2_*/*纯碱*DS05*.png"),
        ("results/sandbox/d4_phase2_*/SUMMARY.md", "results/sandbox/d4_phase2_*/d4_report.json"),
        d4_symbol="SA",
    ),
)


def relpath(root: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def find_paths(root: Path, patterns: tuple[str, ...]) -> list[Path]:
    out: list[Path] = []
    seen: set[Path] = set()
    for pattern in patterns:
        matches = list(root.glob(pattern)) if any(ch in pattern for ch in "*?[]") else [root / pattern]
        for path in matches:
            if path.is_file() and path not in seen:
                out.append(path)
                seen.add(path)
    return sorted(out, key=lambda p: relpath(root, p))


def load_d4_cases(root: Path) -> dict[str, dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    reports = sorted((root / "results" / "sandbox").glob("d4_phase2_*/d4_report.json"))
    for path in reports:
        try:
            data = json.loads(path.read_text(encoding="utf-8-sig"))
        except Exception:
            continue
        cases = data.get("sections", {}).get("ds05_futures_cases", [])
        for item in cases:
            if isinstance(item, dict):
                symbol = str(item.get("symbol", "")).upper()
                if symbol:
                    merged[symbol] = item
    return merged


def inspect_case(root: Path, case: ArtifactCase, d4_cases: dict[str, dict[str, Any]]) -> dict[str, Any]:
    visuals = find_paths(root, case.visual_patterns)
    reports = find_paths(root, case.report_patterns)
    d4_item = d4_cases.get(case.d4_symbol.upper()) if case.d4_symbol else None
    d4_status = str((d4_item or {}).get("status", "") or "")
    d4_latest = ((d4_item or {}).get("scan") or {}).get("latest") or {}
    report_evidence = bool(reports) or d4_status == "ok"
    if visuals:
        status = "archived"
    elif report_evidence:
        status = "missing_visual"
    else:
        status = "missing_evidence"
    return {
        "case_id": case.case_id,
        "label": case.label,
        "strategy_id": case.strategy_id,
        "status": status,
        "visuals": [relpath(root, path) for path in visuals],
        "reports": [relpath(root, path) for path in reports],
        "d4_status": d4_status,
        "d4_latest": d4_latest,
        "note": case.note,
    }


def build_archive(root: Path = ROOT) -> dict[str, Any]:
    d4_cases = load_d4_cases(root)
    rows = [inspect_case(root, case, d4_cases) for case in CASES]
    archived = sum(1 for row in rows if row["status"] == "archived")
    missing_visuals = sum(1 for row in rows if row["status"] == "missing_visual")
    missing_evidence = sum(1 for row in rows if row["status"] == "missing_evidence")
    return {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "total": len(rows),
        "archived_visuals": archived,
        "missing_visuals": missing_visuals,
        "missing_evidence": missing_evidence,
        "failures": missing_evidence,
        "rows": rows,
    }


def render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Disputed Signal Sandbox Archive",
        "",
        f"Generated: {payload['generated_at']}",
        "",
        f"- archived_visuals: {payload['archived_visuals']}/{payload['total']}",
        f"- missing_visuals: {payload['missing_visuals']}",
        f"- missing_evidence: {payload['missing_evidence']}",
        "",
        "| Case | Strategy | Status | Visual | Evidence | Note |",
        "|---|---|---|---|---|---|",
    ]
    for row in payload["rows"]:
        visual = "<br>".join(f"`{item}`" for item in row["visuals"]) or "-"
        evidence_items = list(row["reports"])
        if row.get("d4_status"):
            latest = row.get("d4_latest") or {}
            evidence_items.append(
                f"d4_status={row['d4_status']} latest={latest.get('date', '-')}"
            )
        evidence = "<br>".join(f"`{item}`" if "/" in item else item for item in evidence_items) or "-"
        lines.append(
            f"| {row['label']} | {row['strategy_id']} | **{row['status']}** | {visual} | {evidence} | {row.get('note') or ''} |"
        )
    missing = [row for row in payload["rows"] if row["status"] != "archived"]
    if missing:
        lines.extend(["", "## Follow-up"])
        for row in missing:
            lines.append(f"- {row['label']}: {row['status']}")
    return "\n".join(lines) + "\n"


def write_index(payload: dict[str, Any], out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "archive_index.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    (out_dir / "INDEX.md").write_text(render_markdown(payload), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit disputed signal sandbox archive coverage.")
    parser.add_argument("--root", default=str(ROOT))
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR))
    parser.add_argument("--no-write", action="store_true", help="only print JSON summary; do not write index files")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = Path(args.root).resolve()
    payload = build_archive(root)
    if not args.no_write:
        write_index(payload, Path(args.out_dir))
    print(json.dumps({k: payload[k] for k in ("total", "archived_visuals", "missing_visuals", "missing_evidence", "failures")}, ensure_ascii=False, indent=2))
    return 1 if payload["failures"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
