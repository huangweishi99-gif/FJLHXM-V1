# W17-prod 远端 API 部署 — 2026-06-08

## 范围

对齐 `FJLHXM-V1.md` **W17-prod**：在国内量化服务器（SSH 别名 `domestic-quant`）增量部署 FengJi Web API（Auth/JWT、订阅、监测 WS、静态 Web），**不影响** data_manager / radar / pending monitor。

## 前置条件

- 国内服务器已有 `C:\Users\Administrator\quant_futures` 与 `src/`、`packages/fengji_core/`（现有定式部署）
- 本机 SSH `BatchMode` 可连 `domestic-quant`
- 服务器已安装 Python 3.12+ 与 API 依赖（`services/api/requirements.txt`、`services/db/requirements.txt`）
- PostgreSQL 可用（本机 docker compose 或服务器 PG）；`DATABASE_URL` 写入**服务器私密 env**，不入库

## 1. 服务器私密配置（必做）

在服务器创建（**勿提交 git**）：

`C:\Users\Administrator\quant_futures\runtime\secrets\fengji_api.env`

模板见 `scripts/remote_fengji_api_env.example.ps1`。至少：

```ini
DATABASE_URL=postgresql+psycopg://fengji:***@127.0.0.1:5432/fengji
FENGJI_JWT_SECRET=<随机 32+ 字符>
```

生产环境 **禁止** `FENGJI_AUTH_ALLOW_DEV_SECRET=1`。

## 2. 同步部署（本机 PowerShell）

```powershell
Set-Location "C:\Users\guangwan\Documents\New project"

# 仅 API + migrations + 脚本（默认不同步 web/）
powershell -ExecutionPolicy Bypass -File scripts\sync_deploy_fengji_api.ps1

# 含前端静态资源
powershell -ExecutionPolicy Bypass -File scripts\sync_deploy_fengji_api.ps1 -SyncWeb

# 配置好 DATABASE_URL 后执行 migration
powershell -ExecutionPolicy Bypass -File scripts\sync_deploy_fengji_api.ps1 -RunMigration

# 重启 API 进程
powershell -ExecutionPolicy Bypass -File scripts\sync_deploy_fengji_api.ps1 -RestartApi

# 安装登录自启计划任务（可选）
powershell -ExecutionPolicy Bypass -File scripts\sync_deploy_fengji_api.ps1 -InstallTask

# 远端 health + alembic current
powershell -ExecutionPolicy Bypass -File scripts\sync_deploy_fengji_api.ps1 -Verify
```

清单文件：`scripts/fengji_api_deploy_manifest.txt`（**不含**密钥、不含 `data/`）。

## 3. 服务器手动重启

```powershell
powershell -ExecutionPolicy Bypass -File C:\Users\Administrator\quant_futures\scripts\restart_fengji_api.ps1
powershell -ExecutionPolicy Bypass -File C:\Users\Administrator\quant_futures\scripts\verify_fengji_api_health.ps1
```

默认监听 `127.0.0.1:8000`；对外暴露须自行配置反向代理/TLS，本文不写域名与证书。

## 4. 部署后 Smoke / 验收清单

**结构化验收（推荐）：**

```powershell
python scripts/w17_remote_acceptance.py --ssh-tunnel domestic-quant --local-port 8040
powershell -ExecutionPolicy Bypass -File scripts/run_w17_remote_acceptance.ps1 -SshTunnel domestic-quant
```

清单说明：`docs/W17_PROD_REMOTE_ACCEPTANCE_CHECKLIST_2026-06-09.md`  
JSON 报告：`runtime/web_validation/w17_remote_acceptance.json`

**兼容旧命令：**

```powershell
python scripts/smoke_w17_post_deploy.py --ssh-tunnel domestic-quant --local-port 8040
```

期望 `"ok": true`，必需项 7/7 通过；WS 首帧 `monitor.snapshot.v1` / heartbeat / delta。

## 5. Migration 目标

```text
alembic upgrade head  →  007 (head)
```

含 `auth_users`、`subscription_orders` 及 W11/W18 相关表。

## 6. 边界

- 不同步、不重启 `data_manager_futures` / radar / pending monitor
- 不写 `paper_state`、不触发挂单、不真实下单
- 未修改峰极OS / DS01-09 / 风控

## 7. 仍待

- 服务器 PG 安装/托管方案（若尚未部署 docker compose）
- 公网 HTTPS + 域名 + CORS 生产值
- 真实微信/Stripe 支付回调与 Admin 审核
- 付款流 Playwright smoke（对已部署 URL）
