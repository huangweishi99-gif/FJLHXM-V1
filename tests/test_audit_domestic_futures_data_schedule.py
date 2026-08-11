from __future__ import annotations

from pathlib import Path


def test_current_domestic_futures_data_schedule_contract_passes() -> None:
    from scripts.audit_domestic_futures_data_schedule import run_checks

    checks = run_checks()

    assert checks
    assert all(check.ok for check in checks), [check.as_dict() for check in checks if not check.ok]


def test_window_list_parses_dt_time_tuple() -> None:
    import ast

    from scripts.audit_domestic_futures_data_schedule import window_list

    node = ast.parse("WINDOWS = ((dt_time(8, 30), dt_time(11, 35), {0, 1, 2, 3, 4}),)").body[0].value

    assert window_list(node) == [{"start": "08:30:00", "end": "11:35:00", "days": [0, 1, 2, 3, 4]}]


def test_runtime_snapshot_reports_missing_dirs(tmp_path: Path) -> None:
    from scripts.audit_domestic_futures_data_schedule import runtime_snapshot

    snapshot = runtime_snapshot(tmp_path)

    assert snapshot["heartbeat_exists"] is False
    assert snapshot["timeframe_file_counts"] == {"1d": 0, "1h": 0, "15m": 0, "5m": 0}
