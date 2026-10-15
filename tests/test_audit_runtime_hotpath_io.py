"""防回归：热路径 IO 审计脚本必须通过（尾读 + 连接复用 + 数据泵告警）。"""
from __future__ import annotations

from scripts.audit_runtime_hotpath_io import run_checks


def test_hotpath_io_expectations_hold_on_real_code() -> None:
    failures = run_checks()
    assert failures == []
