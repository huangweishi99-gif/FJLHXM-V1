from __future__ import annotations

import argparse
from pathlib import Path

from fengji_feishu_notify import expected_close_notify_key, fill_notify_key, pending_notify_key, send_feishu_once, should_send_feishu, system_notify_key


def test_should_send_feishu_only_once(tmp_path: Path) -> None:
    claims = tmp_path / "claims"
    key = fill_notify_key("order-123")
    assert should_send_feishu(claims, key) is True
    assert should_send_feishu(claims, key) is False


def test_pending_and_expected_close_keys_distinct() -> None:
    assert pending_notify_key("o1") == "pending|o1"
    from fengji_feishu_notify import pending_semantic_notify_key, pending_setup_notify_key

    assert pending_setup_notify_key("SYM|DS09|LONG|x") == "pending_setup|SYM|DS09|LONG|x"
    assert (
        pending_semantic_notify_key(
            {
                "symbol": "TRUMPUSDT",
                "strategy_id": "DS09",
                "timeframe": "M15",
                "side": "long",
                "trigger_price": 1.686,
                "stop_price": 1.64,
            }
        )
        == "pending_semantic|TRUMPUSDT|DS09|M15|long|1.686|1.64"
    )
    assert expected_close_notify_key("o1") == "expected_close|o1"
    assert fill_notify_key("o1") == "fill|o1"


def test_send_feishu_once_dedup(tmp_path: Path) -> None:
    claims = tmp_path / "claims"
    sent: list[str] = []

    def _fake_send(_webhook: str, text: str) -> None:
        sent.append(text)

    key = fill_notify_key("o1")
    assert send_feishu_once(claims, key, "http://example", "first", _fake_send) is True
    assert send_feishu_once(claims, key, "http://example", "second", _fake_send) is False
    assert sent == ["first"]


def test_system_notify_key_and_default_claims_dir(tmp_path: Path) -> None:
    from fengji_feishu_notify import default_feishu_claims_dir

    assert system_notify_key("overseas_paper", "startup") == "system|overseas_paper|startup"
    assert default_feishu_claims_dir(tmp_path) == (tmp_path / "runtime" / "feishu_notify_claims").resolve()


def test_notify_new_pending_orders_dedupes_by_setup_key(tmp_path: Path, monkeypatch) -> None:
    from fengji_pending_order_monitor import notify_new_pending_orders

    sent: list[str] = []

    def _fake_send(_webhook: str, text: str) -> None:
        sent.append(text)

    monkeypatch.setattr("fengji_pending_order_monitor.send_msg", _fake_send)
    setup_key = "TRUMPUSDT|DS09|LONG|2026-06-29|lock=900|def=902|1.686"
    base = {
        "symbol": "TRUMPUSDT",
        "strategy_id": "DS09",
        "timeframe": "M15",
        "side": "long",
        "trigger_price": 1.686,
        "stop_price": 1.64,
        "current_price": 1.659,
        "distance_pct": 0.016,
        "status": "ACTIVE",
        "setup": "DS09 second attack after M15 defense extreme",
        "setup_key": setup_key,
        "os_camp": "D1=red,M15=red",
    }
    orders = [
        {**base, "order_id": "TRUMPUSDT-DS09-M15-long-aaaaaaaaaaaaaaaa"},
        {**base, "order_id": "TRUMPUSDT-DS09-M15-long-bbbbbbbbbbbbbbbb"},
    ]
    args = argparse.Namespace(
        feishu_webhook="http://example",
        notify_claims_dir=str(tmp_path / "claims"),
    )
    state: dict = {}
    notify_new_pending_orders(args, state, orders)
    notify_new_pending_orders(args, state, orders)
    assert len(sent) == 1
    assert setup_key in state["notified_pending_setup_keys"]
    assert state["notified_pending_semantic_keys"] == ["pending_semantic|TRUMPUSDT|DS09|M15|long|1.686|1.64"]


def test_notify_new_pending_orders_dedupes_by_semantic_key_across_setup_key_change(
    tmp_path: Path, monkeypatch
) -> None:
    from fengji_pending_order_monitor import notify_new_pending_orders

    sent: list[str] = []

    def _fake_send(_webhook: str, text: str) -> None:
        sent.append(text)

    monkeypatch.setattr("fengji_pending_order_monitor.send_msg", _fake_send)
    base = {
        "symbol": "TRUMPUSDT",
        "strategy_id": "DS09",
        "timeframe": "M15",
        "side": "long",
        "trigger_price": 1.686,
        "stop_price": 1.64,
        "current_price": 1.659,
        "distance_pct": 0.016,
        "status": "ACTIVE",
        "setup": "DS09 second attack after M15 defense extreme",
        "os_camp": "D1=red,M15=red",
    }
    orders = [
        {
            **base,
            "order_id": "TRUMPUSDT-DS09-M15-long-aaaaaaaaaaaaaaaa",
            "setup_key": "TRUMPUSDT|DS09|LONG|2026-06-29|attack=947|1.686",
        },
        {
            **base,
            "order_id": "TRUMPUSDT-DS09-M15-long-bbbbbbbbbbbbbbbb",
            "setup_key": "TRUMPUSDT|DS09|LONG|2026-06-29|lock=944|def=951|1.686",
        },
    ]
    args = argparse.Namespace(
        feishu_webhook="http://example",
        notify_claims_dir=str(tmp_path / "claims"),
    )
    state: dict = {}
    notify_new_pending_orders(args, state, orders)
    assert len(sent) == 1


def test_notify_new_pending_orders_bootstraps_semantic_from_legacy_order_ids(
    tmp_path: Path, monkeypatch
) -> None:
    from fengji_pending_order_monitor import notify_new_pending_orders

    sent: list[str] = []

    def _fake_send(_webhook: str, text: str) -> None:
        sent.append(text)

    monkeypatch.setattr("fengji_pending_order_monitor.send_msg", _fake_send)
    base = {
        "symbol": "TRUMPUSDT",
        "strategy_id": "DS09",
        "timeframe": "M15",
        "side": "long",
        "trigger_price": 1.686,
        "stop_price": 1.64,
        "current_price": 1.659,
        "distance_pct": 0.016,
        "status": "ACTIVE",
        "setup": "DS09 second attack after M15 defense extreme",
        "setup_key": "TRUMPUSDT|DS09|LONG|2026-06-29|lock=942|def=949|1.686",
        "os_camp": "D1=red,M15=red",
    }
    args = argparse.Namespace(
        feishu_webhook="http://example",
        notify_claims_dir=str(tmp_path / "claims"),
    )
    state = {
        "notified_pending_order_ids": [
            "TRUMPUSDT-DS09-M15-long-legacyaaaaaaaaaaaa",
        ],
    }
    notify_new_pending_orders(
        args,
        state,
        [{**base, "order_id": "TRUMPUSDT-DS09-M15-long-newbbbbbbbbbbbbbb"}],
    )
    assert sent == []
    assert state["notified_pending_semantic_keys"] == [
        "pending_semantic|TRUMPUSDT|DS09|M15|long|1.686|1.64"
    ]
