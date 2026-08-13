# 订阅收款路线裁定 · 2026-06-16

## 用户裁定

**选项 3**：继续 **个人微信静态收款码 + manual_confirm**，**暂不**接虎皮椒/爱发电/免签监听；待办理 **个体工商户** 后，再接入 **微信支付官方 Native 扫码 + 服务器 notify**。

## 当前阶段（Phase：个人码内测）

| 项 | 值 |
|----|-----|
| 定价 | 标准 **¥99/月** · 专业 **¥299/月** |
| 收款 | `web/assets/qr/wechat-pay.png` 个人静态码 |
| 开通 | 用户点「我已完成付款」→ `POST /api/v1/subscriptions/manual-confirm` |
| 生产 env | `FENGJI_ALLOW_MANUAL_SUBSCRIPTION_CONFIRM=1` · **勿配** `FENGJI_PAYMENT_WEBHOOK_SECRET` |
| 审计 | channel=`personal_wechat_qr` · metadata 含 `amount_yuan` |
| 运营 SOP | `docs/W_PAY_PERSONAL_WECHAT_SOP.md` |

**不做**：虎皮椒 API · 爱发电外链 · 手机监听免签 · 微信商户 Native（此阶段）。

## 下一阶段触发条件（个体户 + 官方微信）

全部满足后再开 **W-Pay-Merchant** Wave：

1. **个体工商户**营业执照（或公司主体）
2. 网站 **ICP 备案**（主体一致）
3. **微信支付商户号** + **Native 支付**权限
4. （建议）已认证 **服务号 AppID** 绑定商户号
5. 生产 HTTPS 回调域就绪

## 下一阶段技术清单（届时再做，不在此阶段开发）

1. `POST /api/v1/subscriptions/wechat/native-order` — 统一下单 → `code_url`
2. `POST /api/v1/webhooks/wechat-pay/notify` — 官方验签 + 幂等
3. 关闭 `FENGJI_ALLOW_MANUAL_SUBSCRIPTION_CONFIRM`
4. `payment.html` — 动态二维码 + 轮询订单状态
5. 到期降级 Job · Admin 订单/对账（W-Pay-2）
6. 复用现有 `activate_user_subscription()` · `subscription_orders`

参考：`docs/V11_INDEPENDENT_PAPER_EXECUTION.md` 不涉及支付；支付立项见 `FJLHXM-V1.md` §4.6。

## 市面方案（已评估、暂不采用）

| 方案 | 结论 |
|------|------|
| 虎皮椒等聚合 | 过渡可用；用户选择 **不采用** |
| 爱发电 | 零开发；用户选择 **不采用** |
| 免签监听 | 风险高；**禁止**作峰极主链路 |
| 官方 Native | **目标态**，等个体户 |

## 验证（当前阶段）

```powershell
python scripts/stress_subscription_manual_confirm.py --auto-server --standard 20 --pro 20
powershell -File scripts/verify_remote_personal_wechat_pay.ps1
# REMOTE_PERSONAL_WECHAT_PAY_VERIFY ok=True
```
