from __future__ import annotations

from subscription_payment_config import build_subscription_payment_config
from subscription_plan_catalog import plan_pricing, pricing_catalog


def test_plan_pricing_standard_and_pro() -> None:
    std = plan_pricing("standard")
    pro = plan_pricing("pro")
    assert std is not None and std["amount_yuan"] == 99
    assert pro is not None and pro["amount_yuan"] == 299
    assert pricing_catalog()["standard"]["display_with_period"] == "¥99/月"


def test_payment_config_includes_pricing_and_personal_wechat(monkeypatch) -> None:
    monkeypatch.setenv("FENGJI_ALLOW_MANUAL_SUBSCRIPTION_CONFIRM", "1")
    monkeypatch.delenv("FENGJI_PAYMENT_WEBHOOK_SECRET", raising=False)

    cfg = build_subscription_payment_config()
    assert cfg["pricing"]["pro"]["amount_yuan"] == 299
    assert cfg["channel_mode"] == "personal_wechat_qr"
    assert cfg["channels"]["personal_wechat_qr"] is True
    assert "个人收款码" in cfg["message"]
