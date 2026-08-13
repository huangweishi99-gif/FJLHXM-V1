# W00 工作树提交边界审计报告

日期：2026-06-05

范围：`C:\Users\guangwan\Documents\New project`

目的：在进入 Web/Pencil 9 屏验收和产品化收口前，先把当前脏工作树按风险分桶，避免把峰极OS最高宪法、阵营转换、DS01-DS09、服务器密钥、运行态日志、大数据文件混入后续提交或整理动作。

## 1. 结论

当前工作树非常脏，不适合直接整体提交、整体同步或整体清理。

必须先按下列分桶处理：

1. `CORE_STRATEGY_OS`：核心策略/OS/挂单/监控代码，必须单独审计、单独测试、单独提交。
2. `WEB_PG_API_DESIGN`：Web、Pencil、FastAPI、PG、回测页产品化，可作为下一阶段 P0 Web 验收主提交范围。
3. `SERVER_DEPLOY_SCRIPTS`：国内/海外服务器脚本，涉及运行态和敏感配置，必须单独审计后提交。
4. `DOCS_HANDOFF_RULES`：交接文档、Cursor/Codex 规则、路线图，可作为文档提交范围。
5. `DATA_RESULTS_ASSETS`：数据、结果、图片、运行态、大量 CSV，默认不提交，除非用户明确确认。
6. `OTHER_REVIEW`：脚本、工具、中文旧脚本、二维码、规则图片等，需要逐项判断，不允许随手混入。

## 2. 当前分桶统计

来自 `git status --short` 的只读分类结果：

| 分桶 | 数量 | 默认处理 |
|------|------|----------|
| CORE_STRATEGY_OS | 35 | 保护区；必须单独审计 |
| WEB_PG_API_DESIGN | 22 | 可进入 Web 产品化提交候选 |
| SERVER_DEPLOY_SCRIPTS | 30 | 单独审计；先脱敏 |
| DOCS_HANDOFF_RULES | 13 | 可进入文档提交候选 |
| DATA_RESULTS_ASSETS | 286 | 默认排除 |
| OTHER_REVIEW | 61 | 待人工/逐项裁定 |

## 3. 可优先提交候选

### 3.1 文档计划候选

本轮已确认是计划/交接更新，可单独提交：

- `FJLHXM-V1.md`
- `TODO.md`
- `CHANGELOG.md`
- `docs/W00_WORKTREE_BOUNDARY_AUDIT_2026-06-05.md`

说明：这组文件不修改策略逻辑，不影响运行态，可作为“W00 边界审计 + FJLHXM-V1 计划更新”提交。

### 3.2 Web/Pencil/PG 候选

后续 W08/W13/W14/W16 验收时可进入候选，但本报告不直接确认提交：

- `web/`
- `services/`
- `designs/`
- `FJLHXM-UI.pen`
- `docs/FJLHXM_UI_DESIGN_FREEZE.md`
- `scripts/build_fjlhxm_ui_pen.py`
- `scripts/finalize_fjlhxm_ui_pen.py`
- `scripts/smoke_domestic_paper_state_web.ps1`
- `scripts/smoke_pg_api_consistency.py`
- `scripts/sync_domestic_futures_1d_for_web.py`
- `docker-compose.yml`
- `alembic.ini`
- `migrations/`

进入提交前必须做：

- JS/HTML 静态检查。
- API smoke。
- 关键页面浏览器验收。
- 确认 `.pen` 与生成脚本一致。
- 确认没有把二维码、收款码、运行态截图、大数据误混入。

## 4. 必须保护的核心策略/OS 文件

以下文件当前有改动或新增，不能与 Web 文档整理混提：

- `packages/fengji_core/fengji_core/os_engine.py`
- `packages/fengji_core/fengji_core/ds07.py`
- `packages/fengji_core/fengji_core/ds09.py`
- `packages/fengji_core/fengji_core/data.py`
- `packages/fengji_core/fengji_core/os_state_store.py`
- `packages/fengji_core/fengji_core/context_snapshot.py`
- `packages/fengji_core/fengji_core/context_stats.py`
- `packages/fengji_core/fengji_core/runtime_stop_updater.py`
- `packages/fengji_core/fengji_core/state_lock.py`
- `packages/fengji_core/fengji_core/symbol_names.py`
- `src/fengji_total_radar.py`
- `src/fengji_pending_orders.py`
- `src/fengji_pending_order_monitor.py`
- `src/fengji_futures_pending_order_monitor.py`
- `src/fengji_radar_order_loop.py`
- `src/backtest_ds03.py`
- `src/backtest_ds07.py`
- `data_manager_futures.py`
- `remote_domestic_optimize/data_manager_futures.py`
- `tests/test_os_engine.py`
- `tests/test_pending_orders.py`
- `tests/test_futures_pending_orders.py`
- `tests/test_radar_ds04.py`
- `tests/test_radar_ds05.py`
- `tests/test_radar_ds07.py`
- `tests/test_fengji_total_radar_loader.py`
- `tests/test_rebuild_os_state_all_loader.py`
- `tests/test_runtime_stop_updater_loader.py`

处理规则：

- 不允许整体提交。
- 不允许和 Web/Pencil 验收提交混在一起。
- 每次提交前必须重新跑对应测试。
- 涉及 OS 连线、阵营、DS01-DS09 时，必须更新规则文档并生成沙盒图或案例说明。

## 5. 默认排除项

以下内容默认不进入提交：

- `data/`
- `runtime/`
- `results/`
- `archives/`
- `test-results/`
- `.pytest_cache/`
- `__pycache__/`
- `results/sandbox/*.png`
- 大量 A 股 CSV、期货/crypto 数据 CSV、回测结果、运行日志。

原因：

- 体积大。
- 多数是运行产物或行情数据。
- 容易污染提交历史。
- 可能包含交易状态、旧错误状态或本地路径。

如需提交数据样本，必须单独创建小样本 fixture，并在测试中说明用途。

## 6. 敏感信息扫描结果

本轮做了两级扫描：

1. 关键词扫描：覆盖 `token`、`webhook`、`secret`、`TQ_PASS`、`TQ_PHONE` 等，命中 213 处。多数是变量名、文档安全说明或测试占位，需要按上下文判断。
2. 高置信扫描：只识别疑似真实 `sk-...`、完整 webhook URL、私钥块、硬编码密码/secret 赋值。

高置信结果（首次扫描）：

- 发现疑似敏感信息，位置：`scripts/restart_domestic_futures_runtime.ps1` 第 39 行附近，需要人工检查并脱敏。

处理结果：

- 已将 `scripts/restart_domestic_futures_runtime.ps1` 第 39 行附近的具体 webhook 匹配改为通用模式 `FENGJI_FEISHU_WEBHOOK=https?://`。
- 该脚本仍保留“进程命令行是否暴露 webhook”的告警能力，但文件中不再保存具体 webhook URL。
- 复验结果：PowerShell 语法解析通过；当前变更候选文本文件高置信敏感扫描 `HIGH_CONFIDENCE_HIT_COUNT=0`。

安全要求：

- 不在文档、聊天、日志中显示具体内容。
- 该脚本在提交前必须确认是否仍含完整 webhook URL。
- 如确认为真实 webhook，应改为从本地私密配置或环境变量读取。

## 7. 建议提交/整理顺序

### 第 1 批：W00 文档边界提交

候选：

- `FJLHXM-V1.md`
- `TODO.md`
- `CHANGELOG.md`
- `docs/W00_WORKTREE_BOUNDARY_AUDIT_2026-06-05.md`

验证：

- 文档标题、版本、优先级检查。
- 不需要跑策略测试。

### 第 2 批：Web/Pencil 9 屏验收提交

候选：

- `web/`
- `services/`
- `designs/`
- `FJLHXM-UI.pen`
- `docs/FJLHXM_UI_DESIGN_FREEZE.md`
- Web/Pencil 生成与 smoke 脚本。

验证：

- JS 语法检查。
- HTML 内联脚本检查。
- API smoke。
- 浏览器截图/点击流。
- Pencil MCP 画布截图，若 MCP 不通则标记待确认。

### 第 3 批：PG/API/context 统计提交

候选：

- `packages/fengji_core/fengji_core/context_snapshot.py`
- `packages/fengji_core/fengji_core/context_stats.py`
- `scripts/batch_import_context_stats_to_pg.py`
- `scripts/calibrate_context_market_tiers.py`
- `services/`
- 相关测试。

验证：

- PG/API/CLI 抽样一致性。
- 统计结果只展示，不反改策略。

### 第 4 批：核心 OS/策略修复提交

候选：

- `os_engine.py`
- DS 定式文件。
- radar/pending/monitor 相关文件。
- 对应规则文档与测试。

验证：

- `python -m pytest tests\test_os_engine.py tests\test_fengji_total_radar_loader.py tests\test_rebuild_os_state_all_loader.py -q`
- 按影响范围补跑挂单/雷达/回测测试。
- 必要时生成沙盒图。

### 第 5 批：服务器脚本提交

候选：

- `scripts/restart_*`
- `scripts/sync_deploy_*`
- `scripts/watchdog_*`
- `scripts/verify_*`

验证：

- 先脱敏。
- 只读检查命令行不暴露 webhook/token/password。
- 远端 smoke 单独记录。

## 8. 下一步

执行 W08 之前，建议先完成：

1. 决定是否先提交第 1 批 W00 文档边界文件。
2. 开始 W08：逐屏验收 `FJLHXM-UI.pen` 与 Web 9 页面实现。
3. 服务器脚本进入提交前，仍需按 `SERVER_DEPLOY_SCRIPTS` 分桶单独复核，不与 Web/Pencil 提交混合。

## 9. 禁止事项

- 禁止 `git add .`。
- 禁止整体提交当前工作树。
- 禁止删除未知文件。
- 禁止把 `data/`、`runtime/`、`results/`、`archives/`、密钥配置或完整 webhook 混入提交。
- 禁止把 Web/Pencil 提交和峰极OS/九大定式核心逻辑提交混在一起。
- 禁止在未复核测试前同步核心策略到国内/海外服务器。
