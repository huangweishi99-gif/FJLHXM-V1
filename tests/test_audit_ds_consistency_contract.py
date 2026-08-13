from __future__ import annotations

from pathlib import Path


def test_current_ds_consistency_contract_passes() -> None:
    from scripts.audit_ds_consistency_contract import run_checks

    checks = run_checks()

    assert checks
    assert all(check.ok for check in checks), [check.as_dict() for check in checks if not check.ok]


def test_check_contract_reports_missing_tokens(tmp_path: Path) -> None:
    from scripts.audit_ds_consistency_contract import Contract, check_contract

    rel = "packages/fengji_core/fengji_core/ds01.py"
    path = tmp_path / rel
    path.parent.mkdir(parents=True)
    path.write_text("def ds01_left_filter_pass():\n    return True\n", encoding="utf-8")
    contract = Contract(
        name="tmp_contract",
        path=rel,
        required_tokens=("def ds01_left_filter_pass(", "max_lines: int = 2"),
    )

    result = check_contract(tmp_path, contract)

    assert not result.ok
    assert "max_lines: int = 2" in result.detail


def test_check_contract_reports_missing_file(tmp_path: Path) -> None:
    from scripts.audit_ds_consistency_contract import Contract, check_contract

    contract = Contract(name="missing_contract", path="missing.py", required_tokens=("x",))

    result = check_contract(tmp_path, contract)

    assert not result.ok
    assert "missing_file=missing.py" == result.detail


def test_check_contract_reports_forbidden_token(tmp_path: Path) -> None:
    from scripts.audit_ds_consistency_contract import Contract, check_contract

    rel = "src/fengji_total_radar.py"
    path = tmp_path / rel
    path.parent.mkdir(parents=True)
    path.write_text("current_contract\nold_contract\n", encoding="utf-8")
    contract = Contract(
        name="forbidden_contract",
        path=rel,
        required_tokens=("current_contract",),
        forbidden_tokens=("old_contract",),
    )

    result = check_contract(tmp_path, contract)

    assert not result.ok
    assert "old_contract" in result.detail


def test_ds07_contract_rejects_legacy_align_turn(tmp_path: Path) -> None:
    """DS07 旧逻辑（ALIGN_TURN 并轨 + 峰极线突破触发）不得回流权威源与雷达。"""
    from scripts.audit_ds_consistency_contract import (
        Contract,
        check_contract,
        CONTRACTS,
    )

    ds07_contract = next(
        contract for contract in CONTRACTS if contract.name == "ds07_core_new_resonance_contract"
    )
    assert "LONG_ALIGN_TURN" in ds07_contract.forbidden_tokens
    assert "high > float(blue_ext)" in ds07_contract.forbidden_tokens
    assert "low < float(red_ext)" in ds07_contract.forbidden_tokens

    # 权威源若混入旧标记，即使新逻辑 token 全在也必须报失败
    rel = "packages/fengji_core/fengji_core/ds07.py"
    path = tmp_path / rel
    path.parent.mkdir(parents=True)
    path.write_text(
        "from fengji_core.ds03 import resolve_ds03_attack\n"
        "resolve_ds03_attack(df, i)\n"
        "LONG_CONTINUE\nSHORT_CONTINUE\n"
        "DS07 D1 Red + H1 Red DS03\nDS07 D1 Blue + H1 Blue DS03\n"
        "camp_confirmed\n"
        "LONG_ALIGN_TURN\n",
        encoding="utf-8",
    )
    result = check_contract(tmp_path, ds07_contract)

    assert not result.ok
    assert "LONG_ALIGN_TURN" in result.detail


def test_radar_contract_rejects_legacy_align_turn(tmp_path: Path) -> None:
    """雷达入口同样禁止 DS07 旧 ALIGN_TURN 标记回流。"""
    from scripts.audit_ds_consistency_contract import Contract, check_contract, CONTRACTS

    radar_contract = next(
        contract for contract in CONTRACTS if contract.name == "radar_uses_canonical_ds_contracts"
    )
    assert "SHORT_ALIGN_TURN" in radar_contract.forbidden_tokens

    rel = "src/fengji_total_radar.py"
    path = tmp_path / rel
    path.parent.mkdir(parents=True)
    path.write_text(
        "from quant.ds01 import ds01_left_filter_pass, ds01_os_defense_missing\n"
        "from quant.ds03 import resolve_ds03_attack\n"
        "from quant.ds05 import make_ds05_signal\n"
        "from quant.ds07 import attach_os_detail, make_ds07_signal, map_d1_to_h1_future\n"
        "left_count=\n"
        "resolve_ds03_attack(d1, i)\n"
        "K2 possible extreme\n"
        "make_ds07_signal(cur, i, set(), symbol=symbol, prev_row=prev, df=mapped)\n"
        "SHORT_ALIGN_TURN\n",
        encoding="utf-8",
    )
    result = check_contract(tmp_path, radar_contract)

    assert not result.ok
    assert "SHORT_ALIGN_TURN" in result.detail
