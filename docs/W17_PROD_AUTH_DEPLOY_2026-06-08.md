# W17-prod Auth/JWT 本地部署说明

日期：2026-06-08

## 范围

- `POST /api/v1/auth/register|login|refresh`
- `GET /api/v1/auth/me`
- 监测 WS `access_token` JWT 鉴权（`pro` 档）
- **不写** `paper_state`、不触发挂单、不真实下单

## 1. 数据库 migration 006

```powershell
Set-Location "C:\Users\guangwan\Documents\New project"
docker compose up -d
# 等待 healthy 后：
python -m alembic upgrade head
python -m alembic current   # 期望 006 (head)
```

新建表：`auth_users`（account 唯一、password_hash、plan_id、plan_expires_at）。

## 2. JWT 密钥（必设，勿写入仓库）

生产环境必须设置环境变量，**禁止**依赖 `FENGJI_AUTH_ALLOW_DEV_SECRET`。

```powershell
# 本地开发可临时：
$env:FENGJI_JWT_SECRET = "<随机 32+ 字符>"
# 或仅开发兜底（勿用于生产）：
$env:FENGJI_AUTH_ALLOW_DEV_SECRET = "1"
```

参考模板：`services/api/env.example`（复制为本地私密 env，不要 commit）。

## 3. 启动 API

```powershell
pip install -r services/api/requirements.txt
pip install -r services/db/requirements.txt
$env:PYTHONPATH = "services;packages/fengji_core"
$env:FENGJI_AUTH_ALLOW_DEV_SECRET = "1"   # 本地 only
uvicorn main:app --app-dir services/api --host 127.0.0.1 --port 8000
```

## 4. Smoke 验收

**路由级（mock DB，无需 PG）：**

```powershell
python -m pytest tests/test_auth_api_routes.py tests/test_auth_api.py -q
```

**离线集成（TestClient + 真实 PG register）：**

```powershell
python scripts/smoke_w17_auth_ws.py --offline
```

**Auto-server（临时 uvicorn + 真实 WebSocket）：**

```powershell
python scripts/smoke_w17_auth_ws.py --auto-server --port 8031
```

**长期运行 API：**

```powershell
powershell -ExecutionPolicy Bypass -File scripts/run_fengji_api.ps1 -Port 8000
```

期望输出 `"ok": true`，WS 首帧为 `monitor.snapshot.v1` 或 `monitor.heartbeat.v1`。

## 5. Web 接入

- `login.html` 优先调 `/api/v1/auth/register|login`，成功写入 `fj-access-token` + `fj-auth`
- `monitorWebSocketUrl()` 有 token 时带 `access_token` query
- API 不可用时回退 localStorage 演示态

## 6. 仍待

- 服务器执行 `sync_deploy_fengji_api.ps1 -RunMigration -RestartApi -Verify`（见 **`docs/W17_PROD_API_REMOTE_DEPLOY_2026-06-08.md`**）
- Playwright 浏览器级 WS smoke（已完成，见 W16 报告）
- WS 频道拆分 / delta 消息
