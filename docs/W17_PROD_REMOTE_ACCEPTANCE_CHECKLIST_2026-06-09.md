# W17-prod 远端验收清单 — 2026-06-09

## 范围

对齐 `FJLHXM-V1.md` **P1-W17-prod**：在国内量化服务器部署 FengJi Web API 后，用**结构化清单**验收 health / Auth / WS / Web 静态页 / Admin / Feature Gate，**不写 paper_state、不触发挂单**。

## 一键执行

### A. 本机预检（无需服务器）

```powershell
Set-Location "C:\Users\guangwan\Documents\New project"
python scripts/w17_remote_acceptance.py --preflight-only
# 或
powershell -ExecutionPolicy Bypass -File scripts/run_w17_remote_acceptance.ps1 -PreflightOnly
```

验证：部署 manifest、deploy 脚本存在；可选 SSH `domestic-quant` 连通（失败不阻塞预检通过）。

### B. 本机模拟远端（auto-server，需 Docker PG）

```powershell
docker compose up -d
alembic upgrade head
python scripts/w17_remote_acceptance.py --auto-server
# 或（读取 runtime/secrets/fengji_local.env 的 Admin Token）
powershell -ExecutionPolicy Bypass -File scripts/run_w17_remote_acceptance.ps1 -AutoServer
```

报告：`runtime/web_validation/w17_remote_acceptance.json`

### C. 远端 SSH 隧道（运维已部署 API）

```powershell
# 一键 bootstrap（PG 隧道 + env + migrate + 计划任务 + 验收）
powershell -ExecutionPolicy Bypass -File scripts/bootstrap_domestic_w17_p1.ps1

# 或分步：
powershell -ExecutionPolicy Bypass -File scripts/start_pg_reverse_tunnel.ps1   # 保持运行
powershell -ExecutionPolicy Bypass -File scripts/sync_deploy_fengji_api.ps1 -SyncWeb -RunMigration -InstallTask -RestartApi -Verify

# 本机验收
python scripts/w17_remote_acceptance.py --ssh-tunnel domestic-quant --local-port 8040
powershell -ExecutionPolicy Bypass -File scripts/run_w17_remote_acceptance.ps1 -SshTunnel domestic-quant
```

### D. 直连 URL

```powershell
python scripts/w17_remote_acceptance.py --base-url https://your-api.example.com
powershell -ExecutionPolicy Bypass -File scripts/run_w17_remote_acceptance.ps1 -BaseUrl "http://127.0.0.1:8000"
```

## 验收项

| ID | 项 | 必需 | 说明 |
|----|-----|------|------|
| `health` | GET `/api/v1/health` | ✅ | `status=ok` |
| `auth_flow` | 注册/登录/me/refresh | ✅ | 需 PG + migration 006+ |
| `ws_monitor` | JWT pro WS 首帧 | ✅ | `monitor.snapshot.v1` / heartbeat / delta |
| `admin_unauth` | Admin 无 Token | ✅ | HTTP 401 |
| `web_index` | `/web/index.html` | ✅* | *需 `-SyncWeb` 部署前端 |
| `web_strategies` | `/web/strategies.html` | ✅* | 含 W15 动画脚本 |
| `web_login` | `/web/login.html` | ✅* | |
| `ws_stats` | WS 遥测 | 可选 | |
| `monitor_domestic` | 国内持仓只读 | 可选 | |
| `admin_overview` | Admin 概览 | 可选 | 需 `FENGJI_ADMIN_TOKEN` |
| `feature_gate_total` | 免费档拒 TOTAL | 可选 | Feature Gate |
| `subscription_manual_confirm` | manual-confirm | 可选 | 仅 `FENGJI_ALLOW_MANUAL_SUBSCRIPTION_CONFIRM=1` |

**通过标准**：所有 **必需** 项 `ok=true`。

## 服务器前置（运维）

1. 创建 `runtime/secrets/fengji_api.env`（模板 `scripts/remote_fengji_api_env.example.ps1`）
2. `DATABASE_URL` + `FENGJI_JWT_SECRET`（生产禁止 dev secret）
3. `alembic upgrade head` → **007**
4. 可选：`FENGJI_ADMIN_TOKEN`、`FENGJI_ALLOW_MANUAL_SUBSCRIPTION_CONFIRM`（本地/dev）

详见 `docs/W17_PROD_API_REMOTE_DEPLOY_2026-06-08.md`。

## 验证（开发机）

```powershell
python -m pytest tests/test_w17_remote_acceptance.py -q
python scripts/w17_remote_acceptance.py --preflight-only
python scripts/w17_remote_acceptance.py --auto-server --port 8043
```

## 实跑记录（2026-06-09）

| 步骤 | 结果 |
|------|------|
| SSH `domestic-quant` | 连通 |
| `sync_deploy_fengji_api.ps1 -SyncWeb` | **成功**（41 文件 + web/） |
| 远端 `services/api/main.py` | 存在 |
| 远端 `web/index.html` | 存在 |
| `w17_remote_acceptance --ssh-tunnel` | **失败** — `:8000` 无 API |

**阻塞**：`fengji_api.env` 未创建；远端无 PostgreSQL；API 未启动。

## 实跑记录（2026-06-10 · Wave 5 P1 · 解除阻塞）

| 步骤 | 结果 |
|------|------|
| `bootstrap_domestic_w17_p1.ps1` | PG 反向隧道 + env + migrate 007 + `FengJiApiServer` |
| 远端 `fengji_api.env` | **已创建**（服务器本地，密钥不入库） |
| Alembic | **007 (head)** |
| API 进程 | 计划任务 `FengJiApiServer` + `schtasks /Run` |
| `--ssh-tunnel domestic-quant --local-port 8040` | **通过** — 必需 **7/7**、可选 **4/5** |
| `ws_monitor` | **通过** — `monitor.snapshot.v1`（服务端 JWT + manual-confirm pro） |
| `admin_overview`（可选） | **401** — 未设 `FENGJI_ADMIN_TOKEN` |
| `pytest tests/test_w17_remote_acceptance.py -q` | **4 passed** |
| 报告 | `runtime/web_validation/w17_remote_acceptance.json` |

**结论**：W17 远端必需验收项 **全部通过**；PG 经本机 Docker 反向隧道为**临时方案**，生产须在 `domestic-quant` 安装 PostgreSQL。

**生产化仍待**：服务器本地 PG、HTTPS/域名/CORS、Admin Token（可选项）。

## 实跑记录（2026-06-11 · Wave 5 P1 · 复测，已 supersede）

| 步骤 | 结果 |
|------|------|
| `--preflight-only --preflight-ssh domestic-quant` | **通过**（manifest + deploy 脚本 + SSH 连通） |
| 远端 `Test-Path .../fengji_api.env` | **False**（仍未创建） |
| 远端 `GET :8000/api/v1/health` | **失败**（API 未监听） |
| `--auto-server --port 8043`（本机 Docker PG + migration 007） | **通过** — 必需 **7/7**、可选 **5/5** |
| `--ssh-tunnel domestic-quant --local-port 8040` | **失败** — `API not ready` |

**结论**：见 2026-06-10 记录（已解除）。

## 仍待 W17-prod

- 公网 HTTPS + 域名 + CORS 生产值
- 真实微信/Stripe 支付回调
- 对已部署 URL 的付款流 Playwright smoke
- 服务器本地 PostgreSQL（勿长期依赖 PG 反向隧道）

## 边界

- 验收脚本会创建临时 smoke 用户（`w17-smoke-*@test.local`）
- 不修改峰极OS / DS / 风控 / paper_state
