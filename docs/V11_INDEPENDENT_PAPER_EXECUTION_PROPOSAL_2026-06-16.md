# V1.1 完整独立信号撮合立项

状态：`PHASE1 IMPLEMENTED`（2026-06-16，用户确认 CRYPTO+JSON）  
类型：**运行产品化 / Web 监测层** — **不涉及**峰极 OS、阵营转换、DS01–DS09 定式逻辑、真实交易所下单

## 1. 背景

V1.1 已交付 **scoped 共享运行态投影**（`scoped_shared_v1_1`）：

| 能力 | 现状 | 模块 |
|------|------|------|
| 共享 radar→挂单→paper | 国内/海外各 **1 套** 运行态 | `fengji_total_radar.py` · `fengji_pending_orders.py` · `*_pending_order_monitor.py` |
| Web 监测展示 | 读共享 `paper_state` | `monitor_domestic.py` · `monitor_overseas.py` |
| 每用户 paper 账户 | PG `paper_accounts` + ledger；**按自选过滤**共享持仓 | `monitor_paper_account.py` · migration `008` |
| 用户 watchlist | PG `paper_watchlist` + runtime 只读 preview | `watchlist_runtime.py` · `paper_watchlist.py` |

**缺口**：用户 A 与用户 B 看到的是同一套 domestic/overseas 模拟持仓的 **子集投影**，并非各自独立的 radar→挂单→成交→止损链路。  
用户若只观察 RB、另一用户只观察 AG，二者仍共享同一笔 RB 开仓的权益与 seen_entries 去重。

## 2. 目标与非目标

### 2.1 目标

1. **每用户独立 paper 执行**：用户 watchlist 内的品种，走独立的 pending→fill→stop→ledger 闭环。
2. **策略口径不变**：仍调用现有 `fengji_total_radar` / `fengji_pending_orders` / `runtime_stop_updater`；不复制定式/OS 逻辑。
3. **可审计、可回滚**：共享运行态保留为 **reference**；独立账户可 shadow 对比后再切流。
4. **与订阅档位对齐**：免费/标准/专业在 **品种数、刷新频率、WS** 上已有 Feature Gate；独立撮合须复用同一 `plan_id` 边界。

### 2.2 非目标（红线）

- 不向交易所、天勤、券商发真实单。
- 不修改峰极 OS、阵营转换、九大定式、挂单器核心规则。
- 不用 `signal_tier` 反向改 radar 筛选或风控。
- 不静默删除旧共享 `paper_state` / 模拟持仓（须备份 + 用户确认）。

## 3. 现状架构（共享运行态）

```
数据泵 → CSV/OS state
         ↓
fengji_total_radar (全品种 whitelist)
         ↓
fengji_pending_orders → pending_orders.json/csv
         ↓
*_pending_order_monitor → paper_state.json (单文件, state_lock)
         ↓
push_paper_state → 国内 API → monitor.html / paper-account scoped 投影
```

**watchlist runtime**（W18）停在 **只读 preview**：`build_watchlist_signal_preview()` 复用 `chart_bundle`，**不写** paper_state。

## 4. 目标架构（每用户独立）

```
PG paper_watchlist (per user, status=pending_runtime|paused)
         ↓
paper_execution_job (按 user 批 / 按 plan 限频)
  ├─ radar_subset(symbols=user_watchlist)
  ├─ pending_orders_user(user_id)
  └─ paper_monitor_user(user_id) → paper_state_user
         ↓
PG paper_accounts + paper_account_ledger (已有)
+ 新表/新文件: user pending / open / fills
         ↓
API GET /monitor/paper-account · /paper-positions · ledger
monitor.html: 「我的模拟」vs「平台参考」（可选）
```

### 4.1 存储选型（推荐）

| 层 | 推荐 | 理由 |
|----|------|------|
| 账户汇总 | PG `paper_accounts`（已有） | 已 migration 008 |
| 流水 | PG `paper_account_ledger`（已有） | 审计 |
| 挂单/持仓/去重状态 | **Phase 1** JSON `runtime/paper_users/{user_id}/` + **Phase 3** PG 表 | 与现有 monitor 脚本同构，先文件后 PG |
| OS state | **继续共享** `runtime/fengji_os_state` | OS 硬化与品种无关；按 symbol 读 snapshot，不 per-user 复制 OS |

**原则**：OS/雷达 **按 symbol 算一次**；paper 执行 **按 user 隔离**。

### 4.2 建议新增 PG 表（Phase 3，可选提前设计）

```text
paper_user_pending_orders   (user_id, order_id, symbol, strategy_id, status, ...)
paper_user_open_positions   (user_id, position_key, symbol, side, entry_*, current_stop, ...)
```

Migration `009_paper_user_execution`；与 `008` 外键通过 `user_id` 关联。

## 5. 与现有模块的复用边界

| 模块 | 复用方式 |
|------|----------|
| `fengji_total_radar.py` | 增加 `--symbols` 过滤（已有参数）；job 传入 user watchlist |
| `fengji_pending_orders.py` | 输出到 user 目录；`monitor-state`  per user |
| `fengji_futures_pending_order_monitor.py` / crypto 版 | 封装 `PaperMonitorConfig(paper_state_path=..., orders_file=...)` |
| `runtime_stop_updater.refresh_position_stop` | **必须**每轮 refresh；与回测 `update_dsXX_stop` 对齐 |
| `state_lock.file_lock` | 每 user 一个 state 文件，锁路径=该文件 |
| `fill_supervision` / `audit_paper_fills` | 扩展支持 `paper_users/` 目录审计 |

## 6. 分阶段实施计划（批准后开始编码）

### Phase 0 — 立项 ✅（本轮）

- [x] 本文件 + 架构边界
- [x] 用户确认 Phase 1：**CRYPTO + JSON** · standard/pro only · 共享运行态保留

### Phase 1 — 执行引擎骨架 ✅（2026-06-16）

1. **`services/paper_execution/`** — `UserPaperPaths` · watchlist/plan gate · runner
2. **`scripts/run_user_paper_radar_once.py`** — radar + pending
3. **`scripts/run_user_paper_monitor_once.py`** — monitor `--once`
4. **测试**：`tests/test_user_paper_execution_paths.py` **9 passed**

**路径**：`runtime/paper_users/{safe_user_id}/crypto/`（paper_state / pending / radar 隔离）

**CLI 示例**：

```powershell
python scripts/run_user_paper_radar_once.py --user-id USER --plan-id standard --symbols BTCUSDT,ETHUSDT
python scripts/run_user_paper_monitor_once.py --user-id USER --plan-id standard
```

**交付物**：CLI 可对 standard/pro 用户跑通 radar→pending→monitor；Web 仍读 scoped 投影（Shadow 默认）。

### Phase 2 — 批处理 Job + execution 视图 ✅（2026-06-16）

1. **`scripts/run_user_paper_execution_job.py`** — 扫描 CRYPTO `pending_runtime` · `_execution_job_state.json` 限频
2. **`monitor_paper_account.py`** — `paper_mode=execution|scoped|auto` · `per_user_execution_v1_2`
3. **计划任务** — `install_user_paper_execution_task.ps1` → `FengJiUserPaperExecutionJob`（1min tick，内层 standard 60s / pro 30s）
4. **文档** — `docs/V11_USER_PAPER_EXECUTION.md`
5. **测试** — **17 passed**（paths 9 + job 3 + monitor 5）

**Shadow 默认**：UI/API 仍 `scoped`；`?paper_mode=execution` 或 `FENGJI_PAPER_ACCOUNT_MODE=execution` 可预览独立账户。

### Phase 3 — PG 持久化 + API ✅（2026-06-16）

1. Migration `009_paper_user_execution` — 本地 `alembic upgrade head` ✅
2. 双写：JSON state + PG positions/pending（`paper_user_execution.py` · `sync_pg.py`）
3. API：
   - `GET /api/v1/monitor/paper-account/positions`
   - `GET /api/v1/monitor/paper-account/pending`
   - PG 优先，JSON 回退
4. **Web**：`monitor.html`「平台参考 | 我的模拟」Tab · `localStorage fj-paper-view` · 明细面板

**交付物**：刷新监测页见 per-user 持仓/挂单；Shadow 默认仍 scoped。

**测试**：paths 9 + job 3 + monitor 5 + pg 3 = **20 passed**

**待运维**：~~远端 deploy + migration 008→009~~ ✅ 2026-06-16

### Phase 4 — Shadow 对比 + 切流 ✅（2026-06-16）

1. **`FENGJI_PAPER_MODE`**：`shadow`（默认）| `scoped_shared` | `per_user_execution`
2. Job 成功后写 `runtime/paper_users/_shadow/{user}.json` + PG ledger 双轨事件
3. **指标**：equity_gap · open_count_gap · fill/stop/bad_audits 代理计数
4. **API**：`GET /api/v1/monitor/paper-account/shadow`
5. **切流**：`FENGJI_PAPER_MODE=per_user_execution`；回滚 `scoped_shared`
6. **Web**：监测页 Shadow 提示条；execution 预览不覆盖 scoped 主账户（shadow 期）

**测试**：累计 **26 passed**

## 7. 风险与缓解

| 风险 | 缓解 |
|------|------|
| 计算量 × 用户数 | 仅 scan watchlist 品种；job 批处理 + plan 限频；crypto 与 futures 分 job |
| 与共享运行态 drift | Shadow 期对比报告；OS state 仍共享，drift 主要来自 fill 时点 |
| seen_entries / setup_key 去重隔离 | 每 user 独立 monitor_state |
| 国内/海外规则混用 | `market_group` 分 `domestic_futures` / `overseas_crypto` 两账户或两 ledger 命名空间 |
| 旧用户无 watchlist | 回退 scoped 投影或引导添加自选 |
| 权益/保证金口径 | 独立 initial_cash；期货 multiplier/手续费仍读现有常量，不 per-user 改规则 |

## 8. 批准门禁

请用户确认后进入 Phase 1 编码：

| # | 决策项 | 建议默认 |
|---|--------|----------|
| 1 | Phase 1 先做 **CRYPTO only** 还是 **四市场** | **CRYPTO only** ✅ 已确认 |
| 2 | 存储 Phase 1 用 **JSON** 还是直接 **PG 009** | **JSON 先行** ✅ 已确认 |
| 3 | Shadow 期 UI 默认展示 | **scoped 投影** ✅ 已确认 |
| 4 | 免费档是否启用独立撮合 | **否** ✅ 已确认 |
| 5 | 共享运行态是否长期保留 | **是** ✅ 已确认 |

~~回复示例：`批准 Phase 1 CRYPTO+JSON`~~ → **已批准 2026-06-16**

## 9. 验证基线

| 阶段 | 命令 |
|------|------|
| Phase 1 | `python -m pytest tests/test_user_paper_execution_paths.py -q` |
| Phase 1 | 单用户 CLI：`run_user_paper_radar_once.py --user-id test --dry-run` |
| Phase 2 | `verify_v11_monitor_e2e.py` 增加 `paper-account` per-user 断言 |
| Phase 3 | `tests/test_paper_user_execution_pg.py` + monitor 扩展 · **20 passed** ✅ |
| Phase 4 | `tests/test_paper_execution_shadow.py` · **26 passed** ✅ |
| 回归 | `test_pending_orders` · `test_futures_pending_orders` · `test_fill_supervision` |

## 10. 文档与索引

| 文档 | 用途 |
|------|------|
| `峰极OS_挂单器与模拟实盘说明.md` | 共享运行态 SOP |
| `docs/PAPER_STATE_SYNC.md` | Web 推送共享 state |
| `docs/W18_*` | watchlist runtime 边界 |
| `services/monitor_paper_account.py` | 当前 scoped 投影实现 |
| `migrations/versions/008_paper_accounts.py` | 已有账户表 |

---

**下一步**：用户确认 §8 门禁 → 启动 Phase 1 编码（`services/paper_execution/` + CLI + 测试）。
