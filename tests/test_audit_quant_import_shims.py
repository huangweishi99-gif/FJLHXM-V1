from __future__ import annotations

import ast
from pathlib import Path


def test_current_quant_import_shim_contract_passes() -> None:
    from scripts.audit_quant_import_shims import run_checks

    checks = run_checks()

    assert checks
    assert all(check.ok for check in checks), [check.as_dict() for check in checks if not check.ok]


def test_disallowed_logic_nodes_detects_function_body() -> None:
    from scripts.audit_quant_import_shims import disallowed_logic_nodes

    tree = ast.parse("from fengji_core.ds01 import *\ndef old_logic():\n    return 1\n")

    assert disallowed_logic_nodes(tree) == ["FunctionDef"]


def test_imported_modules_handles_star_and_version_import() -> None:
    from scripts.audit_quant_import_shims import imported_modules

    tree = ast.parse("from fengji_core import *\nfrom fengji_core import __version__\n")

    assert imported_modules(tree) == ["fengji_core", "fengji_core.__version__"]


def test_read_text_strips_utf8_bom(tmp_path: Path) -> None:
    from scripts.audit_quant_import_shims import read_text

    path = tmp_path / "shim.py"
    path.write_bytes(b"\xef\xbb\xbffrom fengji_core import *\n")

    assert read_text(path).startswith("from fengji_core")


def test_check_src_quant_shims_reports_bad_tmp_module(tmp_path: Path) -> None:
    from scripts.audit_quant_import_shims import check_src_quant_shims

    src_quant = tmp_path / "src" / "quant"
    src_quant.mkdir(parents=True)
    for name, target in {
        "__init__": "from fengji_core import *\nfrom fengji_core import __version__\n",
        "data": "from fengji_core.data import *\n",
        "ds01": "from fengji_core.ds01 import *\n",
        "ds02": "from fengji_core.ds02 import *\n",
        "ds03": "from fengji_core.ds03 import *\n",
        "ds04": "from fengji_core.ds04 import *\n",
        "ds05": "from fengji_core.ds05 import *\n",
        "ds06": "from fengji_core.ds06 import *\n",
        "ds07": "from fengji_core.ds07 import *\n",
        "ds08": "from fengji_core.ds08 import *\n",
        "ds09": "from fengji_core.ds09 import *\n",
        "futures_specs": "from fengji_core.futures_specs import *\n",
        "metrics": "from fengji_core.metrics import *\n",
        "os_engine": "from fengji_core.os_engine import *\n",
        "strategies": "from fengji_core.strategies import *\n",
    }.items():
        (src_quant / f"{name}.py").write_text(target, encoding="utf-8")
    (src_quant / "ds01.py").write_text("from fengji_core.ds01 import *\nVALUE = 1\n", encoding="utf-8")

    result = check_src_quant_shims(tmp_path)

    assert not result.ok
    assert "ds01" in result.detail
