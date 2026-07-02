"""V1.1: read-only subscription payment channel config (no secrets exposed)."""
from __future__ import annotations

import os
from typing import Any

from db.subscriptions import parse_redeem_codes, subscription_period_days
from subscription_plan_catalog import pricing_catalog


def _env_enabled(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in {"1", "true", "yes"}


def build_subscription_payment_config() -> dict[str, Any]:
    manual_confirm = _env_enabled("FENGJI_ALLOW_MANUAL_SUBSCRIPTION_CONFIRM")
    payment_webhook = bool(os.getenv("FENGJI_PAYMENT_WEBHOOK_SECRET", "").strip())
    redeem_code = bool(parse_redeem_codes())

    if manual_confirm:
        primary_channel = "manual_confirm"
        confirm_button_mode = "manual_confirm"
    elif payment_webhook:
        primary_channel = "payment_webhook"
        confirm_button_mode = "webhook_pending"
    elif redeem_code:
        primary_channel = "redeem_code"
        confirm_button_mode = "redeem_only"
    else:
        primary_channel = "demo"
        confirm_button_mode = "demo_only"

    personal_wechat = manual_confirm and not payment_webhook

    messages = {
        "manual_confirm": (
            "请用微信扫收款码，按页面金额付款；备注填写登录账号与档位；"
            "付款后点击「我已完成付款」开通（个人收款码，无法自动到账通知）。"
        ),
        "webhook_pending": "扫码付款后请等待系统自动开通（通常数分钟内）；无需点击确认按钮。",
        "redeem_only": "当前仅支持兑换码开通，请返回订阅页或联系管理员。",
        "demo_only": "支付通道未配置：登录态下无法自动开通，请联系管理员或使用兑换码。",
    }

    return {
        "version": 1,
        "period_days": subscription_period_days(),
        "pricing": pricing_catalog(),
        "channel_mode": "personal_wechat_qr" if personal_wechat else primary_channel,
        "channels": {
            "manual_confirm": manual_confirm,
            "payment_webhook": payment_webhook,
            "redeem_code": redeem_code,
            "personal_wechat_qr": personal_wechat,
        },
        "primary_channel": primary_channel,
        "confirm_button_mode": confirm_button_mode,
        "message": messages[confirm_button_mode],
        "env_hints": {
            "manual_confirm": "FENGJI_ALLOW_MANUAL_SUBSCRIPTION_CONFIRM=1",
            "payment_webhook": "FENGJI_PAYMENT_WEBHOOK_SECRET",
            "redeem_code": "FENGJI_SUBSCRIPTION_REDEEM_CODES=standard:CODE,pro:CODE",
            "period_days": "FENGJI_SUBSCRIPTION_PERIOD_DAYS",
        },
    }
