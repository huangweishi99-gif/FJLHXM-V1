# W17-prod Feature Gate MVP — 2026-06-08

## 范围

对齐 `FJLHXM-V1.md` Phase 4 / W17-prod：**服务端 Feature Gate MVP**，与 W16-WS JWT 监测衔接。不实现支付回调、远端生产部署、Playwright。

## 已实现

### 服务端 (`services/feature_gate.py`)

- 档位与 `web/js/config.js` 对齐：`years`、`strategy_id`、watchlist 名额常量
- `effective_plan()`：有 JWT 时以 DB `plan_id` 为准；**无 JWT 时 gated 路由一律按 free**（不再信任 body/localStorage `plan_id`）
- `ensure_plan_active()` / `plan_expires_at`：免费试用与付费订阅到期后拒绝回测/自选/WS
- 门禁路由：
  - `POST /api/v1/backtests` — 登录用户校验订阅有效 + years/定式
  - `POST /api/v1/custom-instruments/request` — **须 JWT**；忽略 body 伪造 `plan_id`/`user_id`
  - `WS /api/v1/ws/monitor` — JWT 时以 DB 档位为准；订阅过期返回 `plan_expired`

### Web (`web/js/app.js`)

- `getSubscriptionPlan()`：JWT session `user.plan` 优先于 `localStorage.fj-plan`
- `isPlanActive()` / `planGateMessage()`：优先读 `/api/v1/auth/me` 的 `plan_expires_at`
- `refreshAuthSessionFromApi()` + `initShell()` 派发 `fj-auth-ready`
- `authHeaders()`：回测/自选提交带 `Authorization: Bearer`
- `monitorWebSocketUrl()`：有 token 时不传 `plan` query（服务端从 JWT 解析）

### 监测页 (`web/monitor.html`)

- 已登录用户等待 `fj-auth-ready` 后再建 WS，避免 plan 未同步即连

## 验证

```powershell
Set-Location "C:\Users\guangwan\Documents\New project"
python -m pytest tests\test_feature_gate.py tests\test_feature_gate_api.py tests\test_auth_api_routes.py -q
node --check web\js\app.js
```

## 仍待 W17-prod 后续

- 支付回调与 DB 订阅升降档（MVP 已有 redeem/manual/webhook 占位）
- 监测轮询延迟的服务端强制 ✅（2026-06-12，`monitor_polling_gate.py`）
- 远端 API + 真实 `FENGJI_JWT_SECRET`
- Playwright 浏览器级 WS / 回测 gate smoke

## 边界

- 未修改峰极OS / DS01-09 / 风控 / `paper_state`
- URL `?plan=` 仍被剥离，不参与鉴权
