#!/usr/bin/env python3
"""Audit the post-fill sandbox review orchestration contract.

This is a read-only static/runtime-light audit. It verifies that effective
pending summaries can launch a review manifest by default, that chart execution
requires an explicit flag, and that supported DS plotters are wired without
reimplementing strategy logic in the orchestration layer.
"""
from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
EXPECTED_SUPPORTED = {"DS01", "DS03", "DS04", "DS05", "DS07", "DS08", "DS09"}
EXPECTED_PLOTTERS = {
    "DS01": ["scripts/plot_crypto_ds01_trade_sandbox.py"],
    "DS03": ["scripts/plot_live_ds03_sandbox.py"],
    "DS04": ["scripts/plot_live_ds04_sandbox.py"],
    "DS05": ["scripts/plot_live_ds05_sandbox.py", "src/plot_ds05_sandbox.py"],
    "DS07": ["scripts/plot_live_ds07_sandbox.py"],
    "DS08": ["scripts/plot_live_ds08_sandbox.py"],
    "DS09": ["scripts/plot_live_ds09_sandbox.py", "src/plot_ds09_sandbox.py"],
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


def normalized(text: str) -> str:
    return text.replace("\\", "/")


def check_contains(name: str, text: str, tokens: list[str]) -> CheckResult:
    body = normalized(text)
    missing = [token for token in tokens if normalized(token) not in body]
    return CheckResult(name, not missing, "missing=" + ",".join(missing) if missing else "ok")


def check_effective_summary_entry(root: Path) -> CheckResult:
    text = read_text(root / "scripts" / "summarize_pending_effective_status.py")
    return check_contains(
        "effective_summary_sandbox_review_entry",
        text,
        [
            'FILL_REVIEW_STATUSES = {"filled", "filled_open"}',
            '"review_candidate_orders": sum',
            "def build_sandbox_review_command(",
            "generate_fill_sandbox_review.py",
            'parser.add_argument("--sandbox-review"',
            'parser.add_argument("--sandbox-review-execute"',
            'parser.add_argument("--event-tail-lines", type=int, default=20000)',
            'parser.add_argument("--review-out-dir", default="runtime/fill_sandbox_review")',
            "if args.sandbox_review_execute:",
            'command.extend(["--execute", "--timeout", str(args.review_timeout)])',
            "sandbox review: no filled or filled_open candidates",
        ],
    )


def check_review_generator_contract(root: Path) -> CheckResult:
    text = read_text(root / "scripts" / "generate_fill_sandbox_review.py")
    return check_contains(
        "fill_sandbox_review_generator_contract",
        text,
        [
            'FILL_STATUSES = {"filled", "filled_open"}',
            'SUPPORTED_STRATEGIES = {"DS01", "DS03", "DS04", "DS05", "DS07", "DS08", "DS09"}',
            "def tail_text_lines(",
            "event_tail_lines: int = 20000",
            "def build_review_tasks(",
            "def execute_tasks(",
            "if task.status != \"ready\":",
            "fill_sandbox_review.json",
            "fill_sandbox_review.md",
            "render_markdown(tasks)",
            "The script is intentionally an orchestration layer.",
        ],
    )


def check_supported_plotters(root: Path) -> CheckResult:
    generator = normalized(read_text(root / "scripts" / "generate_fill_sandbox_review.py"))
    missing_files: list[str] = []
    missing_refs: list[str] = []
    for strategy, rels in EXPECTED_PLOTTERS.items():
        for rel in rels:
            if not (root / rel).is_file():
                missing_files.append(rel)
            if Path(rel).name not in generator:
                missing_refs.append(f"{strategy}:{rel}")
    missing_strategy_refs = [strategy for strategy in sorted(EXPECTED_SUPPORTED) if f'"{strategy}"' not in generator]
    ok = not missing_files and not missing_refs and not missing_strategy_refs
    detail = (
        f"missing_files={missing_files} missing_refs={missing_refs} "
        f"missing_strategy_refs={missing_strategy_refs}"
    )
    return CheckResult("supported_ds_plotter_wiring", ok, detail)


def check_tests_cover_flow(root: Path) -> CheckResult:
    summary_test = read_text(root / "tests" / "test_summarize_pending_effective_status.py")
    review_test = read_text(root / "tests" / "test_generate_fill_sandbox_review.py")
    return check_contains(
        "fill_sandbox_review_test_coverage",
        summary_test + "\n" + review_test,
        [
            "test_build_sandbox_review_command_reuses_effective_summary_paths",
            "test_builds_ready_ds01_review_task_from_filled_open_order",
            "test_marks_filled_unsupported_strategy_explicitly",
            "test_ds05_filled_open_uses_live_plotter",
            "test_ds09_filled_open_uses_live_plotter",
            "test_load_jsonl_reads_only_tail_lines",
            "test_match_trade_no_uses_side_price_and_date",
        ],
    )


def runtime_snapshot(root: Path) -> dict[str, Any]:
    out_dir = root / "runtime" / "fill_sandbox_review"
    json_path = out_dir / "fill_sandbox_review.json"
    md_path = out_dir / "fill_sandbox_review.md"
    png_count = len(list(out_dir.glob("*.png"))) if out_dir.is_dir() else 0
    return {
        "out_dir": str(out_dir),
        "out_dir_exists": out_dir.is_dir(),
        "review_json_exists": json_path.is_file(),
        "review_md_exists": md_path.is_file(),
        "png_count": png_count,
    }


def run_checks(root: Path = ROOT) -> list[CheckResult]:
    return [
        check_effective_summary_entry(root),
        check_review_generator_contract(root),
        check_supported_plotters(root),
        check_tests_cover_flow(root),
    ]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit fill sandbox review orchestration.")
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
