from __future__ import annotations

from pathlib import Path


def test_audit_detects_real_webhook_without_printing_value(tmp_path: Path) -> None:
    from scripts.audit_security_boundaries import ROOT, scan_file

    path = tmp_path / "sample.py"
    path.write_text(
        'WEBHOOK = "https://example.com/open-apis/bot/v2/hook/secret-value"\n',
        encoding="utf-8",
    )

    findings = scan_file(path, tmp_path)

    assert len(findings) == 1
    assert findings[0].label == "complete_webhook_url"
    assert findings[0].as_dict() == {
        "severity": "fail",
        "label": "complete_webhook_url",
        "path": "sample.py",
        "line": 1,
    }
    assert "secret-value" not in str(findings[0].as_dict())
    assert ROOT.exists()


def test_audit_ignores_regex_pattern_and_env_assignment(tmp_path: Path) -> None:
    from scripts.audit_security_boundaries import scan_file

    path = tmp_path / "sample.py"
    path.write_text(
        "\n".join(
            [
                r"pattern = r'https://open\\.feishu\\.cn/open-apis/bot/v2/hook/[^\"\\']+'",
                'WEBHOOK = "${FEISHU_WEBHOOK:-}"',
            ]
        ),
        encoding="utf-8",
    )

    assert scan_file(path, tmp_path) == []


def test_audit_detects_real_order_api(tmp_path: Path) -> None:
    from scripts.audit_security_boundaries import scan_file

    path = tmp_path / "trade.py"
    path.write_text("exchange.create_order(symbol, 'limit', 'buy', 1, 2)\n", encoding="utf-8")

    findings = scan_file(path, tmp_path)

    assert len(findings) == 1
    assert findings[0].label == "ccxt_create_order"
