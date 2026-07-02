# TODO

更新时间：2026-07-02（Phase 1 完成 · `2ead68e`）

## 2026-07-02 · 方案 B Phase 1 完成 ✅

- [x] **PR #7–#10 全部 merge**（services · chart · deploy · web）。
- [x] **Phase 1 签收**：`docs/PLAN_B_PHASE1_COMPLETE.md`（manifest 全绿 · OpenAPI 38 · pytest 18 passed · W17 preflight ok）。
- [ ] **Phase 2**：本地 PG + W17 全量 acceptance · 国内 `sync_deploy_fengji_api.ps1 -Verify` · FUTURES 5m 数据桶。
- [ ] **HYPE #28**：`docs/HYPE28_STOP_FOLLOWUP.md` · 待 07-02 D1。
- [ ] **stash@{0}**：按桶 cherry-pick · 勿整包 pop。

## 2026-07-02 · 方案 B Phase 0 完成

## 已完成 / 待复查（2026-05-28 LC DS09 与数据）

- [x] **LC 天勤 15m 加长回填**：`backfill_lc_domestic.ps1` 请求 12000 → 实际选用 **10000** 根（校验通过）；1d **800** 根；`data_manager_futures.fetch_frame` 最长 sane 档逻辑（`ec1be47`）。
- [x] **天勤 CSV 解析**：`load_tq_futures_kline_csv`、`load_m15_frame` 纳秒 `datetime`；避免误用天勤 7 列启发式（`8596374`）。
- [x] **LC DS09 校验脚本**：`verify_ds09_lc_session.py`、`debug_lc_ds09.py`；真数据 `m15≈9900`、`bad_trades=0`、`locks=0`。
- [x] **国内流水线**：`run_lc_ds09_domestic.ps1`（`-BuildFrom1h` 仅联调）；`sync_deploy_domestic.ps1` 同步 DS09/雷达；雷达循环已重启。
- [x] **验收清单**：`docs/LC_DS09_ACCEPTANCE.md`。
- [x] **沙盒总览图**：`results/sandbox/lc_ds09/LC_DS09_session_overview.png`（真·15m 数据）。
- [x] **Git 推送**：`8780b1e`、`ec1be47` 等已上 `origin/main`。
- [x] **LC DS09 0 笔**：用户确认接受（2026-05-28）；`locks=0` 为行情结果，ETH 作引擎对照，勿用 `build_lc_bars_from_1h` 冒充验收。
- [x] 国内服务器已安装 `matplotlib` 3.10.9（`domestic_install_matplotlib.ps1`，2026-05-28）。
- [ ] **待复查**：有 `locks>0` 历史时再补 `LC_DS09_trade_*.png`。
- [ ] **待复查**：`data_manager_futures.py` 中天勤账号默认值是否已迁到环境变量（勿提交密钥）。

## 2026-05-28 增量 TODO

- [x] 确认 `packages/fengji_core` 与 `src/quant` 的权威关系：`packages/fengji_core/fengji_core` 为核心权威源，`src/quant` 为兼容层。
- [x] 将 `src/quant/os_engine.py`、`ds01.py`、`ds03.py`、`ds05.py`、`ds07.py` 收敛为 re-export，降低双实现分叉风险。
- [x] 运行核心测试集，确认 re-export 后 `quant.*` 兼容入口仍正常。
- [x] 用导入 smoke test 验证 CLI、回测、雷达和挂单链路所依赖的 `quant.*` 兼容导入仍能加载核心包。
- [x] **2026-05-28 验收**：`pytest tests/` 59+ passed；`scripts/plan_a_verify.ps1` 全绿（含 ETH DS01–DS09 smoke，`bad_audits=0`）。
- [x] **运行态巡检**：`check_overseas_runtime_status.ps1` + 新增 `check_domestic_runtime_remote.ps1`（雷达/挂单 15:15–15:19 更新，LC 数据 15:13）。
- [x] 修正 `tests/test_radar_setup_keys.py` 中 DS03 `setup_key` 断言（`watch` / `peak_key` 新规口径）。
- [x] 海外 OS 增量：`verify_os_state_overseas.sh` 两轮 radar `--once`，BTC `delta1=2` `delta2=0`，`processed_len=1835` 不变。
- [x] 国内 OS 增量：`verify_os_state_domestic.ps1` LC `delta1=0` `delta2=0`，`processed_len=690` 不变。
- [x] 本地 OS 增量：`verify_os_state_incremental.py` IOUSDT 第二轮 `size_delta=0`。
- [x] IOUSDT DS03 沙盒：`results/sandbox/io_ds03_20260528/IOUSDT_DS03_long_20260526.png`（测试口径参数；实盘 IO 该日无 fake_peak 触发，与合成用例一致见 `test_ds03`）。

## 2026-05-27 总工程 TODO

### 当前最高优先级任务

1. 连接恢复后立即重传峰极OS增量连线最终版到海外服务器：`src/quant/os_engine.py`、`src/quant/ds07.py`、`src/fengji_total_radar.py`，然后重启海外雷达/挂单/模拟盘并检查 `runtime/fengji_os_state` 是否生成。
1. 复核并同步 DS09《股票式 / 九重天》最新口径：D1必须在峰极OS下给出安全红/蓝阵营，M15只在第一次刺穿后锁定，等待第一进攻峰、防守极、二次攻击才入场。
1. 固化峰极OS总工程交接文档，保证 Cursor/Codex 可在无旧聊天记录的情况下接手。
2. 已确认 `packages/fengji_core` 与 `src/quant` 的权威关系：`packages/fengji_core/fengji_core` 为核心权威源，`src/quant` 为兼容层；后续重点是验证和服务器同步。
3. 复核 DS01、DS03、DS05、DS07 最新规则是否已同步到本地、国内服务器、海外服务器。
4. 实时检查国内/海外服务器的数据泵、模拟盘、雷达循环、挂单监控是否正常运行。
5. 继续 A股板块回测、失败股票重试和结果归档。

### 九大定式逐个待完成任务

- [ ] DS01《挫式棍》：复核左30线数小于等于 2 的代码、测试、雷达、挂单、模拟盘是否一致；重点复核 RENDERUSDT、IOUSDT、DOGEUSDT 案例。
- [ ] DS02《阴阳相吃式》：确认是否属于收线确认型策略；补充雷达输出、测试和沙盒图案例。
- [ ] DS03《二四棒式》：复核 active high/low 与合法假峰/假极触发；重点复核 IOUSDT 2026-05-26、ETHUSDT 2026-05-27。
- [ ] DS04《夹棍式》：复核 K1/K2/K3 结构和触发条件；重点复核玻璃、纯碱 2026-05-26。
- [ ] DS05《指形式》：确认 K2 是可能形成“极”的位置，不要求靠近旧 active extreme，不与峰混淆；重点复核红枣案例。
- [x] DS06《外扩峰式》：核心规则已补齐为转势授权 + D/E/F 外扩峰启动；后续只剩服务器/更多市场运行覆盖验证。
- [x] DS07《共振式》：核心规则已补齐为同向延续 + 反向并轨；已同步 `docs/DS07_CALIBRATION.md` 和 `docs/DS07_DRAFT.md`，后续继续排查服务器旧逻辑残留。
- [ ] DS08《否认确定式》：复核五点结构、否认、确定、触发和撤销规则。
- [x] DS09《股票式 / 九重天》：用户已确认股票式/A股专属版本等同九重天；2026-05-27 已修正为 D1 OS战略阵营 + 昨日D1战略边界 + M15二次攻击点火；缺少 M15 数据时只跳过 DS09，不影响 DS01-DS08。
- [x] DS09 国内 LC：夜盘 `assign_cn_futures_session_date`、雷达/挂单接入、天勤 15m 回填与验收清单（2026-05-28）；**成交沙盒图**待有 `locks>0` 历史后再补。

### 阵营转换判断待验证任务

- [ ] 海外服务器连接恢复后，确认峰极OS状态账本 `runtime/fengji_os_state` 按品种/周期生成，并验证第二轮雷达只追加新K线，不重连历史峰极线。
- [ ] 用沙盒图验证红蓝阵营切换是否严格遵守峰极OS最高宪法。
- [ ] 复核 active high/active low、红极/蓝极、合法假峰/假极的字段来源。
- [ ] 确认 DOGEUSDT、LTCUSDT、RENDERUSDT、IOUSDT 的近期阵营判断是否和图形一致。
- [ ] 补充或更新 `tests/test_os_engine.py` 的争议案例。
- [ ] 用DS09固定样本验证 D1红阵营+昨日阴线多头、D1蓝阵营+昨日阳线空头，确保不再只按昨日阴阳线触发。

### 挂单器待完成任务

- [ ] 明确每日/每轮雷达刷新频率。
- [x] 补齐 DS09 雷达/挂单器候选生成：D1安全阵营、昨日边界、M15锁定、第一进攻峰、防守极、二次攻击（`add_ds09` + 挂单默认含 DS09；2026-05-28）。【待复查】国内 LC 当前雷达 DS09 行数常为 0（无结构）。
- [ ] 明确同品种一个定式触发后，其他定式挂单是否撤销及如何记录。
- [ ] 确认国内期货/A股挂单器和海外虚拟货币挂单器规则一致，但市场交易时间不同。
- [ ] 补充挂单触发后的沙盒图自动生成或半自动检查流程。
- [x] 建立独立 `峰极OS_挂单器与模拟实盘说明.md`，交接挂单器、模拟实盘、日志、安全和待补齐边界。

### 实盘数据待整理任务

- [ ] 梳理虚拟货币数据源、更新频率、失败补偿和数据新鲜度检查。
- [x] 梳理国内期货天勤 LC 15m 加长与脏数据边界：`FUTURES_15M_LENGTH`、最长 sane 档、`docs/LC_DS09_ACCEPTANCE.md`（2026-05-28）。【待复查】是否需天勤历史区间 API 突破 10000 根上限。
- [ ] 梳理国内期货天勤数据源、日盘/夜盘开收盘时间、开盘前自动更新、收盘后停止规则（全品种表）。
- [ ] 梳理 A股数据源；A股无夜盘。
- [ ] 补齐或替换 A股 60 分钟历史数据源。
- [x] 建立独立 `峰极OS_数据与回测说明.md`，交接数据类型、文件位置、字段、5m/60m状态、回测规则和九大定式回测状态。

### 国内服务器与国外服务器待验证任务

- [x] 国内全链路重启脚本：`resolve_domestic_paper.ps1` + manifest；`cmd` 内 `PYTHONPATH` 引号修复；`fengji_radar_order_loop` 子进程补 `packages/fengji_core`（2026-05-28）。
- [ ] 国内服务器：实时检查数据泵、模拟盘、雷达循环、挂单监控、日志、数据新鲜度。【待复查】数据泵偶发双进程，需确认 `start_factory` 是否重复拉起。
- [ ] 海外服务器：实时检查数据泵、模拟盘、雷达循环、挂单监控、日志、数据新鲜度。
- [ ] 确认服务器代码版本与本地核心文件一致。
- [ ] 确认服务器启动脚本使用脱敏配置，不把密钥写入仓库。
- [x] 建立独立 `峰极OS_服务器与部署说明.md`，交接国内/国外服务器、部署、启动停止、日志排查和安全红线。

### 模拟实盘运行待完成任务

- [ ] 海外虚拟货币：确认 DS01-DS08/DS09 的当前覆盖状态和通知格式。
- [ ] 国内期货/A股：确认模拟盘入口、启动工厂、数据泵和挂单器协同。
- [ ] 明确模拟开仓、平仓、止损、手续费滑点和账本字段。
- [ ] 确认当前全部链路仍是只模拟、不真实下单。

### 回测待验证任务

- [ ] 回归九大定式单定式测试。
- [ ] 回归总定式统一账本。
- [ ] 继续 A股板块回测，复跑失败股票。
- [ ] 对最近有争议的信号生成沙盒图并归档。
- [ ] 对 A股 DS07/DS08 标注数据覆盖不足边界。

### Cursor 接手待完成任务

- [ ] Cursor 打开项目前先读取交接文件。
- [ ] Cursor 只按项目文档和当前代码判断，不继承不可见旧聊天。
- [ ] Cursor 修改代码前先输出计划，修改后更新 `CHANGELOG.md` 和 `TODO.md`。
- [ ] Cursor 不得写入服务器地址、密码、Token、完整 webhook。
- [x] 更新 `.cursor/rules/project.mdc`，让 Cursor 每次接手峰极OS总工程时自动遵守项目交接规则。

### 风险点

- 权威源重复：`packages/fengji_core`、`src/quant`、远程同步包可能出现旧逻辑分叉。
- 旧 DS07、旧 DS05、旧左30理解可能污染当前策略。
- 服务器运行状态随时间变化，不能用旧日志当当前状态。
- A股小时线数据不足会导致 DS07/DS08 回测结论偏弱。
- 敏感信息不能写入文档、日志或输出。
- 当前只允许模拟，不允许真实下单。

### 下一次启动 Codex / Cursor 的建议提示词

```text
请先读取 C:\Users\guangwan\Documents\New project 下的 PROJECT_CONTEXT.md、AGENTS.md、TODO.md、CHANGELOG.md、README.md、峰极OS_CANONICAL_RULES.md，以及 docs/CANONICAL_RULES.md、docs/FENGJI_TOTAL_PATTERN_SPEC.md、docs/PLAN_A_ROADMAP.md。这个项目是峰极OS总工程，包含 DS01-DS09 九大定式，不是单一定式项目。不要删除文件，不要回滚已有改动，不要写入任何服务器密码、API Key、Token 或完整 webhook。读取后先汇报当前状态、权威源风险、下一步建议，然后等待我指定任务。
```

## 当前最高优先级任务

1. 固化当前项目上下文，保证 Cursor/Codex 新会话可接手。
2. 复查 DS01、DS03、DS05、DS07 与峰极 OS 的当前代码是否全部同步到海外、国内服务器。
3. 检查海外虚拟货币模拟盘、国内期货/A股模拟盘、数据泵、雷达挂单循环是否仍正常运行。
4. 跑核心测试，确认最近策略修正没有破坏雷达、挂单和模拟盘。

## 待完成任务

- [x] 安装或修复本地测试环境，解决 `pytest` / Python 权限问题。
- [x] 运行 `scripts\plan_a_verify.ps1` 做 A0 安装验收（2026-05-28 全绿）。
- [x] 运行核心测试集（2026-05-28：`59 passed`）。
- [ ] 复核海外服务器：
  - `data_manager.py`
  - `src/峰极总定式01-08策略海外模拟实盘.py`
  - `fengji_pending_order_monitor.py`
  - `fengji_radar_order_loop.py`
  - `paper_run.log`
  - `data_sync.log`
  - `pending_order_monitor.log`
- [ ] 复核国内服务器：
  - `data_manager_futures.py`
  - `峰极总定式01-08国内期货A股模拟实盘.py`
  - `商业终端_Dash.py`
  - 国内期货/A股挂单逻辑
  - 启动工厂 bat/cmd
- [ ] 继续 A股板块回测，复跑失败股票，归档结果。
- [ ] 补齐 A股 60 分钟历史数据，或明确 A股正式筛选临时只用 DS01-DS06 日线口径。
- [ ] 明确国内期货日盘/夜盘数据泵自动运行时间表；A股无夜盘。
- [ ] 把 `codex_assets\skills` 中的技能安装到全局 Codex 技能目录，若后续需要自动触发。

## 待验证问题

- [ ] `左三线` 的最终定义仍待确认。不要自行编造；需要从用户确认或权威白皮书/代码冻结版中确认。
- [ ] 当前 `src/quant` 与 `packages/fengji_core` 是否完全一致，是否存在双实现不同步。
- [ ] 国内服务器当前代码是否已经包含 DS01 左30 <=2、DS03 failed peak/low、DS05 K2 可能极、DS07 新逻辑。
- [ ] 海外服务器当前代码是否已经包含 DS01 左30 <=2、DS03 failed peak/low、DS05 K2 可能极、DS07 新逻辑。
- [x] **A 股三板块补跑（2026-05-29）**：新能源车 `BK0900`、证券 `BK0473`、互联网金融 `BK0637` → `results/fengji_total_a_stock_sectors_ev_sec_fintech_ds07_fixed`；汇总 `results/a_stock_all_sectors_overview.csv`。
- [ ] A股板块结果是否已全部归档到 `results\a_stock_sector_archive_ds07_fixed.zip` 或对应目录。【部分】zip 仅含 CPO/算力/半导体/虚拟机器人 4 板块摘要，全量见 `results/fengji_total_a_stock_sectors_*`。
- [ ] 现有模拟挂单触发是否需要每日开盘前统一刷新，触发一笔后是否撤销同品种其他定式挂单。

## 已完成但需要复查的内容

- [ ] DS01 左30线数修正：确认代码、测试、雷达、模拟盘一致。
- [ ] DS03 假峰/假极触发：确认 IOUSDT 2026-05-26/27 案例及 ETHUSDT DS03 空头案例。
- [ ] DS05 K2 可能形成极：确认红枣、玻璃、纯碱等国内期货案例。
- [ ] DS07 新逻辑：确认旧逻辑已删除，不会污染海外/国内模拟盘。
- [ ] 国内 `data_manager_futures.py` 天勤长连接复用：确认开盘前/收盘后自动运行逻辑。
- [ ] 海外服务器模拟盘：确认 16 个虚拟货币数据和挂单监控日志持续更新。

## 风险点

- 工作区存在大量未提交代码和数据变更，严禁回滚。
- 本地 Python 执行权限可能被 Codex 沙箱拦截。
- 服务器上运行状态会随时间变化，不能使用旧日志当作当前事实。
- A股 60 分钟历史不足会导致 DS07/DS08 历史结论不完整。
- 旧 Word 文档和旧代码可能包含旧 OS、旧 DS07、旧 DS05 理解，不能直接恢复。
- 文档和日志中不能写入完整 webhook、Token、密码、私钥。
- 虚拟货币当前只模拟，不真实下单。

## 下一次启动 Cursor / Codex 时的建议提示词

```text
请先读取 PROJECT_CONTEXT.md、AGENTS.md、TODO.md、CHANGELOG.md、README.md、峰极OS_CANONICAL_RULES.md，以及 docs/CANONICAL_RULES.md 和 docs/FENGJI_TOTAL_PATTERN_SPEC.md。不要删除文件，不要回滚已有改动。所有定式必须在峰极OS最高宪法下执行。读取后先汇报当前状态、未提交改动风险、下一步建议，然后等待我指定任务。
```
