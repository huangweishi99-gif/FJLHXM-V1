from __future__ import annotations

import json
from pathlib import Path


def test_current_disputed_signal_archive_has_no_missing_evidence() -> None:
    from scripts.audit_disputed_signal_sandbox_archive import build_archive

    payload = build_archive()

    assert payload["total"] >= 12
    assert payload["failures"] == 0
    assert payload["archived_visuals"] >= 12
    assert payload["missing_visuals"] == 0


def test_missing_visual_with_report_is_not_failure(tmp_path: Path) -> None:
    from scripts.audit_disputed_signal_sandbox_archive import ArtifactCase, inspect_case

    report = tmp_path / "results" / "sandbox" / "d4_phase2_20260707" / "SUMMARY.md"
    report.parent.mkdir(parents=True)
    report.write_text("FG report only\n", encoding="utf-8")
    case = ArtifactCase(
        case_id="fg",
        label="FG",
        strategy_id="DS05",
        visual_patterns=("results/sandbox/d4_phase2_20260707/FG*DS05*.png",),
        report_patterns=("results/sandbox/d4_phase2_20260707/SUMMARY.md",),
    )

    row = inspect_case(tmp_path, case, {})

    assert row["status"] == "missing_visual"
    assert row["reports"] == ["results/sandbox/d4_phase2_20260707/SUMMARY.md"]


def test_missing_visual_without_report_is_missing_evidence(tmp_path: Path) -> None:
    from scripts.audit_disputed_signal_sandbox_archive import ArtifactCase, inspect_case

    case = ArtifactCase(
        case_id="eth",
        label="ETH",
        strategy_id="DS03",
        visual_patterns=("results/sandbox/ETH*.svg",),
        report_patterns=("results/sandbox/SUMMARY.md",),
    )

    row = inspect_case(tmp_path, case, {})

    assert row["status"] == "missing_evidence"


def test_write_index_creates_json_and_markdown(tmp_path: Path) -> None:
    from scripts.audit_disputed_signal_sandbox_archive import write_index

    payload = {
        "generated_at": "2026-07-12 12:00:00",
        "total": 1,
        "archived_visuals": 1,
        "missing_visuals": 0,
        "missing_evidence": 0,
        "failures": 0,
        "rows": [
            {
                "label": "RENDER",
                "strategy_id": "DS01",
                "status": "archived",
                "visuals": ["results/x.png"],
                "reports": ["results/x.md"],
                "d4_status": "",
                "d4_latest": {},
                "note": "",
            }
        ],
    }

    write_index(payload, tmp_path)

    data = json.loads((tmp_path / "archive_index.json").read_text(encoding="utf-8"))
    md = (tmp_path / "INDEX.md").read_text(encoding="utf-8")
    assert data["archived_visuals"] == 1
    assert "RENDER" in md
