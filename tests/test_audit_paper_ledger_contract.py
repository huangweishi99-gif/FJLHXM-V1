from __future__ import annotations

import ast
from pathlib import Path


def test_argparse_defaults_extracts_literal_defaults(tmp_path: Path) -> None:
    from scripts.audit_paper_ledger_contract import argparse_defaults

    source = tmp_path / "sample.py"
    source.write_text(
        "def parse_args():\n"
        "    parser.add_argument('--fee-rate', type=float, default=0.0005)\n"
        "    parser.add_argument('--name', default='paper')\n",
        encoding="utf-8",
    )

    assert argparse_defaults(source) == {"--fee-rate": 0.0005, "--name": "paper"}


def test_string_dict_keys_extracts_function_dict_keys(tmp_path: Path) -> None:
    from scripts.audit_paper_ledger_contract import string_dict_keys

    source = tmp_path / "sample.py"
    source.write_text(
        "def make_record():\n"
        "    record = {'entry_price': 1, 'exit_price': 2}\n"
        "    other = {'ignored': 3}\n"
        "    return record\n",
        encoding="utf-8",
    )

    assert string_dict_keys(source, "make_record") == {
        "entry_price",
        "exit_price",
        "ignored",
    }


def test_current_paper_ledger_contract_passes() -> None:
    from scripts.audit_paper_ledger_contract import run_checks

    checks = run_checks()

    assert checks
    assert all(check.ok for check in checks), [check.as_dict() for check in checks if not check.ok]
