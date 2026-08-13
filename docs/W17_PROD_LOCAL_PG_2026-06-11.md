# W17 生产化：国内服务器本地 PostgreSQL（替代 15432 反向隧道）

更新时间：2026-06-11

## 背景

P1 验收使用 **本机 Docker PG + SSH 反向隧道 15432**，属临时方案。P2 目标是在 `domestic-quant` 安装 **127.0.0.1:5432** 本地 PostgreSQL，API `DATABASE_URL` 指向本机 PG，可停止 `start_pg_reverse_tunnel.ps1`。

## 一键脚本

```powershell
Set-Location "C:\Users\guangwan\Documents\New project"

# 可选：预下载安装包（服务器 TLS 受限时必需）
curl.exe -L --tlsv1.2 -o runtime\secrets\postgresql-16.6-1-windows-x64.exe `
  "https://get.enterprisedb.com/postgresql/postgresql-16.6-1-windows-x64.exe"

powershell -ExecutionPolicy Bypass -File scripts\bootstrap_domestic_w17_p2_local_pg.ps1
```

## 步骤说明

| 步骤 | 脚本 | 说明 |
|------|------|------|
| 1 | 本地 `docker pg_dump` | 可选，种子 context/auth 数据 |
| 2 | `sync_deploy_fengji_api.ps1` | 同步 API + remote 脚本 |
| 2b | scp 安装包 | 若 `runtime/secrets/postgresql-16.6-1-windows-x64.exe` 存在 |
| 3 | scp dump | 上传到服务器 `runtime/secrets/` |
| 4 | `setup_domestic_postgresql.ps1 -Install` | 服务器静默安装 + 建库 |
| 5 | `patch_fengji_api_env_from_pg_secret.ps1` | **只改 DATABASE_URL**，不轮换 JWT |
| 6 | migration + restart API | `sync_deploy ... -RunMigration -RestartApi` |
| 7 | `w17_remote_acceptance.py` | 必需 7/7 |

## 服务器侧脚本

- `scripts/remote/setup_domestic_postgresql.ps1` — 安装/建用户/可选 pg_restore
- `scripts/remote/patch_fengji_api_env.ps1` — 单行 patch DATABASE_URL
- `scripts/remote/patch_fengji_api_env_from_pg_secret.ps1` — 从 `fengji_pg_password.txt` 拼 URL
- `scripts/remote/seed_fengji_pg_password.ps1` — 写入应用库密码（不入库）

密码文件均在 `runtime/secrets/`（服务器本地，勿提交）。

## 完成状态（2026-06-11）

- PG 16 服务 @5432；API `DATABASE_URL` 指向本机 PG
- Alembic **007 (head)**；W17 **7/7 + 可选 5/5**
- 本机 **15432 隧道已停止**（`scripts/stop_pg_reverse_tunnel.ps1`）

## 2026-06-11 尝试记录

| 轮次 | 结果 | 说明 |
|------|------|------|
| 1 | 失败 → 已回滚 | 服务器 EDB HTTPS 下载 TLS 失败；误 patch 5432 后已回滚 15432，W17 **7/7** |
| 2 | 失败（未 patch） | scp 324MB 安装包成功；静默安装 **exit 1**（`temp_check_comspec.bat` 写入 Temp 失败）；fail-fast 生效，仍走 15432 隧道 |

**安装器 exit 1 可能原因**：服务器 `%TEMP%` 权限/磁盘/杀软拦截。建议在服务器 **RDP 以管理员** 手动运行 `runtime\secrets\postgresql-16.6-1-windows-x64.exe`，或修复 Temp 目录权限后重跑：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\bootstrap_domestic_w17_p2_local_pg.ps1 -SkipDump
```

安装完成后只需执行 patch + migration（若已装 PG 可 `-SkipInstall`）：

```powershell
ssh domestic-quant "powershell -File ...\setup_domestic_postgresql.ps1 -SkipCreateUser"
# 或 SkipInstall 若 PG 已存在
```

## 回滚（若 P2 中途失败）

```powershell
ssh domestic-quant "powershell -NoProfile -ExecutionPolicy Bypass -File C:\Users\Administrator\quant_futures\scripts\remote\patch_fengji_api_env.ps1 -DatabaseUrl postgresql+psycopg://fengji:fengji_dev@127.0.0.1:15432/fengji"
ssh domestic-quant "powershell -NoProfile -ExecutionPolicy Bypass -File C:\Users\Administrator\quant_futures\scripts\restart_fengji_api.ps1"
```

确保本机 `start_pg_reverse_tunnel.ps1` 仍在运行。

## 仍待

- [ ] 完成 P2 安装（需安装包 scp 或人工在服务器装 PG 16）
- [ ] 可选：配置 `FENGJI_ADMIN_TOKEN` 使 admin_overview 通过
- [ ] 公网 HTTPS / 域名 / CORS
