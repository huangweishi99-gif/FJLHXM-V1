# 本地一键使用指南 — 无需配置服务器

## 一条命令启动

```powershell
Set-Location "C:\Users\guangwan\Documents\New project"
powershell -ExecutionPolicy Bypass -File scripts\start_fengji_local.ps1
```

**前提**：本机已安装并运行 **Docker Desktop**（用于 PostgreSQL）。

脚本会自动：

1. 启动 `docker compose` 中的 PostgreSQL  
2. 生成 `runtime/secrets/fengji_local.env`（JWT + 管理 Token，已 gitignore）  
3. 执行 `alembic upgrade head`（到 007）  
4. 启动 API，并打印可点击的本地地址  

## 常用页面

| 页面 | 地址 |
|------|------|
| 首页 | http://127.0.0.1:8000/web/index.html |
| 登录/注册 | http://127.0.0.1:8000/web/login.html |
| 模拟监测 | http://127.0.0.1:8000/web/monitor.html |
| 管理后台 | http://127.0.0.1:8000/web/admin.html |

## 管理后台 Token

启动时在终端会打印 **管理 Token**。也可打开：

`runtime/secrets/fengji_local.env` → `FENGJI_ADMIN_TOKEN=...`

在 http://127.0.0.1:8000/web/admin.html 粘贴即可。

## 仅初始化（不启动 API）

```powershell
powershell -ExecutionPolicy Bypass -File scripts\start_fengji_local.ps1 -SetupOnly
```

## 与远端服务器的关系

- **本地**：用本脚本，**不需要** SSH、不需要配置国内服务器。  
- **远端**：仍见 `docs/W17_PROD_API_REMOTE_DEPLOY_2026-06-08.md`（需运维或他人协助）。

## 边界

- 本地密钥仅用于开发，勿用于生产  
- 未修改峰极OS / 定式 / 模拟盘逻辑  
