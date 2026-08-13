# W17-prod Subscription MVP — 2026-06-08

## 范围

对齐 `FJLHXM-V1.md` Phase 4 / W17-prod：**订阅状态入库**，从 `localStorage.fj-plan` 演示升级到服务端 `auth_users.plan_id` + 审计表。未接真实微信/Stripe SDK。

## 已实现

### 数据库（migration 007）

- 表 `subscription_orders`：`user_id`、`plan_id`、`channel`、`status`、`external_ref`、`metadata_json`
- `auth_users.plan_id` / `plan_expires_at` 在开通时更新（默认 30 天，`FENGJI_SUBSCRIPTION_PERIOD_DAYS` 可配）

### API

| 路由 | 说明 |
|------|------|
| `POST /api/v1/subscriptions/manual-confirm` | JWT 用户扫码后自确认；须 `FENGJI_ALLOW_MANUAL_SUBSCRIPTION_CONFIRM=1` |
| `POST /api/v1/subscriptions/redeem` | 兑换码；`FENGJI_SUBSCRIPTION_REDEEM_CODES=standard:CODE,pro:CODE` |
| `POST /api/v1/webhooks/subscription` | 支付回调占位；HMAC `X-FengJi-Signature` + `FENGJI_PAYMENT_WEBHOOK_SECRET` |

### Web

- `payment.html`「我已完成付款」→ 已登录时优先调 `manual-confirm`，刷新 JWT + `fj-plan`
- 无 token 或 manual 未启用时仍回退演示 `localStorage`（与 W17-demo 兼容）
- 新增 `FengJiApp.redeemSubscriptionCode(code)` 供后续定价页/内测入口使用

## 部署

```powershell
alembic upgrade head   # 应到 007 (head)
# 本地开发可设：
# FENGJI_ALLOW_MANUAL_SUBSCRIPTION_CONFIRM=1
# FENGJI_SUBSCRIPTION_REDEEM_CODES=standard:DEMO-STD,pro:DEMO-PRO
```

## 验证

```powershell
python -m pytest tests\test_subscription_api.py tests\test_auth_api_routes.py -q
node --check web\js\app.js
```

## 仍待

- 真实微信/支付宝回调字段映射与对账任务 `subscription_reconcile`
- Admin 人工审核付款备注
- 远端生产部署 + Playwright 付款流 smoke

## 边界

- 未修改峰极OS / DS / 风控 / `paper_state`
- 密钥与兑换码仅放环境变量，不入库
