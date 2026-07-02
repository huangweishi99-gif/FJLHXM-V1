from __future__ import annotations

from services.subscription_payment_config import build_subscription_payment_config


def test_payment_config_defaults_to_demo(monkeypatch) -> None:
    monkeypatch.delenv("FENGJI_ALLOW_MANUAL_SUBSCRIPTION_CONFIRM", raising=False)
    monkeypatch.delenv("FENGJI_PAYMENT_WEBHOOK_SECRET", raising=False)
    monkeypatch.delenv("FENGJI_SUBSCRIPTION_REDEEM_CODES", raising=False)

    cfg = build_subscription_payment_config()
    assert cfg["primary_channel"] == "demo"
    assert cfg["confirm_button_mode"] == "demo_only"
    assert cfg["channels"]["manual_confirm"] is False
    assert cfg["channels"]["payment_webhook"] is False
    assert cfg["channels"]["redeem_code"] is False
    assert "env_hints" in cfg
    assert "FENGJI_PAYMENT_WEBHOOK_SECRET" in cfg["env_hints"]["payment_webhook"]


def test_payment_config_manual_confirm_priority(monkeypatch) -> None:
    monkeypatch.setenv("FENGJI_ALLOW_MANUAL_SUBSCRIPTION_CONFIRM", "1")
    monkeypatch.setenv("FENGJI_PAYMENT_WEBHOOK_SECRET", "secret-not-exposed")
    monkeypatch.setenv("FENGJI_SUBSCRIPTION_REDEEM_CODES", "standard:ABC")

    cfg = build_subscription_payment_config()
    assert cfg["primary_channel"] == "manual_confirm"
    assert cfg["confirm_button_mode"] == "manual_confirm"
    assert cfg["channels"]["manual_confirm"] is True
    assert cfg["channels"]["payment_webhook"] is True


def test_payment_config_webhook_when_no_manual(monkeypatch) -> None:
    monkeypatch.delenv("FENGJI_ALLOW_MANUAL_SUBSCRIPTION_CONFIRM", raising=False)
    monkeypatch.setenv("FENGJI_PAYMENT_WEBHOOK_SECRET", "wh-secret")
    monkeypatch.delenv("FENGJI_SUBSCRIPTION_REDEEM_CODES", raising=False)

    cfg = build_subscription_payment_config()
    assert cfg["primary_channel"] == "payment_webhook"
    assert cfg["confirm_button_mode"] == "webhook_pending"
