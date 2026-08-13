# V1.1 每用户独立 CRYPTO 模拟撮合（Phase 1–4）

## 范围

- **Phase 1**：单用户 CLI · JSON 隔离
- **Phase 2**：批处理 Job · execution 视图 · 计划任务
- **Phase 3**：PG 009 双写 · positions/pending API · 监测页 Tab
- **Phase 4**：Shadow 对比 · 切流开关 · ledger 双轨

**不涉及** OS/定式/真实下单。

## 全局模式 · `FENGJI_PAPER_MODE`

| 值 | 行为 |
|----|------|
| `shadow` | **默认** · UI/API auto 仍 scoped · Job 写 shadow 对比 + ledger |
| `scoped_shared` | 仅 scoped 投影（回滚/旧行为） |
| `per_user_execution` | 切流 · auto 默认 execution |

显式覆盖 UI：`FENGJI_PAPER_ACCOUNT_MODE=scoped|execution`

## Shadow 对比

Job 每轮成功后（shadow 模式）：

- 文件：`runtime/paper_users/_shadow/{safe_user_id}.json`
- PG ledger：`shadow_compare` · `shadow_execution_snapshot`
- 指标：equity_gap · open_count_gap · fill/stop/bad_audits

```powershell
python scripts/report_paper_shadow_comparison.py
python scripts/report_paper_shadow_comparison.py --user-id USER --json
```

## API

- `GET /api/v1/monitor/paper-account?paper_mode=auto|scoped|execution`
- `GET /api/v1/monitor/paper-account/shadow`（standard/pro）
- `GET /api/v1/monitor/paper-account/positions|pending`

## 切流 / 回滚

```powershell
# Shadow 观察（默认）
$env:FENGJI_PAPER_MODE = "shadow"

# 正式切流
$env:FENGJI_PAPER_MODE = "per_user_execution"

# 回滚 scoped
$env:FENGJI_PAPER_MODE = "scoped_shared"
```

Shadow 期「我的模拟」Tab 仅预览，**不覆盖** PG scoped 主账户快照。

## 本机计划任务（2026-06-16）

```powershell
powershell -File scripts/install_user_paper_execution_task.ps1
# FengJiUserPaperExecutionJob · 1min · runtime/logs/user_paper_execution_job.log
# Job 内按 plan 限频：standard 60s / pro 30s
```

## 远端 deploy（2026-06-16）

```powershell
powershell -File scripts/sync_deploy_fengji_api.ps1 -SyncWeb -RunMigration -RestartApi -Verify
# manifest 118 + web · migration 009 (head) · E2E 5/5
```

## 验证

```powershell
python -m pytest tests/test_paper_execution_shadow.py tests/test_user_paper_execution_paths.py tests/test_user_paper_execution_job.py tests/test_monitor_paper_account.py tests/test_paper_user_execution_pg.py -q
# 26 passed
```
