"""行为测试：scripts/audit_runtime_asset_bloat.py（只读资产膨胀盘点）。"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path

from scripts.audit_runtime_asset_bloat import main, scan_assets

MIN_MB = 0.001  # ~1KB，便于在 tmp 目录构造样本


def _age(path: Path, days: float) -> None:
    stamp = time.time() - days * 86400
    os.utime(path, (stamp, stamp))


def _make_root(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    (root / "src").mkdir(parents=True)
    (root / "runtime").mkdir(parents=True)
    return root


def test_scan_flags_stale_unreferenced_blobs(tmp_path: Path) -> None:
    root = _make_root(tmp_path)
    (root / "src" / "app.py").write_text("print('hi')\n", encoding="utf-8")
    blob = root / "runtime" / "orphan_events_tail.jsonl"
    blob.write_text("x" * 4096, encoding="utf-8")
    _age(blob, days=60)

    findings = scan_assets(root, min_mb=MIN_MB, stale_days=14, dirs=("runtime",))

    assert len(findings) == 1
    item = findings[0]
    assert item["path"] == "runtime/orphan_events_tail.jsonl"
    assert item["referenced_in_code"] is False
    assert item["stale"] is True
    assert float(item["age_days"]) >= 59


def test_scan_keeps_referenced_and_recent_files_out_of_stale(tmp_path: Path) -> None:
    root = _make_root(tmp_path)
    (root / "src" / "app.py").write_text("open('runtime/used_tail.jsonl')\n", encoding="utf-8")
    referenced = root / "runtime" / "used_tail.jsonl"
    referenced.write_text("x" * 4096, encoding="utf-8")
    _age(referenced, days=60)
    recent = root / "runtime" / "fresh_dump.jsonl"
    recent.write_text("y" * 4096, encoding="utf-8")  # 刚写入

    findings = {item["path"]: item for item in scan_assets(root, min_mb=MIN_MB, stale_days=14, dirs=("runtime",))}

    # 代码里有引用 => 即便很旧也不判 stale；刚写入 => 不判 stale
    assert findings["runtime/used_tail.jsonl"]["referenced_in_code"] is True
    assert findings["runtime/used_tail.jsonl"]["stale"] is False
    assert findings["runtime/fresh_dump.jsonl"]["stale"] is False


def test_scan_ignores_files_below_threshold(tmp_path: Path) -> None:
    root = _make_root(tmp_path)
    (root / "src" / "app.py").write_text("pass\n", encoding="utf-8")
    small = root / "runtime" / "tiny.jsonl"
    small.write_text("x" * 16, encoding="utf-8")

    assert scan_assets(root, min_mb=MIN_MB, stale_days=14, dirs=("runtime",)) == []


def test_main_reports_and_exit_codes(tmp_path: Path, capsys, monkeypatch) -> None:
    root = _make_root(tmp_path)
    (root / "src" / "app.py").write_text("pass\n", encoding="utf-8")
    blob = root / "runtime" / "orphan.jsonl"
    blob.write_text("x" * 4096, encoding="utf-8")
    _age(blob, days=60)
    monkeypatch.chdir(root)

    assert main(["--root", ".", "--min-mb", str(MIN_MB), "--dirs", "runtime"]) == 0
    assert "orphan.jsonl" in capsys.readouterr().out

    assert main(["--root", ".", "--min-mb", str(MIN_MB), "--dirs", "runtime", "--fail-on-stale"]) == 1


def test_main_writes_json_report(tmp_path: Path, monkeypatch) -> None:
    root = _make_root(tmp_path)
    (root / "src" / "app.py").write_text("pass\n", encoding="utf-8")
    blob = root / "runtime" / "orphan.jsonl"
    blob.write_text("x" * 4096, encoding="utf-8")
    _age(blob, days=60)
    report = root / "report.json"

    code = main(["--root", str(root), "--min-mb", str(MIN_MB), "--dirs", "runtime", "--json", str(report)])

    assert code == 0
    payload = json.loads(report.read_text(encoding="utf-8"))
    assert payload["stale_count"] == 1
    assert payload["findings"][0]["path"] == "runtime/orphan.jsonl"


def test_main_missing_root_returns_two(tmp_path: Path) -> None:
    assert main(["--root", str(tmp_path / "nope"), "--min-mb", str(MIN_MB)]) == 2
