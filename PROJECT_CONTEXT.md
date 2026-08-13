# PROJECT_CONTEXT

更新时间：2026-07-07

> **Codex / Cursor 一键接手入口：** [`CODEX_APP_HANDOFF.md`](CODEX_APP_HANDOFF.md)

## 2026-07-07 方案 B Phase 2 完成（D0–D7）

### 摘要

- **N 日清单 D0–D7 全部完成**；收口页 `docs/PHASE2_CLOSEOUT.md` · 验收 `python scripts/verify_phase2_closeout.py`。
- **D5**：天勤 `require_tq_credentials`（无代码默认明文）· 雷达频率/挂单撤销规则文档。
- **D6**：A股 H1≥500 定式门槛 · 期货 34 品种夜盘表 · `market_coverage`。
- **D7**：`stash@{0}` 边界审计（411 文件 · 勿整包 pop）。
- **D4**：`verify_d4_pattern_cases` · 国内飞书 `domestic_display`（纯碱 SA）。
- **D2–D3**：PR #13 pending plan/apply · PR #15 W18 watchlist。
- **D0–D1**：PR #12 os_engine/radar · OS 账本增量全绿。

详见 `docs/PLAN_B_PHASE2_PROGRESS.md`。

## 2026-07-06 方案 B Phase 2 进行中（归档）

### 摘要

- **PR #12 / D0–D1**：`os_engine`·radar 已 merge 并部署；OS 账本第二轮 **只追加**（国内 LC / 海外 BTC / 本地 incremental 全绿）。见 `docs/PLAN_B_PHASE2_PROGRESS.md`。
- **本地 PG + W17**：Docker PG · **7/7 + 5/5** · 见 `docs/PLAN_B_PHASE2_PROGRESS.md`。
- **国内 API**：`sync_deploy_fengji_api.ps1 -Verify` 通过（health ok；alembic **009 head**）。
- **pending monitor 锁优化**：海外 crypto + 国内 futures 均已 **plan/apply 分离**（锁内单次 `save_json` · 锁外 notify/CSV）；海外单轮 ~8s（原 ~24s）。
- **FUTURES 5m**：国内 34 品种 CSV 就绪 · 本机 sync + ingest · B0-2 **pass**（`scripts/assess_instruments_vs_coverage.py`）。
- **data_manager**：**34/34 fail=0**（7/5 16:51）· PG/SC **`[OK]`** · `ensure_single` 代码陈旧重启已部署。
- **国内 deploy / 运维**：`sync_deploy_domestic.ps1` · `verify_domestic_health.ps1` · `compare_overseas_core_hashes`（批量 SSH）· deploy+ops manifest 全绿。
- **海外 hash**：**mismatches=0**（2026-07-05 批量比对 ~7s）。

## 2026-07-02 方案 B Phase 1 完成

### 本轮状态摘要

- **Git `main`**：`2ead68e` · Phase 0（PR #1–#6）+ Phase 1（PR #7–#10）已全部 merge。
- **FastAPI / OpenAPI**：`services/api/main.py` · `docs/api/openapi.json` · **38 paths** · `export_openapi_snapshot.py`。
- **Web**：`web/` 已入库（登录/定价/付款/交流群分离 · `test_web_static`）。
- **部署**：`sync_deploy_fengji_api.ps1` + `fengji_api_deploy_manifest.txt` 全量文件齐 · W17 preflight ok。
- **Chart**：`src/chart_bundle.py` · `packages/fengji_core/.../chart_line.py`。
- **fill_supervision**：海外 audit `invalid_new=0`（见 Phase 0 验收）。
- **签收文档**：`docs/PLAN_B_PHASE1_COMPLETE.md` · `docs/PLAN_B_PHASE0_COMPLETE.md`。
- **Phase 2 入口**：本地 PG + W17 全量 acceptance · 国内 deploy 试跑 · FUTURES 5m 数据桶。
- **HYPE #28**：已 gap_stop 平仓 · `docs/HYPE28_STOP_FOLLOWUP.md`。

## 2026-05-28 LC DS09 与数据管线

### 本轮状态摘要

- **国内 LC（碳酸锂）DS09**：天勤真·15m 已回填至约 **10000 根**（请求 12000 时 `data_length=10000` 为当前最长校验通过档；12000/11000 常失败）；1d 稳定 **800 根**（LC 日线 >800 常校验失败，勿强求 1200）。
- **DS09 回测/校验**：`m15_rows≈9900`，`boundary_sessions=298`，`ds09_trades=0`，`ds09_bad_trades=0`；`debug_lc_ds09` 显示 `locks=0`（窗口内无 M15 突破昨日边界，属行情结果，非审计失败）。
- **天勤 CSV 加载**：`fengji_core.data.load_tq_futures_kline_csv` + `backtest_ds09.load_m15_frame` 优先解析纳秒 `datetime`；`data_manager_futures.fetch_frame` 对 15m 取**最长且校验通过**的 `data_length`。
- **验收文档**：`docs/LC_DS09_ACCEPTANCE.md`（数据、session、回测、雷达、签收表）。
- **脚本**：`backfill_lc_domestic.ps1`、`backfill_lc_on_server.py`、`repair_lc_15m_only.py`、`run_lc_ds09_domestic.ps1`（`-BuildFrom1h` 仅联调）、`build_lc_bars_from_1h.py`（禁止作实盘源）、`verify_ds09_lc_session.py`、`debug_lc_ds09.py`。
- **沙盒**：`results/sandbox/lc_ds09/LC_DS09_session_overview.png`；国内 `runtime/sandbox/lc_ds09/session_check.txt`。
- **Git**：`main` 已含 `8780b1e`（LC 流水线脚本）、`ec1be47`（加长 15m + 验收清单）等提交。
- **已签收（2026-05-28）**：用户确认接受 LC `ds09_trades=0`；对照 ETH `plan_a_verify` 区分引擎与行情。国内 **matplotlib** 可用 `scripts/domestic_install_matplotlib.ps1` 安装后补单笔沙盒图（待 `locks>0` 历史）。

### 国内服务器（时间敏感，须 SSH 复验）

- 项目根目录：`C:/Users/Administrator/quant_futures`（SSH 别名常见为 `domestic-quant`，见本机 SSH 配置）。
- 数据泵：`data_manager_futures.py`（**tqsdk 优先**，回退 tqsdk2）；`FUTURES_15M_LENGTH` 默认 **8000**，失败时 `frame_looks_acceptable` 降级；心跳 `runtime/logs/data_manager_heartbeat.txt`。
- 雷达：`fengji_radar_order_loop` 已含 LC；`sync_deploy_domestic.ps1` 可同步核心并 `-RestartRadarLoop`。
- Python：**3.10** 无法 `pip install -e fengji_core`（要求 ≥3.11），运行用 `PYTHONPATH=src;packages/fengji_core`。

## 2026-05-27 总交接版

### 项目名称

项目名称：峰极OS总工程。

本项目不是单一定式项目，也不是只包含 DS03/DS05 的临时工程，而是围绕峰极OS最高宪法、阵营转换、DS01-DS09 九大定式、挂单器、实盘数据、国内/海外服务器部署、模拟实盘、回测验证和 Cursor/Codex 跨工具接手建立的完整工程。

### 项目总目标

把峰极OS和九大定式做成一套可验证、可运行、可部署、可回测、可交接的量化交易工程：

- 峰极OS负责结构身份：峰、极、峰极线、3-3/T+3、红蓝阵营、转势状态。
- 九大定式负责交易触发：DS01-DS09 必须在峰极OS最高宪法之下执行。
- 雷达和挂单器负责提前计算触发价、止损价、距离和状态。
- 模拟实盘负责在不真实下单的前提下监控触发、记录开平仓、发送通知。
- 回测与沙盒图负责验证策略逻辑是否和峰极OS一致。
- 国内服务器、海外服务器负责长期运行数据泵、模拟盘和挂单监控。

### 当前项目状态

当前阶段：方案 A，引擎稳定化和实盘模拟链路固化。

当前状态概括：

- 本地工程已具备峰极OS核心、DS01-DS09、回测、雷达、挂单器、模拟盘、数据泵、部署脚本和交接文档。
- DS01、DS03、DS05、DS07 在 2026-05-26 至 2026-05-27 有过关键规则修正，需要持续确认本地、国内服务器、海外服务器三处一致。
- 海外虚拟货币模拟盘和国内期货/A股模拟盘已建立运行链路，但“当前是否正常运行”属于时间敏感事实，每次必须 SSH 实时检查。
- A股板块回测已经推进多个板块，但 A股 60 分钟历史数据覆盖仍是 DS07/DS08 历史级验证的主要限制。
- 当前虚拟货币和国内期货/A股均只允许模拟和观察，不允许自动真实下单。

### 已完成内容

- 已建立峰极OS最高宪法文档和根目录规则摘要。
- 已建立 `packages/fengji_core/fengji_core` 核心包，包含 OS 引擎与 DS01-DS09。
- 已建立 `src/quant` 策略层；其中 DS01、DS03、DS05、DS07 是最近活跃修正文件。
- 已建立 DS01-DS09 单定式回测入口。
- 已建立 A股单股、批量、板块回测入口。
- 已建立虚拟货币和国内期货/A股雷达、模拟挂单、挂单监控链路。
- 已建立海外虚拟货币模拟实盘入口。
- 已建立国内期货数据泵和海外虚拟货币数据泵。
- 已生成多批虚拟货币、国内期货、A股板块回测结果。
- 已生成多个沙盒图，用于检查峰极连线、阵营和买卖点标注。
- 已建立 `PROJECT_CONTEXT.md`、`AGENTS.md`、`TODO.md`、`CHANGELOG.md`、`README.md` 等跨工具交接文件。

### 未完成内容

- 需要确认 `src/quant` 与 `packages/fengji_core` 是否完全一致，避免双实现分叉。
- 需要确认国内服务器、海外服务器当前运行代码已经包含 DS01、DS03、DS05、DS07 最新修正。
- 需要建立独立的服务器运行手册、数据管线手册、挂单器手册、A股板块回测手册。
- 需要补齐或替换 A股 60 分钟历史数据源，否则 DS07/DS08 的 A股历史结论不能视为完整。
- DS09 国内 LC 已做 session/回测/雷达冒烟；待在有 `locks>0` 的历史窗口补单笔沙盒图，并对照 ETH `plan_a_verify` 区分引擎与行情。
- 需要对 DS02、DS04、DS06、DS08 做同等强度的案例复核、测试和沙盒图验证（DS09 规则已校准，LC 为数据与案例覆盖问题）。
- 需要明确国内期货日盘/夜盘数据泵自动运行表；A股无夜盘。
- 需要把敏感配置彻底迁移到本地私密配置文件或服务器环境变量，文档中只保留占位符。

### 当前目录结构

```text
C:\Users\guangwan\Documents\New project
├── .cursor/                         Cursor 项目规则
├── codex_assets/skills/              Codex 可复用技能草案
├── config/                           配置示例，不得写真实密钥
├── data/                             本地行情数据
│   ├── 1d/
│   ├── a_stock/
│   ├── a_stock_sina_smoke/
│   └── crypto_okx/
├── docs/                             峰极OS、九大定式、回测审查文档
├── packages/fengji_core/             峰极OS核心包，含 OS 与 DS01-DS09
├── results/                          回测结果、沙盒图、归档结果
├── runtime/                          运行态产物、远程检查快照、日志
├── scripts/                          检查、绘图、部署、重启脚本（含 LC DS09：`backfill_lc_domestic.ps1`、`run_lc_ds09_domestic.ps1`）
├── docs/LC_DS09_ACCEPTANCE.md        国内 LC DS09 验收清单
├── src/                              主程序、回测、雷达、挂单器、模拟盘
├── tests/                            pytest 测试
├── remote_domestic_optimize/          国内服务器同步/优化包
└── domestic_futures_ds07_update/      历史 DS07 更新包
```

### 重要文件说明

- `峰极OS_最高宪法.md`：峰极OS总工程最高规则文件，所有定式优先遵守。
- `峰极OS_阵营转换判断.md`：红蓝阵营、转势状态机、阵营转换代码逻辑专项文件。
- `峰极OS_九大定式规则总纲.md`：DS01-DS09统一规则总纲。
- `峰极OS_CANONICAL_RULES.md`：根目录规则摘要，给 Cursor/Codex 快速接手使用。
- `docs/CANONICAL_RULES.md`：当前工程峰极OS最高宪法来源之一。
- `docs/FENGJI_TOTAL_PATTERN_SPEC.md`：峰极总定式统一规格。
- `docs/PLAN_A_ROADMAP.md`：方案 A 引擎稳定化路线图。
- `packages/fengji_core/fengji_core/os_engine.py`：可复用峰极OS引擎。
- `packages/fengji_core/fengji_core/ds01.py` 到 `ds09.py`：九大定式核心包实现。
- `src/quant/os_engine.py`：当前主工程 OS 引擎镜像/策略层依赖。
- `src/quant/ds01.py`、`ds03.py`、`ds05.py`、`ds07.py`：最近活跃修正的策略逻辑。
- `src/fengji_total_radar.py`：总定式雷达，输出候选触发价与状态。
- `src/fengji_pending_orders.py`：根据雷达生成模拟挂单。
- `src/fengji_pending_order_monitor.py`：海外虚拟货币模拟挂单监控。
- `src/fengji_futures_pending_order_monitor.py`：国内期货/A股模拟挂单监控。
- `src/fengji_radar_order_loop.py`：雷达和挂单刷新循环。
- `src/峰极总定式01-08策略海外模拟实盘.py`：海外虚拟货币模拟实盘入口。
- `data_manager.py`：海外虚拟货币数据泵。
- `data_manager_futures.py`：国内期货数据泵。
- `src/backtest_ds01.py` 到 `src/backtest_ds09.py`：九大定式单独回测入口。
- `src/backtest_a_stock_fengji.py`、`src/batch_backtest_a_stock_sector.py`：A股回测入口。

### 峰极OS最高宪法的位置和作用

位置：

- `docs/CANONICAL_RULES.md`
- `docs/FENGJI_TOTAL_PATTERN_SPEC.md`
- `峰极OS_CANONICAL_RULES.md`
- `峰极OS_最高宪法.md`
- `峰极OS_阵营转换判断.md`
- `峰极OS_九大定式规则总纲.md`
- `src/quant/os_engine.py`
- `packages/fengji_core/fengji_core/os_engine.py`

作用：

- 统一定义峰、极、峰极线、3-3/T+3、红蓝阵营、转势状态机。
- 所有 DS01-DS09 必须读取 OS 输出的结构身份，不允许绕过 OS 直接用 raw high/low 判断峰极。
- 定式只负责触发、止损、出场和风控，不允许反向修改 OS 宪法。

### 阵营转换判断的位置和作用

位置：

- `src/quant/os_engine.py`
- `packages/fengji_core/fengji_core/os_engine.py`
- 对应测试：`tests/test_os_engine.py`

作用：

- 判断当前属于红色阵营、蓝色阵营还是转势过程。
- 约束 DS01-DS09 的做多/做空方向。
- 为 DS03、DS05、DS07、DS08、DS09 等依赖峰极结构的定式提供 active high/low、合法假峰/假极、硬化节点、D1安全阵营等基础信息。

### 九大定式总览

- DS01《挫式棍》：红阵营阳棍突破、蓝阵营阴棍跌破；左30线数当前工程口径为小于等于 2 段峰极连线可开仓。
- DS02《阴阳相吃式》：形态确认型策略，当前需继续确认开仓是否必须收线确认。
- DS03《二四棒式》：红阵营突破 active high 或合法假峰做多；蓝阵营跌破 active low 或合法假极做空。
- DS04《夹棍式》：K1/K2/K3 夹棍结构，当前需继续用玻璃、纯碱等案例回归验证。
- DS05《指形式》：K2 是可能形成“极”的位置；不要求 K2 靠近旧 active extreme，K2 与峰无关。
- DS06《外扩峰式》：已纳入工程，需要继续做案例和雷达验证。
- DS07《共振式》：D1 给战略授权，H1 通过 DS03 二四棒同向延续触发（`LONG/SHORT_CONTINUE`，`prev_h1_camp==1` 启动前已同阵营）；反向并轨已废止。
- DS08《否认确定式》：五点结构和否认确认逻辑已纳入雷达，需要继续做触发与撤销规则验证。
- DS09《股票式 / 九重天》：已纳入总工程；最新口径为 D1 OS战略阵营 + 昨日D1战略边界 + M15二次攻击点火；缺少 M15 数据时跳过 DS09，但不能把 DS09 从总工程删除。国内 LC 已接雷达/挂单/回测链路；2026-05-28 真·15m 约 10000 根下仍 0 笔成交（无边界突破），见 `docs/LC_DS09_ACCEPTANCE.md`。

### 挂单器当前状态

- 已有雷达生成器：`src/fengji_total_radar.py`。
- 已有模拟挂单生成器：`src/fengji_pending_orders.py`。
- 已有海外虚拟货币挂单监控：`src/fengji_pending_order_monitor.py`。
- 已有国内期货/A股挂单监控：`src/fengji_futures_pending_order_monitor.py`。
- 已有循环入口：`src/fengji_radar_order_loop.py`。
- 已有测试：`tests/test_pending_orders.py`、`tests/test_futures_pending_orders.py`、`tests/test_radar_ds04.py` 到 `tests/test_radar_ds08.py`。
- 当前状态：可生成和监控模拟挂单；是否正在服务器运行必须实时 SSH 检查。

### 实盘数据当前状态

- 海外虚拟货币数据泵：`data_manager.py`。
- 国内期货数据泵：`data_manager_futures.py`。
- 本地数据目录包括 `data/a_stock`、`data/crypto_okx`、`data/1d` 等。
- 已知问题：A股 60 分钟历史覆盖不足，影响 DS07/DS08 的历史级完整验证。
- 待确认：国内期货夜盘/日盘自动更新表是否已经在服务器稳定执行；A股无夜盘。

### 国内服务器与国外服务器部署状态

- 海外服务器：已配置虚拟货币模拟盘和数据泵链路，具体地址见本地私密配置文件或用户本机 SSH 配置。
- 国内服务器：已配置国内期货/A股模拟盘、数据泵、挂单监控链路，具体地址见本地私密配置文件或用户本机 SSH 配置。
- 部署脚本包括 `sync_src_to_server.ps1`、`scripts/restart_overseas_runtime.sh`、`scripts/restart_domestic_futures_runtime.ps1`、`scripts/restart_domestic_radar_loop.ps1`。
- 当前运行状态不可从旧日志推断，必须每次实时 SSH 检查进程、日志和数据新鲜度。

### 模拟实盘运行状态

- 海外虚拟货币模拟盘入口：`src/峰极总定式01-08策略海外模拟实盘.py`。
- 国内期货/A股模拟盘入口：`remote_domestic_optimize/峰极总定式01-08国内期货A股模拟实盘.py` 或服务器对应主目录中的同名文件。
- 运行状态：已有历史运行证据；当前是否正常必须实时检查。
- 安全边界：当前模式只允许模拟触发，不允许真实下单。

### 回测与验证状态

- 虚拟货币、国内期货、A股热门20、多个 A股板块已有结果目录。
- 沙盒图目录主要在 `results/sandbox` 和 `runtime/*sandbox*`。
- A股板块回测已覆盖 CPO、算力、半导体、机器人/虚拟机器人、低空经济、eVTOL、军工、航空装备、新能源车、乘用车、锂电池、证券等结果目录。
- 当前结论必须区分：日线 DS01-DS06 的可用性强于依赖小时线的 DS07/DS08。

### 已知问题

- 旧 Word 文档、旧脚本、远程同步包中可能残留旧 DS07、旧 DS05 或旧阵营理解，不能直接恢复。
- `src/quant` 与 `packages/fengji_core` 存在双路径实现，需要确认权威源和同步机制。
- 服务器状态、数据新鲜度、挂单触发都属于实时事实，不能用旧会话记忆替代检查。
- 敏感信息必须脱敏；文档和输出不得写明服务器密码、API Key、Token、私钥、完整 webhook。
- A股分钟数据不足会导致 DS07/DS08 回测结论不完整。

### 下一步任务

1. 明确权威代码源：`packages/fengji_core` 与 `src/quant` 的职责和同步方式。
2. 逐项复核 DS01-DS09 是否全部在峰极OS最高宪法下执行。
3. 实时检查国内/海外服务器模拟盘、数据泵、挂单器是否正常运行。
4. 补齐服务器运行手册、数据管线手册、挂单器手册、A股板块回测手册。
5. 继续 A股板块回测和失败股票重试归档。
6. 用沙盒图复核近期争议案例：RENDERUSDT、IOUSDT、ETHUSDT、DOGEUSDT、LTCUSDT、红枣、玻璃、纯碱。

### 给 Cursor / Codex 新会话的接手说明

新会话必须先读取：

```text
PROJECT_CONTEXT.md
AGENTS.md
TODO.md
CHANGELOG.md
README.md
峰极OS_最高宪法.md
峰极OS_阵营转换判断.md
峰极OS_九大定式规则总纲.md
峰极OS_CANONICAL_RULES.md
docs/CANONICAL_RULES.md
docs/FENGJI_TOTAL_PATTERN_SPEC.md
docs/PLAN_A_ROADMAP.md
```

接手后先做只读检查：

```powershell
Set-Location "C:\Users\guangwan\Documents\New project"
git status --short
Get-ChildItem -Force
```

如果要修改代码，必须先说明修改计划；修改后必须更新 `CHANGELOG.md` 和 `TODO.md`，并说明测试或验证结果。

## 项目名称与总目标

项目名称：峰极量化项目 / FengJi OS / 峰极总定式工程。

总目标：把峰极 OS、DS01-DS09、峰极总定式、回测、模拟实盘监测、挂单模拟、沙盒图审计和市场数据管线做成可验证、可复用、可交接的量化系统。当前优先级不是 Web/移动端产品化，而是方案 A：引擎稳定化。

核心原则：

- 峰极 OS 负责结构：峰、极、峰极线、红蓝阵营、转势。
- DS01-DS09 负责交易触发、入场、止损、出场。
- 峰极总定式负责统一账本、冲突处理、审计和白名单准入。
- 所有定式必须在峰极 OS 最高宪法下执行策略。

## 当前项目状态

当前阶段：方案 A 引擎稳定化，状态仍为进行中。

当前已具备：

- `src/quant/os_engine.py`：峰极 OS 身份引擎，包含 3-3/T+3、硬化峰极线、红蓝阵营状态机。
- `src/quant/ds01.py`、`src/quant/ds03.py`、`src/quant/ds05.py`、`src/quant/ds07.py`：当前正在活跃修正的定式逻辑。
- `src/backtest_ds01.py` 至 `src/backtest_ds09.py`：各定式回测入口。
- `src/unified_whitelist_engine.py`：峰极总定式统一账本入口。
- `src/batch_unified_crypto_whitelist.py`、`src/batch_unified_whitelist_engine.py`：虚拟货币、国内期货批量总定式回测入口。
- `src/backtest_a_stock_fengji.py`、`src/batch_backtest_a_stock_fengji.py`、`src/batch_backtest_a_stock_sector.py`：A股单股、批量、板块回测入口。
- `src/fengji_total_radar.py`、`src/fengji_pending_orders.py`、`src/fengji_pending_order_monitor.py`、`src/fengji_futures_pending_order_monitor.py`、`src/fengji_radar_order_loop.py`：雷达、模拟挂单和监控链路。
- `src/峰极总定式01-08策略海外模拟实盘.py`：海外虚拟货币模拟实盘入口。
- `data_manager.py`：海外虚拟货币数据泵。
- `data_manager_futures.py`：国内期货数据泵，已改为天勤长连接复用口径。

重要状态限制：

- 当前虚拟货币阶段只允许模拟与观察，不允许自动真实下单。
- A股小时线历史数据仍有覆盖不足问题，东方财富 60 分钟历史曾只返回约 128 根，DS07/DS08 历史级结论要谨慎。
- 本地 Python/pytest 在 Codex 沙箱里曾出现 `Access is denied`，不能把该错误直接判断为代码失败。
- 工作区已有大量未提交改动。接手者必须先读 `git status --short`，不得回滚用户或其他会话已有改动。

## 已完成内容

### 峰极 OS 与定式

- 峰极 OS 当前口径已固化在 `docs/CANONICAL_RULES.md`、`docs/FENGJI_TOTAL_PATTERN_SPEC.md`、`src/quant/os_engine.py`。
- DS01、DS02、DS03、DS04、DS05、DS06、DS07、DS08 已有 draft/calibration 文档。
- DS09 已纳入峰极总定式。最新口径为 D1 OS战略阵营 + 昨日D1战略边界 + M15二次攻击点火；缺少 M15 数据时跳过 DS09，但 DS01-DS08 照常运行。
- DS01 左30线数已修正为“启动棍水平方向向左30根K线内穿过峰极线段数 <= 2”，不是左侧 30 根峰极点数量。
- DS03 已支持在红阵营/蓝阵营中突破合法假峰/假极触发，前提是该假峰/假极来自峰极 OS 硬化节点与合法 N 形结构。
- DS05 已修正为 K2 是可能形成“极”的位置，不要求靠近旧 active extreme，也不是峰候选。
- DS07 已按权威源冻结为 D1 提供战略授权，H1 通过 DS03 二四棒同向延续触发（`LONG/SHORT_CONTINUE`），要求启动前已同阵营（`prev_h1_camp==1`）；反向并轨（ALIGN_TURN）已废止。

### 回测与审查

- 国内期货 DS01-DS08、虚拟货币总定式、A股热门20和多个 A股板块已有结果文件。
- A股热门20审查文档：`docs/FENGJI_TOTAL_A_STOCK_HOT20_REVIEW.md`。
- A股 fixed 热门20汇总：`results/fengji_total_a_stock_hot20_ds07_fixed/a_stock_hot20_summary.csv`。
- 多个 A股板块结果位于 `results/fengji_total_a_stock_sectors_*_ds07_fixed`。
- 交接文件 `CODEx_当前上下文交接.md` 已记录 2026-05-26 以前的重要项目状态。

### 运行与部署

- 海外服务器历史项目位置：已配置，具体地址见本地私密配置文件或用户本机 SSH 配置。
- 国内服务器历史项目位置：已配置，具体地址见本地私密配置文件或用户本机 SSH 配置。
- 不要在文档中写入飞书 webhook、API Key、Token、密码、私钥。
- 本项目已新增可复用 Skill 草案在 `codex_assets/skills/`，用于运行体检、信号沙盒审计、A股板块回测接手。

## 当前目录结构

```text
.
├── README.md
├── PROJECT_CONTEXT.md
├── AGENTS.md
├── TODO.md
├── CHANGELOG.md
├── 峰极OS_最高宪法.md
├── 峰极OS_阵营转换判断.md
├── 峰极OS_九大定式规则总纲.md
├── 峰极OS_CANONICAL_RULES.md
├── FJLHXM-V1.md
├── CODEx_当前上下文交接.md
├── data_manager.py
├── data_manager_futures.py
├── docs/
│   ├── CANONICAL_RULES.md
│   ├── FENGJI_TOTAL_PATTERN_SPEC.md
│   ├── PLAN_A_ROADMAP.md
│   ├── DS01_DRAFT.md / DS01_CALIBRATION.md
│   ├── DS02_DRAFT.md / DS02_CALIBRATION.md
│   ├── DS03_DRAFT.md / DS03_CALIBRATION.md
│   ├── DS04_DRAFT.md / DS04_CALIBRATION.md
│   ├── DS05_CALIBRATION.md
│   ├── DS06_DRAFT.md / DS06_CALIBRATION.md
│   ├── DS07_DRAFT.md / DS07_CALIBRATION.md
│   ├── DS08_DRAFT.md / DS08_CALIBRATION.md
│   └── DS09_DRAFT.md / DS09_CALIBRATION.md
├── src/
│   ├── quant/
│   ├── backtest_ds01.py ... backtest_ds09.py
│   ├── unified_whitelist_engine.py
│   ├── batch_unified_crypto_whitelist.py
│   ├── batch_unified_whitelist_engine.py
│   ├── backtest_a_stock_fengji.py
│   ├── batch_backtest_a_stock_sector.py
│   ├── fengji_total_radar.py
│   ├── fengji_pending_orders.py
│   ├── fengji_pending_order_monitor.py
│   ├── fengji_futures_pending_order_monitor.py
│   └── 峰极总定式01-08策略海外模拟实盘.py
├── scripts/
│   ├── plan_a_verify.ps1
│   ├── plot_live_ds03_sandbox.py
│   ├── plot_live_ds03_sandbox_svg.py
│   ├── restart_overseas_runtime.sh
│   ├── restart_domestic_futures_runtime.ps1
│   └── start_factory_ascii.bat
├── tests/
├── results/
├── runtime/
├── packages/fengji_core/
└── codex_assets/skills/
```

## 重要代码文件说明

- `src/quant/os_engine.py`：峰极 OS 最高宪法的工程核心。任何定式判断都必须从这里的 OS 输出字段出发。
- `src/quant/ds01.py`：DS01 挫棍，含左30线数逻辑。
- `src/quant/ds03.py`：DS03 二四棒，含 active peak/low 和 failed high/low 触发逻辑。
- `src/quant/ds05.py`：DS05 指形战法，K2 可能形成极。
- `src/quant/ds07.py`：DS07 跨周期 D1+H1 共振逻辑。
- `src/fengji_total_radar.py`：把 DS01-DS08/相关定式转成雷达行，供挂单与监控使用。
- `src/fengji_pending_orders.py`：把雷达行转成模拟挂单。
- `src/fengji_pending_order_monitor.py`：海外虚拟货币模拟挂单监控。
- `src/fengji_futures_pending_order_monitor.py`：国内期货/A股模拟挂单监控。
- `src/峰极总定式01-08策略海外模拟实盘.py`：海外模拟实盘主文件，当前不真实下单。
- `data_manager.py`：海外虚拟货币数据同步。
- `data_manager_futures.py`：国内期货数据同步。
- `src/batch_backtest_a_stock_sector.py`：A股板块批量回测，继续板块回测时优先看这个。

## 已确定的重要决策

1. 所有定式必须在峰极 OS 最高宪法下执行策略。
2. 旧 Word 文档只作为历史素材或策略触发逻辑参考，不再决定 OS、峰极线、阵营、转势规则。
3. `hardened_fengji_line` 是沙盒图主峰极线。
4. 峰永远是进攻方向，极永远是防守点与转势关键。
5. 3-3/T+3 释放后，硬化峰极点必须峰极交替，同类吞并，峰极之间至少间隔 2 根完整 K 线。
6. 红极失守红转蓝，蓝极失守蓝转红。
7. DS01 左30线数不是峰极点数量过滤，当前工程口径是穿过峰极线段数 <= 2。
8. DS03 假峰/假极可作为触发点，但必须来自 OS 硬化节点和合法 N 形结构。
9. DS05 K2 是可能形成极，不是峰；K2 不要求靠近旧 active extreme。
10. DS07 D1 提供战略授权，H1 通过 DS03 二四棒同向延续触发（`LONG/SHORT_CONTINUE`），H1 启动前必须已与 D1 同阵营（`prev_h1_camp==1`）；反向并轨已废止。
11. DS04 是抄底摸顶型三K夺权定式，不用红多蓝空作为前置过滤，但仍必须读 OS 做审计。
12. 虚拟货币当前只模拟、观察、挂单触发，不真实下单。
13. A股当前只做多，执行规则按 `docs/FENGJI_TOTAL_A_STOCK_HOT20_REVIEW.md`。

## 已知问题

- 本地 Python 在 Codex 沙箱中可能被权限拦截，表现为 `Access is denied`。
- `pytest` 可能不在 PATH，需要用完整 Python 路径或先修 PATH。
- A股 60 分钟历史数据覆盖不足，影响 DS07/DS08 历史结论。
- 工作区有大量未提交修改和新增数据文件，接手前必须先看 `git status --short`。
- 服务器运行状态是时间敏感信息，必须实时 SSH 检查后再回答“当前是否正常”。
- 国内期货晚盘、日盘与 A股无夜盘的运行计划仍需明确固化。
- `左三线` 的最终工程定义目前未在已读文件中找到完整冻结版，必须标记待确认。

## 下一步任务

1. 复查当前未提交代码改动，确认 DS01、DS03、DS05、DS07 和 OS 的最终逻辑都已同步到国内/海外服务器。
2. 运行核心测试：`tests/test_ds01.py`、`tests/test_ds03.py`、`tests/test_ds05.py`、`tests/test_os_engine.py`、`tests/test_pending_orders.py`、`tests/test_futures_pending_orders.py`、`tests/test_radar_*.py`。
3. 检查海外模拟盘、国内期货/A股模拟盘、数据泵、雷达挂单循环是否仍在运行。
4. 继续 A股板块回测，复跑失败股票并归档板块结果。
5. 补齐 A股 60 分钟历史数据，或将 A股正式筛选口径临时降为 DS01-DS06 日线版。
6. 把 `codex_assets/skills/` 里的 Skill 按需要安装到全局 Codex 技能目录。
7. 若要交给 Cursor，先让 Cursor 读取本文件、`AGENTS.md`、`TODO.md`、`峰极OS_最高宪法.md`、`峰极OS_阵营转换判断.md`、`峰极OS_九大定式规则总纲.md`、`峰极OS_CANONICAL_RULES.md`。

## 给 Cursor / Codex 新会话的接手说明

新会话第一步请执行只读检查：

```powershell
Set-Location "C:\Users\guangwan\Documents\New project"
git status --short
Get-Content .\PROJECT_CONTEXT.md
Get-Content .\AGENTS.md
Get-Content .\TODO.md
Get-Content .\峰极OS_最高宪法.md
Get-Content .\峰极OS_阵营转换判断.md
Get-Content .\峰极OS_九大定式规则总纲.md
Get-Content .\峰极OS_CANONICAL_RULES.md
```

推荐启动提示词：

```text
请先读取 PROJECT_CONTEXT.md、AGENTS.md、TODO.md、CHANGELOG.md、README.md、峰极OS_最高宪法.md、峰极OS_阵营转换判断.md、峰极OS_九大定式规则总纲.md、峰极OS_CANONICAL_RULES.md，以及 docs/CANONICAL_RULES.md 和 docs/FENGJI_TOTAL_PATTERN_SPEC.md。不要删除文件，不要回滚已有改动。所有定式必须在峰极OS最高宪法下执行。读取后先汇报当前状态和下一步建议。
```
