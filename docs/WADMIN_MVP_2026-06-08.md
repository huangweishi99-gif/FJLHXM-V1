# WAdmin MVP（本地）— 2026-06-08 / 第二段 2026-06-09

## 范围

对齐 `FJLHXM-V1.md` **P1-WAdmin** 第一步：只读运行概览，**无需配置远端服务器**。

## 已实现

### API

- `GET /api/v1/admin/overview`  
- 鉴权：`Authorization: Bearer <FENGJI_ADMIN_TOKEN>`（与 `start_fengji_local.ps1` 自动生成）

返回字段：

| 字段 | 说明 |
|------|------|
| `service` | API 健康（由路由层注入） |
| `auth_users` | 注册用户总数 |
| `auth_users_recent` | 最近 20 位用户（**不含** `password_hash`） |
| `subscription_orders_total` / `subscription_orders_recent` | 订阅订单统计与最近 10 条 |
| `custom_instrument_requests_total` | 自选请求数 |
| `backtest_jobs` | 回测任务按状态计数 |
| `monitor_ws` | WS 遥测：`active_total`、`lifetime`（含 `snapshots_sent` / `heartbeats_sent` / `deltas_sent`）、`recent_events` |

### Web

- `web/admin.html` — 粘贴 Token 后查看概览
- 统计卡：API 状态、用户/订单/自选/回测、WS 连接与快照/心跳/增量计数
- 表格：最近注册用户、最近订阅订单、监测 WS 最近事件
- WS 连接数使用 `monitor_ws.active_total`（与 W16-WS telemetry 对齐）

### 模块

- `services/admin_overview.py` — `_user_admin_view()`、`build_admin_overview()`

## 验证

```powershell
python -m pytest tests/test_admin_overview.py tests/test_admin_api.py -q
node --check web/js/app.js
```

本地：先 `scripts/start_fengji_local.ps1`，再打开 `http://127.0.0.1:8000/web/admin.html`（粘贴 `FENGJI_ADMIN_TOKEN`）。

## 仍待 WAdmin

- 品种上下架、任务重跑、运行态 SSH 巡检聚合、审计日志检索

## 边界

- 只读；不写 `paper_state`、不触发挂单
- 管理 Token 仅存 `sessionStorage`（`fj-admin-token`），与 JWT 用户会话分离
