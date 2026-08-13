# W17-demo 登录/订阅/付款演示流验收报告

日期：2026-06-05

范围：

- `web/login.html`
- `web/pricing.html`
- `web/payment.html`
- `web/community.html`
- `web/js/app.js`
- `web/js/config.js`
- `web/assets/qr/qq-group.jpg`
- `web/assets/qr/wechat-pay.png`

## 1. 结论

W17-demo 登录/订阅/付款演示流 API/DOM/静态级验收通过。

本轮不接入真实支付、不接入正式账户系统、不写任何密钥。权限演示仍以 `localStorage.fj-plan` 为唯一来源，URL `?plan=` 不授予权限。

浏览器截图级验收仍待 Chrome/Playwright 可用后补。

## 2. 页面职责

### 2.1 登录/注册

`web/login.html`：

- 登录：本地写入 `localStorage.fj-user`。
- 注册：要求确认密码，注册后调用 `FengJiApp.setSubscriptionPlan("free")`，开启免费 7 天试用。
- 免费试用只含定式 01-03。
- 标准/专业订阅必须从订阅页进入付款页，不在登录页混入订阅档位。

### 2.2 定价页

`web/pricing.html`：

- 从 `web/js/config.js` 的 `PRICING_TIERS` 渲染三档。
- 免费档入口：`login.html?mode=register&intent=free`。
- 标准档入口：`payment.html?pay=standard`。
- 专业档入口：`payment.html?pay=pro`。

### 2.3 付款页

`web/payment.html`：

- 只支持 `pay=standard` 与 `pay=pro`。
- 未登录时跳转到 `login.html?mode=login&return=payment.html?...`。
- 标准档付款确认后写入 `fj-plan=standard`，落地 `monitor.html`。
- 专业档付款确认后写入 `fj-plan=pro`，落地 `backtest.html`。
- 专业档禁止降级到标准档。
- 无效付款链接返回订阅页。

### 2.4 交流群页

`web/community.html`：

- 只展示 QQ 群二维码。
- 不展示微信收款码。
- 不承载 `?pay=` 付款流程。

## 3. 安全与权限

已复核：

- 权限唯一来源：`localStorage.fj-plan`。
- `FengJiApp.stripPlanQueryFromUrl()` 会剥离 URL `?plan=`。
- `loginUrlWithReturn()` 只允许本项目白名单页面作为 return，不允许外部 URL。
- `community.html?pay=*` 不再作为付款入口。
- 支付密钥、Token、服务器密码、真实支付回调均未写入页面。

验证输出：

```text
STRIP_PLAN true /backtest.html?symbol=PVC#x
PAY_PLAN_STANDARD standard
PAY_PLAN_INVALID true
CONFIRM_STANDARD true standard monitor.html
CONFIRM_PRO true pro backtest.html
BLOCK_DOWNGRADE blocked_downgrade backtest.html
LOGIN_RETURN_SAFE true
LOGIN_RETURN_LOCAL login.html?mode=login&return=payment.html%3Fpay%3Dpro
```

## 4. 页面与资源 Smoke

资源存在：

```text
web/assets/qr/qq-group.jpg
web/assets/qr/wechat-pay.png
```

前端脚本解析：

```text
web/login.html:INLINE_OK=1
web/pricing.html:INLINE_OK=1
web/payment.html:INLINE_OK=1
web/community.html:INLINE_OK=1
web/js/app.js:SCRIPT_OK
web/js/config.js:SCRIPT_OK
```

本地 HTTP smoke：

```text
HTTP_OK 200 /login.html text/html
HTTP_OK 200 /login.html?mode=register&intent=free text/html
HTTP_OK 200 /pricing.html text/html
HTTP_OK 200 /payment.html?pay=standard text/html
HTTP_OK 200 /payment.html?pay=pro text/html
HTTP_OK 200 /community.html text/html
HTTP_OK 200 /backtest.html?plan=pro text/html
HTTP_OK 200 /monitor.html?plan=standard text/html
```

## 5. 已知限制

1. 这是演示级 Auth/订阅流，不是正式生产鉴权。
2. 没有真实微信支付回调、订单号、订阅到期时间、发票、退款、风控审计。
3. 没有服务端 JWT、用户表、支付表、订阅状态表。
4. 浏览器截图级和真实点击级验收仍待 Chrome/Playwright。
5. 当前 `fj-plan` 存在浏览器本地，可被用户自行修改；正式生产必须由服务端订阅状态控制。

## 6. 下一步

进入 W22/W23/W24 PG/API/CLI 对账：

- 扩展 W14 的 `PG_API_CONSISTENCY_OK=6/6` 到至少 10 组。
- 对账回测指标、收益曲线、最大回撤、信号强弱、桶详情、同桶样本、CSV 导出。
- 统计仅用于展示和筛选，不反向修改峰极OS、阵营转换、DS01-DS09 或风控参数。
