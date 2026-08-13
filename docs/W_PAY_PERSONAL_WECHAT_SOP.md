# 个人微信收款码 · 订阅运营 SOP

状态：**ACTIVE**（2026-06-16）  
定价：**标准 ¥99/月 · 专业 ¥299/月**（与 `web/js/config.js` 一致）  
支付形态：**个人静态收款码**，**不接**微信支付商户号。

---

## 1. 能力边界

| 能做 | 不能做 |
|------|--------|
| 展示固定微信收款码 + 应付金额 | 微信自动回调、自动对账 |
| 用户付款后点「我已完成付款」开通 | 无人值守自动收费 |
| `subscription_orders` 审计（含金额 metadata） | 防「未付先点确认」的强校验 |
| Admin 只读查看最近订单 | 自动退款 |

**运营模式**：用户自助扫码 + 自助确认；运营侧在微信零钱/账单里**人工核对**备注与金额。

---

## 2. 生产环境配置（国内 API）

`runtime/secrets/fengji_api.env`：

```env
FENGJI_ALLOW_MANUAL_SUBSCRIPTION_CONFIRM=1
# 不要配置 FENGJI_PAYMENT_WEBHOOK_SECRET（避免误切 webhook 模式）
FENGJI_SUBSCRIPTION_PERIOD_DAYS=30
```

验证：

```powershell
curl http://127.0.0.1:8000/api/v1/subscriptions/payment-config
# confirm_button_mode=manual_confirm
# channel_mode=personal_wechat_qr
# pricing.standard.amount_yuan=99
```

---

## 3. 用户流程

1. 注册/登录 → `pricing.html` 选档  
2. `payment.html?pay=standard|pro`  
3. 看 **应付金额 ¥99/月 或 ¥299/月**  
4. 微信扫 `assets/qr/wechat-pay.png`  
5. **备注必填**：`登录账号 · 标准` 或 `登录账号 · 专业`（页面有提示）  
6. 点 **「我已完成付款」** → JWT 刷新 → 进监测/回测  

---

## 4. 运营核对（建议每次开通前抽查）

1. 打开微信收款记录，找对应金额（99 或 299）  
2. 核对备注是否含该用户登录账号 + 档位  
3. 若用户已点确认但找不到到账 → Admin 看 `subscription_orders` · 联系用户补付或人工处理  

Admin：`web/admin.html` + `FENGJI_ADMIN_TOKEN` → 最近订阅订单。

---

## 5. 异常处理

| 情况 | 处理 |
|------|------|
| 付错金额 | 不自动改 plan；人工沟通补差或退款后重开 |
| 付错档位 | Admin 记录；必要时 DB 调整 `plan_id`（须人工） |
| 未付先点确认 | 信任制 MVP；可改为「仅 Admin 开通」模式（待立项） |
| 专业降标准 | 系统 **禁止**（API 400） |

---

## 6. 与自动收费的关系

若未来接入微信商户 Native 支付：

- 新增商户下单/回调路由  
- 关闭 `FENGJI_ALLOW_MANUAL_SUBSCRIPTION_CONFIRM`  
- 保留本 SOP 作历史参考  

当前裁定：**不做商户号，维持本 SOP。**

---

## 7. 相关代码

- 定价：`services/subscription_plan_catalog.py` · `web/js/config.js`  
- 支付配置：`GET /api/v1/subscriptions/payment-config`  
- 开通：`POST /api/v1/subscriptions/manual-confirm` → channel=`personal_wechat_qr`  
- 页面：`web/payment.html`
