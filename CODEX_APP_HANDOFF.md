# Codex App 一键接手（峰极OS总工程）

更新时间：**2026-07-07**  
Git `main`：**`2b04e8c`**（已与 `origin/main` 同步，含 Phase 2 D0–D7）

项目路径：

```text
C:\Users\guangwan\Documents\New project
```

远程仓库：`https://github.com/huangweishi99-gif/FJLHXM-V1.git`

---

## 0. 给 Codex 的第一句话（可复制进新会话）

```text
你是峰极OS总工程助手。项目路径 C:\Users\guangwan\Documents\New project。
请先只读：CODEX_APP_HANDOFF.md → PROJECT_CONTEXT.md → AGENTS.md → TODO.md → CHANGELOG.md。
Phase 2（D0–D7）已完成；勿整包 git stash pop；勿改峰极线/阵营/九大定式核心逻辑；勿写入密钥。
接手后运行「第一节 接手后 60 秒检查」中的命令，再向用户汇报。
```

---

## 1. 接手后 60 秒检查（必须先跑）

```powershell
Set-Location "C:\Users\guangwan\Documents\New project"
git status -sb
git log -3 --oneline
python scripts\verify_phase2_closeout.py
```

期望：`PHASE2_CLOSEOUT_OK`；`main` 与 `origin/main` 一致（或仅含用户本地 data WIP）。

可选全量桶验收：

```powershell
powershell -File scripts\verify_project_buckets.ps1
python -m pytest tests\test_os_engine.py tests\test_ds01.py tests\test_pending_orders.py -q
```

---

## 2. 项目是什么

| 维度 | 说明 |
|------|------|
| 名称 | 峰极OS总工程 / FengJi OS / 峰极总定式 |
| 范围 | 最高宪法 · 阵营转换 · **DS01–DS09** · 雷达 · 挂单器 · 国内期货/A股/海外 crypto 模拟盘 · 回测 · Web API |
| 权威代码 | `packages/fengji_core/fengji_core/`（`src/quant` 为兼容 re-export） |
| 当前阶段 | **方案 B Phase 2 已完成**；下一步见 `TODO.md`「总工程 TODO」 |

**硬约束（违反即停）：**

1. 所有定式在峰极OS最高宪法之下；峰/极/峰极线/阵营来自 OS 硬化结构，**禁止**用 raw high/low 替代。
2. **禁止**删除未知文件、整包 `git stash pop`、`git reset --hard`、批量回滚。
3. **禁止**把 API Key、Token、密码、完整 webhook 写入代码/文档/聊天。
4. 模拟盘 **禁止** 改成真实下单；实盘须人工确认。
5. 旧聊天不可见时只信 **仓库 Markdown + 可复现命令**，不得编造进度。

---

## 3. 必读文档（按顺序）

| 序 | 文件 | 用途 |
|----|------|------|
| 1 | **本文件** `CODEX_APP_HANDOFF.md` | 一键入口 |
| 2 | `PROJECT_CONTEXT.md` | 最新进度摘要 |
| 3 | `AGENTS.md` | AI 工作规则 |
| 4 | `TODO.md` | 待办与风险 |
| 5 | `CHANGELOG.md` | 变更历史 |
| 6 | `docs/PHASE2_CLOSEOUT.md` | Phase 2 签收 |
| 7 | `峰极OS_最高宪法.md` | 策略宪法 |
| 8 | `峰极OS_九大定式规则总纲.md` | 九大定式 |
| 9 | `峰极OS_阵营转换判断.md` | 阵营 |
| 10 | `峰极OS_挂单器与模拟实盘说明.md` | 挂单/模拟盘 |
| 11 | `峰极OS_服务器与部署说明.md` | 部署（地址脱敏） |
| 12 | `峰极OS_数据与回测说明.md` | 数据资产 |
| 13 | `docs/MARKET_COVERAGE_BOUNDARIES.md` | A股 60m / 期货日夜盘 |
| 14 | `docs/RADAR_REFRESH_SCHEDULE.md` | 雷达/泵频率 |
| 15 | `docs/PENDING_ORDER_CANCEL_RULES.md` | 同品种挂单撤销 |

规则冲突时：**先向用户指出冲突**，不要自行选一个版本。

---

## 4. Phase 2 已完成清单（D0–D7）

| 日序 | 要点 | 验收 |
|------|------|------|
| D0 | PR #12 `os_engine`/radar merge + 海内外部署 | hash 比对 |
| D1 | OS 账本增量（国内 LC / 海外 BTC） | `verify_os_state_*` |
| D2 | PR #13 pending plan/apply 锁优化 | `test_pending_orders` |
| D3 | PR #15 W18 watchlist | `verify_w18_watchlist_api.py` |
| D4 | 定式案例回归 + 飞书中文名 `domestic_display` | `verify_d4_pattern_cases.py` |
| D5 | 天勤仅环境变量 `require_tq_credentials` | `verify_d5_data_pending_policy.py` |
| D6 | A股 H1≥500 门槛 · 期货夜盘表 | `verify_d6_market_coverage_boundaries.py` |
| D7 | stash 边界审计 · Phase2 收口 | `verify_phase2_closeout.py` |

详情：`docs/PLAN_B_PHASE2_PROGRESS.md` · `docs/PLAN_B_PHASE2_COMPLETE.md`

---

## 5. 目录地图（改代码前先找这里）

```text
packages/fengji_core/fengji_core/   # 权威：os_engine, ds01–ds09, market_coverage, symbol_names
src/                                # 雷达、挂单、回测入口（fengji_total_radar, pending monitors）
data_manager_futures.py             # 国内期货天勤数据泵（根目录）
data_manager.py                     # 海外 crypto 数据泵
services/api/                       # FastAPI + PG（W17 等）
scripts/                            # 部署、验收、watchdog（见各 *manifest.txt）
tests/                              # pytest
docs/                               # 规格、验收、Phase 收口
runtime/                            # 本地运行态（雷达/挂单/模拟盘状态，不入库大数据）
data/                               # 本地行情缓存（大量 untracked，勿误提交）
```

**关键脚本：**

| 场景 | 命令 |
|------|------|
| 国内同步核心 | `powershell -File scripts\sync_deploy_domestic.ps1` |
| 国内 data_manager 仅 sync | `powershell -File scripts\deploy_domestic_futures_pending_lock.ps1 -DataManagerOnly` |
| 海外核心 hash | `python scripts\compare_overseas_core_hashes.py` |
| 国内健康 | `powershell -File scripts\verify_domestic_health.ps1` |
| 天勤环境变量检查 | `powershell -File scripts\check_domestic_tq_env.ps1` |

---

## 6. 服务器与运行态（须实时 SSH 复查）

| 环境 | SSH 别名（本机配置） | 项目根 | 说明 |
|------|---------------------|--------|------|
| 国内期货/A股模拟 | `domestic-quant` | `C:/Users/Administrator/quant_futures` | 天勤 `TQ_PHONE`/`TQ_PASS` 仅环境变量 |
| 海外 crypto | `overseas-quant` | `/home/ubuntu/quant_crypto` | radar 900s · pending 5s |

**不得以旧日志判断当前是否在跑**；接手后应查进程、心跳、日志时间戳。

国内 data_manager：`scripts/check_domestic_status.ps1`（或 SSH 跑同名脚本）  
海外：`scripts/watchdog_overseas.sh` · `scripts/check_overseas_runtime_status.ps1`

---

## 7. stash 与本地脏数据

| 项 | 策略 |
|----|------|
| `stash@{0}: b04-wip-all` | **411 文件**；**禁止** `git stash pop` / `git stash apply` |
| `data/` 大量 CSV | 多为 untracked/modified；**不要**整批 commit |
| `FJLHXM-UI.pen` | 在 stash 内，Web UI 独立轨道 |
| 单文件取用 | `git checkout 'stash@{0}' -- path/to/file` |

见 `docs/STASH_BOUNDARY_AUDIT.md` · `scripts/fengji_stash_residual_manifest.txt`

---

## 8. 已知限制（接手后勿误判为 bug）

1. **A股 60m**：约 100/239 仅 ~128 根；H1&lt;500 时回测自动 **跳过 DS07/DS08**（`market_coverage`）。
2. **国内 Python 3.10**：不能 `pip install -e fengji_core`；用 `PYTHONPATH=src;packages/fengji_core`。
3. **LC DS09**：历史窗口可能 `locks=0`、0 笔成交，属行情结果见 `docs/LC_DS09_ACCEPTANCE.md`。
4. **Cursor 终端** 访问 GitHub 可能偶发 443 reset；用户本机 PowerShell push 已成功。

---

## 9. 当前最高优先级（Phase 2 之后）

见 `TODO.md`「2026-05-27 总工程 TODO」，摘要：

1. 固化交接文档（本文件 + `PROJECT_CONTEXT` 保持更新）。
2. **实时巡检** 国内/海外 data_manager、radar、pending（时间敏感）。
3. **九大定式** 逐一定式复核（DS01–DS08 测试/沙盒/雷达一致性）。
4. A股板块回测归档；补齐 60m 长历史或维持 DS01–DS06 临时口径。
5. 本地 WIP：`src/market_data_store.py` 的 `import_futures_local`（5m 导入）**未提交**，需单独 PR。

---

## 10. 修改代码后的义务

1. 说明：改哪些文件、为什么、如何验证、风险。
2. 更新 `CHANGELOG.md` + `TODO.md`（涉及规则时同步 `PROJECT_CONTEXT.md`）。
3. 跑相关 pytest；部署国内时 **只 sync 相关文件** 并重启对应进程。
4. **不要** 未经用户要求执行 `git commit` / `git push`。

---

## 11. 接手汇报模板（Codex 输出给用户）

```markdown
## Codex 接手报告

- 读取：CODEX_APP_HANDOFF.md + PROJECT_CONTEXT + AGENTS + TODO
- Git：分支 main @ <hash>；与 origin 关系：<一致|ahead N>
- verify_phase2_closeout：<OK|FAIL>
- stash@{0}：存在，未 pop
- 国内/海外运行态：<已 SSH 检查|待用户授权检查>
- 建议下一步：<1–3 条来自 TODO 最高优先级>
```

---

## 12. 相关历史交接（归档，非首选）

- `HANDOFF_CURSOR_CODEX_2026-06-08.md`（2026-06-08 BNB/15m 修复上下文）
- `HANDOFF_CURSOR_CODEX_2026-06-05.md`

**以本文件 + `PROJECT_CONTEXT.md` 日期更新者为准。**
