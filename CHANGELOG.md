# CHANGELOG

## 2026-07-02（Phase 1 · PR #8 merged）

- PR #8 merged：chart_bundle · chart_line · context · phase2 manifest。
- 验收：`docs/POST_MERGE_ACCEPTANCE_PR8_20260702.md`。

## 2026-07-02（Phase 1 · PR #10 web）

- 分支 `pr/b2-web-phase1`：`web/` 全量 · feature_gate_api 无 PG mock 修复 · 静态页测试。
- manifest：`scripts/fengji_web_phase1_manifest.txt`。

## 2026-07-02（Phase 1 · PR #9 merged）

- 分支 `pr/b3-api-deploy-scripts`：`sync_deploy_fengji_api.ps1` · paper-state sync · W17 smoke/remote · phase3 manifest。
- 全量 `fengji_api_deploy_manifest.txt` 本地文件齐 · `test_fengji_api_phase3_manifest` 全绿。

## 2026-07-02（Phase 1 · PR #7 merged）

- PR #7 merged（`1a0bc86`）：services · migrations · auth tests · OpenAPI 38 paths。
- 验收：`docs/POST_MERGE_ACCEPTANCE_PR7_20260702.md`。

## 2026-07-02（Phase 1 · PR #8 chart）

- 分支 `pr/b2-chart-bundle-deps`：`chart_bundle` · `chart_line` · `symbol_names` · `context_*` · phase2 manifest。
- 期货 chart 黄金测试默认 skip（`FENGJI_CHART_FUTURES_GOLDEN=1` 时启用）。

## 2026-07-02（Phase 1 · services MVP）

### PR #7 准备 · services/API 分桶

- 分支 `pr/b2-services-api-phase1`：`services/` · `migrations/` · alembic · docker-compose · Phase1 manifest（67 文件）。
- 新增 `scripts/fengji_api_phase1_manifest.txt` · `tests/test_fengji_api_phase1_manifest.py` · `docs/PLAN_B_PHASE1_SERVICES_BUCKET.md`。
- 验证：pytest phase1 **24 passed** · OpenAPI **38 paths**。

## 2026-07-02（PR #6 merged）

### follow-up PR #6 合并 + Phase 0 签收

- PR #6 `pr/b1-followup-core-compat` merged（`c929b71`）：`STRATEGY_DISPLAY_NAMES` · `ds07` optional `df` · `test_core_post_merge_compat.py`。
- 合并后复验：pytest **38 passed** · OpenAPI **38 paths** · overseas fill audit **invalid_new=0**。
- Phase 0 完成文档：`docs/PLAN_B_PHASE0_COMPLETE.md`。
- HYPE #28：已 sync paper_state + promote 1d（07-01 close 更新为 63.533）· 仍 `STOP_PENDING_MONITOR_BAR` · 待 07-02 D1。

## 2026-07-02

### 方案 B Phase 0 · PR #1–#5 全部合并

- GitHub PR #1–#5 已 merge 到 `main`：fill_supervision（B1）、ops audit（#2）、OpenAPI Phase0（#3）、文档 handoff（#4）、Pencil B0-3 脚本（#5）。
- 合并后验收：`results/post_merge_acceptance_20260702/ACCEPTANCE.md`。
- 修复合并后 core 版本不一致：`constants.STRATEGY_DISPLAY_NAMES`；`ds07.make_ds07_signal` 增加可选 `df` 参数；新增 `tests/test_core_post_merge_compat.py`。
- follow-up 分支：`pr/b1-followup-core-compat`（待 merge）。
- 验证：pytest fill_supervision 相关 **33 passed**；`export_openapi_snapshot.py` **38 paths**；`run_overseas_fill_audit.ps1 -FailOnInvalid` **invalid_new=0** exit **0**。

## 2026-05-28

### 国内全链路重启与 LC DS09 签收（2026-05-28）

- 用户确认接受 LC `ds09_trades=0`（`locks=0`，引擎 `bad_trades=0`）；`docs/LC_DS09_ACCEPTANCE.md` 签收表已更新。
- `scripts/resolve_domestic_paper.ps1`：显式解析 `峰极总定式01-08国内期货A股模拟实盘.py`，修复 GBK/SSH 下 `*模拟实盘.py` 通配符匹配失败。
- `restart_domestic_futures_runtime.ps1`：数据泵 + 模拟盘 + 雷达 + 挂单；`restart_domestic_data_manager.ps1` 补 `PYTHONPATH`。
- `domestic_install_matplotlib.ps1`：国内沙盒图依赖安装。
- **cmd `PYTHONPATH`**：`set "PYTHONPATH=src;packages/fengji_core"`（分号在 cmd 中否则被当命令分隔符）。
- `fengji_radar_order_loop.py`：子进程 `fengji_total_radar.py` 继承 `packages/fengji_core`。

### LC 15m 加长回填与验收清单（2026-05-28 晚）

- `data_manager_futures.fetch_frame`：15m 请求 >8000 时按 12000→…→3000 试探，保留**最长且 `frame_looks_sane` 通过**的一档；1d 仅向下试探且不超过 `FUTURES_1D_LENGTH`。
- 国内 LC 回填结果：`15m=10000`（`data_length=10000`）、`1d=800`、`1h=2600`；12000/11000 的 15m 与 >800 的 1d 对 LC 常校验失败。
- `fengji_core/data.py`：`load_tq_futures_kline_csv`、`parse_tq_datetime_series`；`backtest_ds09.load_m15_frame` 优先天勤 CSV。
- 脚本：`backfill_lc_domestic.ps1`（默认 `M15Length=12000`、`D1Length=800`）、`repair_lc_15m_only.py`、`build_lc_bars_from_1h.py`（仅联调）、`run_lc_ds09_domestic.ps1`（修复 `-BuildFrom1h` 注入远程脚本）。
- 文档：新增 `docs/LC_DS09_ACCEPTANCE.md`。
- 复验：`verify_ds09_lc_session` / `debug_lc_ds09` → `m15_rows≈9911`，`ds09_trades=0`，`locks=0`，`bad_trades=0`。
- Git：`8780b1e`（LC 流水线脚本）、`ec1be47`（加长回填 + 验收清单）。

### 国内 LC DS09 夜盘 session 与沙盒（2026-05-28）

- `assign_session_date(futures=True)` 走 `assign_cn_futures_session_date`（21:00 归次日；天勤 LC 夜盘多为次日 01:00–06:00）。
- `scripts/verify_ds09_lc_session.py` / `run_lc_ds09_domestic.ps1`：国内 690 D1、298 授权 session；当前 15m 仅约 3000 根，窗口内无刺穿边界故 0 笔成交。
- 沙盒：`results/sandbox/lc_ds09/LC_DS09_session_overview.png`（LC 授权日示意）+ `ETH_DS09_trade*_reference.png`（成交标注参考）。

### DS09 九重天接入雷达与挂单器（第 3 步）

- 复述口径与 `docs/DS09_CALIBRATION.md` 一致：D1 已完成 OS 阵营 + 昨日阴阳线授权边界；M15 第一次刺穿只锁定；第一进攻峰 → 第一防守极 → 二次攻击入场；一日一结构。
- `fengji_total_radar.py`：新增 `add_ds09` / `replay_ds09_session`（有 15m 数据时运行）；输出 `PENDING`（防守极已成立待二次攻击）或 `TRIGGERED`。
- `fengji_core/ds09.py`：新增 `assign_session_date`（crypto 日历日 / 期货夜盘）；修复 `make_ds09_signal` 分阶段校验（记录进攻峰时不再要求极已存在）。
- `fengji_pending_orders.py`：默认挂单策略集加入 `DS09`。
- 测试：`tests/test_radar_ds09.py`；全量 `pytest` 62 passed。
- 已同步国外 `fengji_total_radar.py`、`ds09.py`、`fengji_pending_orders.py` 并执行一轮 radar `--once`。

### OS 增量验证（双端 + 本地）

- 新增 `scripts/verify_os_state_incremental.py`、`verify_os_state_overseas.sh`、`verify_os_state_domestic.ps1`。
- 国外 BTC：`processed_len=1835` 两轮雷达后不变；状态文件 `delta2=0`。
- 国内 LC：`processed_len=690` 两轮雷达后不变；`delta1=delta2=0`。
- 本地 IOUSDT 连跑两轮：`size_delta=0`，`incremental_ok=true`。
- DS03 沙盒：`results/sandbox/io_ds03_20260528/IOUSDT_DS03_long_20260526.png`（规则图示；2026-05-26 实盘 IO 日线无 fake_peak，与 `tests/test_ds03` 合成用例区分）。

### 方案 A 验收与运行态巡检

- 运行 `scripts/plan_a_verify.ps1`：**PASSED**（pytest 59 passed、DS05 `bad_trades=0`、ETH 九定式 smoke `bad_audits=0`）。
- 修正 `tests/test_radar_setup_keys.py`：DS03 雷达 `setup_key` 对齐新规（`watch|trigger=` / `{symbol}|DS03|{peak_key}`）。
- 新增 `scripts/check_domestic_runtime_remote.ps1`：本机 SSH 巡检国内 `domestic-quant`（数据泵、雷达循环、LC K 线、OS 状态目录）。
- 国外 `check_overseas_runtime_status.ps1`：data_manager / 雷达 / 挂单 / 模拟盘 / `fengji_os_state` 正常；`radar.json` 15:15 更新。
- 国内巡检：雷达与挂单 15:19 更新；`LC.csv` / `LCUSDT.csv` 15:13 更新；`runtime/fengji_os_state` 已有 LC 等状态文件。

### 海外模拟盘 BNBUSDT 空 CSV 修复

- `data_manager.py`：K 线 **原子写入**（`.tmp` + `replace`），避免同步中被读空文件。
- `src/峰极总定式01-08策略海外模拟实盘.py`（同步为 `overseas_paper_monitor.py`）：`safe_read_csv`、空文件明确报错、`accepted_trades` 空表不再触发 pandas `No columns to parse`。
- `packages/fengji_core/fengji_core/data.py`：新增 `read_csv_strict`。

### 收敛 `src/quant` 与 `packages/fengji_core` 双实现风险

- 确认 `packages/fengji_core/fengji_core` 作为峰极OS与 DS01-DS09 的核心权威源。
- 将 `src/quant/os_engine.py`、`src/quant/ds01.py`、`src/quant/ds03.py`、`src/quant/ds05.py`、`src/quant/ds07.py` 改为兼容层 re-export，避免后续只改一边导致策略分叉。
- 保留 `src/quant` 路径作为现有 CLI、回测脚本、雷达、挂单器和模拟盘的兼容导入入口。
- 验证结果：`quant.*` 导入 smoke 通过；`python -m pytest tests -q` 通过，59 passed（2026-05-28 复验）。

## 2026-05-27

### 固化峰极OS增量连线状态账本

- 更新 `packages/fengji_core/fengji_core/os_engine.py` 与 `src/quant/os_engine.py`：新增 OS 状态导出、恢复、`run_from_state` 增量运行能力；已确认的 raw nodes、hardened nodes、identity nodes、turn events、红蓝阵营和防守/进攻点可持久化为状态账本。
- 更新 `src/fengji_total_radar.py`：雷达默认使用 `runtime/fengji_os_state` 保存每个品种/周期的峰极OS状态；D1保留完整 `hardened_by_bar` 供 DS01/DS06 审计，H1只保存当前硬化峰极线和OS日志，避免大周期循环被历史快照拖慢。
- 更新 `src/quant/ds07.py` 与 `packages/fengji_core/fengji_core/ds07.py`：允许 H1 在不保存完整 `hardened_by_bar` 时仍输出 `hardened_count`，DS08 使用当前 `hardened_nodes` 作为最新骨架。
- 更新 `tests/test_os_engine.py`：新增增量状态与全量运行一致性测试，保证固化后追加K线不会改变既有峰极线和阵营结果。
- 本地验证：`py_compile` 通过；使用内置 Python 轻量脚本验证增量OS与全量OS的 raw nodes、identity nodes、hardened nodes、阵营结果一致。
- 海外服务器同步状态：首次传输过未优化版本；优化后的最终版因海外 SSH banner 超时，尚未确认同步成功，需连接恢复后重传并重启海外雷达/挂单/模拟盘进程。

### 新增数据与回测说明文档

- 新增 `峰极OS_数据与回测说明.md`：整理国内期货、虚拟货币、A股、实盘、模拟实盘和回测数据类型，列出数据目录、结果目录、运行态目录、字段标准、数据库结构和九大定式回测状态。
- 明确当前项目未发现已冻结的 `5m -> 60m` 转换脚本，60m/H1 当前应视为独立数据源、数据库导出或外部已处理 CSV；如需新增转换，必须先冻结国内期货夜盘 session 规则。
- 记录回测统一规则：禁止未来函数污染、信号确认延迟、期货/虚拟货币/A股的资金和费用差异、沙盒图验证要求和已知数据问题。

### 更新 Cursor Project Rules

- 更新 `.cursor/rules/project.mdc`：升级为峰极OS总工程 Cursor 接手规则，要求每次先读取根目录交接文档、峰极OS最高宪法、九大定式总纲、阵营转换、挂单器与服务器部署说明。
- 明确 Cursor 不能自动继承 Codex 旧聊天内容，必须以项目 Markdown 文件作为进度来源；修改前先说明计划，修改后同步 `TODO.md` 和 `CHANGELOG.md`。
- 补充安全红线：不得写入或输出 API Key、Token、Secret、服务器密码、SSH 私钥、完整 webhook 等敏感信息。

### 新增服务器与部署说明文档

- 新增 `峰极OS_服务器与部署说明.md`：整理国内服务器、国外服务器、部署目标、运行模块、数据来源、模拟实盘边界、启动/停止/日志/排查流程和安全红线。
- 明确服务器连接信息、登录用户、密码、API Key、Token、完整 webhook、数据源账号密码均不得写入仓库文档；敏感信息只写“见本地私密配置文件/环境变量/服务器控制台”。
- 标记当前服务器实时运行状态必须通过 SSH 实时检查，不能引用旧日志；国外数据泵守护方式、独立停止脚本和敏感配置迁移仍待补齐。

### 新增挂单器与模拟实盘说明文档

- 新增 `峰极OS_挂单器与模拟实盘说明.md`：整理挂单器目标、架构、DS01-DS09 接入状态、模拟实盘流程、风控安全、相关文件和当前风险。
- 明确当前挂单链路仍是模拟触发，不是真实下单；DS09 九重天雷达/挂单器/模拟盘全链路仍待补齐。
- 文档中不记录任何 API Key、Token、服务器密码、完整 webhook；对敏感信息只保留脱敏处理要求。

### 修正 DS09 九重天 D1 OS 阵营口径，并新增阵营转换专项文档

- 新增 `峰极OS_阵营转换判断.md`：独立记录红/蓝/中性阵营定义、转势状态机、峰极线与阵营关系、DS01-DS09如何调用阵营、相关代码文件、日志验证和已知问题。
- 修正 `packages/fengji_core/fengji_core/ds09.py`：DS09 D1边界生成必须读取进入当日前已完成的D1 OS阵营；红阵营+昨日阴线才授权多头，蓝阵营+昨日阳线才授权空头；缺少D1 `camp` 列直接报错。
- 修正 `src/backtest_ds09.py`：DS09回测先对D1运行峰极OS，再生成当日边界，避免只看昨日阴阳线；交易记录增加 `d1_camp` 审计字段。
- 更新 `tests/test_ds09.py`：新增D1 OS阵营必需和安全D1阵营授权边界的回归测试。
- 更新 `docs/DS09_CALIBRATION.md`、`docs/DS09_DRAFT.md`、`docs/DS09_IN_TOTAL_PATTERN.md`、`docs/CANONICAL_RULES.md`、`docs/FENGJI_TOTAL_PATTERN_SPEC.md`、`峰极OS_最高宪法.md`、`峰极OS_九大定式规则总纲.md`：废止“D1不提供OS阵营方向”的旧表述。
- 更新 `AGENTS.md`、`PROJECT_CONTEXT.md`、`README.md`、`TODO.md`：把 `峰极OS_最高宪法.md`、`峰极OS_阵营转换判断.md`、`峰极OS_九大定式规则总纲.md` 加入接手重点，并记录DS09雷达/挂单器待补齐事项。

### 补全 DS06、DS07、DS09 九大定式总纲

- 更新 `峰极OS_九大定式规则总纲.md`：DS06 外扩峰式从“部分完整”调整为“完整”，明确其核心为转势授权后等待 D/E/F 或 d/e/f 外扩启动，不是破旧极立即入场。
- 更新 `峰极OS_九大定式规则总纲.md`：DS07 共振式从“部分完整”调整为“完整”，当前正式口径为 D1 战略授权 + H1 同向延续或反向并轨；禁止恢复旧的“启动前 H1 必须已同阵营”窄逻辑。
- 更新 `docs/DS07_CALIBRATION.md` 和 `docs/DS07_DRAFT.md`：同步 DS07 当前并轨口径，避免旧文档误导后续 AI 或人工开发。
- 更新 `峰极OS_九大定式规则总纲.md`、`docs/DS09_CALIBRATION.md`、`docs/DS09_IN_TOTAL_PATTERN.md`：根据用户确认，DS09 股票式/A股专属版本等同九重天 D1+M15，不另立一套A股买卖规则。
- 更新 `TODO.md`：将 DS06、DS07、DS09 的规则补全事项标记完成，保留服务器同步、数据覆盖、运行验证等后续任务。

### 自动沉淀峰极OS总工程上下文

本次根据项目扫描结果、当前项目文件、已有代码、已有文档和当前会话上下文，更新根目录总交接文件。目标是让 Cursor 或新的 Codex 会话在无法读取旧聊天记录时，仍能理解这是完整峰极OS总工程，覆盖峰极OS最高宪法、阵营转换、DS01-DS09 九大定式、挂单器、实盘数据、国内/海外服务器、模拟实盘、回测验证和跨工具接手。

### 本次创建/更新的文件

- 更新 `PROJECT_CONTEXT.md`：新增“2026-05-27 总交接版”，补充项目名称、总目标、当前状态、已完成/未完成、目录结构、重要文件、峰极OS最高宪法、阵营转换、九大定式、挂单器、实盘数据、服务器部署、模拟实盘、回测验证、已知问题和接手说明。
- 更新 `AGENTS.md`：新增总工程接手规则，明确必须先读的文件、必须遵守峰极OS最高宪法和九大定式总纲、禁止凭空补全旧聊天、禁止删除未知文件、禁止写入敏感信息、修改前必须说明计划、修改后必须更新文档。
- 更新 `TODO.md`：新增总工程 TODO，按九大定式、阵营转换、挂单器、实盘数据、服务器、模拟实盘、回测、Cursor 接手拆分待办。
- 更新 `CHANGELOG.md`：追加本次上下文沉淀记录。
- 更新 `README.md`：新增总工程接手版摘要，补充项目简介、目录说明、Codex/Cursor 接手方式、运行验证和安全注意事项。

### 当前项目进度摘要

- 峰极OS总工程已形成核心结构：OS 引擎、九大定式、雷达、挂单器、数据泵、模拟盘、回测和交接文档。
- DS01、DS03、DS05、DS07 是最近重点修正对象，需要持续确认本地、国内服务器、海外服务器一致。
- DS02、DS04、DS06、DS08、DS09 已纳入工程，但仍需要同等强度的测试、案例和沙盒图复核。
- A股板块回测已有多个结果目录，但 A股 60 分钟历史数据覆盖不足，限制 DS07/DS08 的历史级结论。
- 国内/海外服务器部署链路已存在，但当前运行状态必须实时 SSH 检查，不能引用旧日志作为当前事实。

### 仍需人工确认的内容

- `packages/fengji_core` 与 `src/quant` 的权威源和同步机制。
- 国内/海外服务器是否已经部署全部最新 DS01、DS03、DS05、DS07 修正。
- DS02、DS04、DS06、DS08、DS09 的最终开仓/确认/撤销规则是否完全冻结。
- 国内期货日盘/夜盘数据泵自动运行表。
- A股 60 分钟数据源的替代或补齐方案。
- 文档中历史遗留敏感信息需要继续脱敏清理。

### 本次沉淀项目上下文

本次目标是把 Codex 旧聊天和当前项目进度沉淀为项目根目录 Markdown 文件，供 Cursor 或新的 Codex 会话继续接手。

### 本次新增或更新的文件

- 新增 `PROJECT_CONTEXT.md`
- 新增 `AGENTS.md`
- 新增 `TODO.md`
- 新增 `CHANGELOG.md`
- 更新 `README.md`
- 新增 `峰极OS_CANONICAL_RULES.md`

### 当前项目进度摘要

- 项目处于方案 A：引擎稳定化阶段。
- 峰极 OS、DS01-DS09、峰极总定式已经成型，但仍需测试和服务器同步复核。
- DS01、DS03、DS05、DS07 最近有重要规则修正，必须确认代码、雷达、挂单、模拟盘一致。
- A股热门20和多个板块已有批量结果，但 60 分钟历史覆盖不足，DS07/DS08 历史级结论需谨慎。
- 国内/海外模拟盘、数据泵和挂单监控需要实时 SSH 复查，旧日志不能当作当前状态。
- 当前虚拟货币阶段只允许模拟和观察，不允许真实下单。

### 下一步建议

1. 新会话先读取 `PROJECT_CONTEXT.md`、`AGENTS.md`、`TODO.md`、`峰极OS_CANONICAL_RULES.md`。
2. 运行 `git status --short`，识别现有未提交改动。
3. 跑核心测试或让用户在本地 PowerShell 跑测试。
4. SSH 检查海外、国内服务器进程、日志、数据新鲜度。
5. 继续 A股板块回测归档，复跑失败股票。
6. 明确并实现国内期货/A股数据泵开盘前自动更新、收盘后停止更新规则。
