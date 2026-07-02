from __future__ import annotations

from pathlib import Path

from fengji_feishu_notify import fill_notify_key, send_feishu_once, should_send_feishu


def test_should_send_feishu_only_once(tmp_path: Path) -> None:
    claims = tmp_path / "claims"
    key = fill_notify_key("order-123")
    assert should_send_feishu(claims, key) is True
    assert should_send_feishu(claims, key) is False


def test_send_feishu_once_dedup(tmp_path: Path) -> None:
    claims = tmp_path / "claims"
    sent: list[str] = []

    def _fake_send(_webhook: str, text: str) -> None:
        sent.append(text)

    key = fill_notify_key("o1")
    assert send_feishu_once(claims, key, "http://example", "first", _fake_send) is True
    assert send_feishu_once(claims, key, "http://example", "second", _fake_send) is False
    assert sent == ["first"]
