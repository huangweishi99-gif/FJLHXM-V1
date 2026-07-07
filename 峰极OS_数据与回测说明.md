# 峰极OS_数据与回测说明.md

更新时间：2026-05-27

本文用于交接峰极OS总工程的数据资产、数据字段、5分钟/60分钟处理状态、回测统一规则、九大定式回测状态和图形验证要求。本文只记录项目结构和规则，不复制大数据内容，不记录任何账户、服务器、API Key、Token、密码或 webhook。

## 1. 数据类型

### 国内期货数据

国内期货数据分为两类：

- 服务器模拟实盘数据：由 `data_manager_futures.py` 在国内服务器上通过天勤数据源更新，服务于国内期货/A股模拟盘、雷达、挂单监控。
- 历史回测数据：项目中通过 `src/market_data_store.py` 导入本地 SQLite 行情库，或由回测脚本读取外部本地 CSV。外部历史数据目录不在本文写明，接手者应通过本地私密配置或用户指定路径确认。

当前工程中，国内期货回测脚本默认支持日线、60分钟线、15分钟线等不同周期；DS07 需要 D1 + H1/60m，DS08 主要使用 H1/60m，DS09 需要 D1 + M15。

### 虚拟货币数据

虚拟货币数据分为：

- 本地/服务器模拟盘数据：`data_manager.py` 从 Binance 行情接口同步 `1d`、`1h`、`15m` 到服务器项目 `data` 目录。
- 本地回测缓存：`data/crypto_okx` 中保存 OKX 格式的 `1D`、`1H`、`15m` 回测缓存。
- SQLite 数据库：`data/market_data.sqlite` 可导入虚拟货币缓存，统一为 `CRYPTO` 市场。

虚拟货币回测当前既有 DS01-DS08 旧结果，也有 DS01-DS09 总定式相关脚本；DS09 依赖 M15 数据。

### 股票数据

股票数据主要包括：

- `data/a_stock`：A股日线和 60分钟线缓存，文件名常见形式如 `代码_1D_qfq.csv`、`代码_60m_qfq.csv`。
- `data/a_stock_sina_smoke`：新浪数据源烟雾测试缓存。
- `data/market_data.sqlite`：本地 SQLite 行情库，支持 `A_STOCK` 市场。
- `src/backtest_a_stock_fengji.py`：A股峰极总定式回测入口，优先从数据库读取，缺数据时可下载或使用本地缓存。

已知限制：A股 60分钟历史覆盖不足，曾出现只返回约 128 根 60分钟线的情况，因此 DS07/DS08 的 A股历史级结论不能按完整历史验证处理。工程门槛与日夜盘表见 **`docs/MARKET_COVERAGE_BOUNDARIES.md`**（H1≥500 方可 DS07/DS08；不足时回测自动降级 DS01–DS06）。

### 实盘数据

实盘数据指服务器运行时持续更新的行情 CSV：

- 海外虚拟货币：服务器项目的 `data/1d`、`data/1h`、`data/15m`。
- 国内期货/A股：服务器项目的 `data/<timeframe>/<symbol>.csv` 或数据泵实际输出目录。

实盘数据的新鲜度必须实时检查，不能引用旧日志判断当前状态。

### 模拟实盘数据

模拟实盘数据包括状态、账本、挂单、成交和事件：

- `runtime/fengji_radar/radar.csv`
- `runtime/fengji_radar/radar.json`
- `runtime/fengji_pending_orders/pending_orders.csv`
- `runtime/fengji_pending_orders/pending_orders.json`
- `runtime/fengji_pending_orders/events.jsonl`
- `runtime/fengji_pending_orders/fills.csv`
- `runtime/fengji_pending_orders/closed_trades.csv`
- `runtime/fengji_paper/state.json`
- `runtime/fengji_futures/state_futures_v2.json`
- `runtime/fengji_futures/trades_futures_astock.csv`

以上数据只代表模拟盘或模拟挂单，不代表真实成交。

### 回测数据

回测数据包括：

- 单定式回测输出：`results/ds01_*` 到 `results/ds09_*`。
- 总定式回测输出：`results/fengji_total_*`、`results/unified_*`、`results/plan_a_*`。
- A股板块回测输出：`results/fengji_total_a_stock_sectors_*_ds07_fixed`。
- 沙盒图：`results/sandbox`、`runtime/*sandbox*`。
- 审计结果：各回测目录中的 `bad_audits.csv`、`accepted_trades.csv`、`rejected_orders.csv`、`summary.csv`、`*_summary.csv` 等。

## 2. 数据文件位置

当前项目内主要数据位置：

```text
data/
├── 1d/                              本地少量虚拟货币日线 CSV
├── a_stock/                         A股 1D/60m 前复权缓存
├── a_stock_sina_smoke/               新浪 A股烟雾测试缓存
├── crypto_okx/                       OKX 虚拟货币 1D/1H/15m 缓存
├── market_data.sqlite                本地 SQLite 行情库
├── market_data_coverage.csv          数据库覆盖率导出
├── market_data_import_a_stock.csv    A股导入日志
├── market_data_import_crypto_okx.csv 虚拟货币导入日志
├── market_data_import_futures.csv    国内期货导入日志
└── sample_ohlcv.csv                  样例 OHLCV
```

当前项目内主要结果位置：

```text
results/
├── sandbox/
├── plan_a_crypto_180d/
├── plan_a_verify/
├── fengji_total_ds01_ds08_okx16_5y/
├── fengji_total_ds01_ds08_futures_15_5y/
├── fengji_total_a_stock_hot20_ds07_fixed/
├── fengji_total_a_stock_sectors_*_ds07_fixed/
├── ds01_* ... ds09_*
└── unified_* / fengji_total_pattern_*
```

当前项目内主要运行态位置：

```text
runtime/
├── fengji_radar/
├── fengji_pending_orders/
├── fengji_paper/
├── fengji_futures/
└── logs/
```

数据库说明文件：

```text
docs/LOCAL_MARKET_DATA_DB.md
src/market_data_store.py
```

## 3. 数据字段说明

### 标准 OHLCV 字段

峰极OS回测和模拟盘的标准 K 线字段为：

```text
date, open, high, low, close, volume
```

`packages/fengji_core/fengji_core/data.py` 要求读取后必须具备 `date/open/high/low/close/volume`；如果 CSV 中没有 `date`，会尝试把 `timestamp`、`datetime`、`time` 重命名为 `date`。

### 日期与时间

- `date`：标准时间字段，回测引擎优先使用。
- `datetime`：常见于原始数据或天勤数据返回；导入时通常转换为 `date` 或数据库 `dt`。
- `timestamp`：常见于 Binance 数据；回测读取时可重命名为 `date`。
- `dt`：SQLite `bars` 表内部时间字段。

时间解析必须显式完成，不能把字符串顺序当作时间顺序。

### 开高低收

- `open` / `开盘` / `开盘价`：开盘价。
- `high` / `最高` / `最高价`：最高价。
- `low` / `最低` / `最低价`：最低价。
- `close` / `收盘` / `收盘价`：收盘价。

导入数据库时，`src/market_data_store.py` 会把常见中英文字段映射为统一字段；若字段名乱码或无法识别，会按前六列位置兜底为 `datetime/open/high/low/close/volume`。

### 成交量、持仓量、结算价

- `volume` / `vol` / `成交量`：成交量；缺失时数据库导入可能填 0。
- `open_interest` / `持仓量`：当前标准 OHLCV 回测接口未统一要求；若原始期货文件存在，应作为扩展字段保留或另行导入，当前是否参与策略：待确认。
- `settle` / `settlement` / `结算价`：当前标准 OHLCV 回测接口未统一要求；若原始期货文件存在，当前是否参与风控或结算：待确认。

### symbol 与 timeframe

- `symbol`：品种代码或股票代码。SQLite 中 `bars` 表使用 `market + symbol + timeframe + dt` 作为主键。
- `timeframe`：周期。当前数据库工具支持别名归一到 `1D`、`1H`、`15m`、`5m` 等。
- `market`：SQLite 中使用 `CRYPTO`、`FUTURES`、`A_STOCK` 区分市场。

### 数据库表

`src/market_data_store.py` 当前核心表：

```text
instruments(market, symbol, name, source, ...)
bars(market, symbol, timeframe, dt, open, high, low, close, volume, source, ...)
```

## 4. 5分钟转60分钟规则

### 当前项目证据

当前扫描未发现明确的“5分钟 K线转换为 60分钟 K线”的专用转换脚本。

已发现的相关实现是：

- `src/market_data_store.py`：支持导入 `5m`、`15m`、`1H`、`1D` 等周期，但没有看到把 5m 重采样为 60m 的专用命令。
- `src/batch_backtest_ds07.py`：要求 H1/60m 文件，默认匹配 `*_60m.csv`。
- `src/batch_backtest_ds08.py`：要求 60m/H1 文件，默认匹配 `*_60m.csv`。
- `src/batch_backtest_ds09.py`：要求 M15 文件，默认匹配 `*15m*.csv`。
- `src/unified_whitelist_engine.py`：从 minute 目录中按文件名寻找 `_60m` 和 `15m`，不负责从 5m 自动合成。

因此当前正式结论：

```text
项目内未发现已冻结的 5m -> 60m 转换脚本。
60m/H1 当前应视为独立数据源、数据库导出或外部已处理 CSV。
```

### 如果后续需要实现

如用户确认要新增 5m 转 60m，必须先冻结市场会话规则，尤其是国内期货夜盘跨日问题。一般 OHLCV 聚合原则可以作为待确认草案：

```text
open   = 60分钟窗口内第一根 5m 的 open
high   = 60分钟窗口内 high 最大值
low    = 60分钟窗口内 low 最小值
close  = 60分钟窗口内最后一根 5m 的 close
volume = 60分钟窗口内 volume 求和
持仓量 = 通常取窗口最后一根，待确认
结算价 = 是否参与 60m 聚合，待确认
```

常见报错风险：

- 夜盘跨日导致 session_date 错误。
- 交易所午休、夜盘品种结束时间不同，不能用自然小时简单切分。
- 缺少 5m bar 导致 60m 不完整。
- CSV 编码或中文列名导致字段映射失败。
- 生成的 60m 文件名不符合 `_60m.csv` 匹配规则，DS07/DS08 找不到数据。

## 5. 回测统一规则

### 禁止未来函数污染

所有回测必须遵守：

- 峰极线确认必须有时间隔离，不能提前使用未确认的峰/极。
- 3-3/T+3 确认不能在确认之前用于开仓。
- 跨周期映射必须只使用当时已经可见的数据。
- 输出必须保留审计字段，例如 `future_violation`、`max_hardened_confirm_idx_used`、`bad_audits`、`os_log`。

### 信号确认延迟

- DS01-DS06 多数使用 D1 数据，信号应在对应 K 线确认后或价格触发时处理。
- DS07 使用 D1 + H1，D1 提供战略授权，H1 负责触发或并轨。
- DS08 使用 H1 五点结构。
- DS09 使用 D1 战略边界 + M15 二次攻击点火；第一次刺穿只锁定，不入场。

### 手续费、滑点、保证金

国内期货单定式/统一回测常见默认：

```text
initial_cash = 100000
lots = 1
commission_rate = 0.0001
slippage_ticks = 1
margin_rate = 由 futures_specs 按品种给出
```

虚拟货币总定式回测常见默认：

```text
initial_cash = 1000 USDT
margin_per_trade = 200 USDT
leverage = 2
fee_rate = 0.0005
slippage_rate = 0.0003
maintenance_margin_rate = 0.005
```

A股回测常见默认：

```text
initial_cash = 20000
只做多
100股整数倍
T+1 卖出
佣金 = 0.03%，最低 5 元
印花税 = 卖出 0.05%
过户费 = 双边 0.001%
滑点 = 单边 0.03%
```

以上是当前代码/文档中的工作口径，不代表真实账户最终规则；真实实盘必须另行确认券商、期货公司或交易所实际规则。

### 爆仓

虚拟货币批量回测中已有按保证金、杠杆和维持保证金率估算强平价的逻辑。国内期货和 A股完整爆仓/强平模型：待确认。

### 最大加仓次数与反向仓

当前总控常见规则：

- 同品种同方向最多 3 笔。
- 未全部平仓前不许开反仓。
- DS01 支持最多 3 次同方向开仓/加仓。

具体以 `unified_whitelist_engine.py`、挂单监控和各定式回测脚本当前参数为准。

### 国内期货、虚拟货币、股票差异

- 国内期货：多空均可，按手数、合约乘数、tick、保证金率、手续费和滑点估算。
- 虚拟货币：多空均可，按保证金、杠杆、手续费率、滑点率和维持保证金率估算。
- A股：当前回测只做多，T+1，100股整数倍，股票费用独立计算，无期货保证金和虚拟货币杠杆。

## 6. 九大定式回测状态

### 定式01 回测状态

状态：部分完整，仍需持续复核。

证据：

- `src/backtest_ds01.py`
- `src/batch_backtest_ds01.py`
- `src/batch_backtest_ds01_crypto.py`
- `tests/test_ds01.py`
- `results/ds01_*`

当前重点：左30线数按“启动棍水平方向向左30根K线内穿过峰极线段数 <= 2”执行，不是左侧 30 根峰极点数量。需要持续确认本地、国内服务器、海外服务器一致。

### 定式02 回测状态

状态：部分完整。

证据：

- `src/backtest_ds02.py`
- `src/batch_backtest_ds02.py`
- `src/plot_ds02_sandbox.py`
- `docs/DS02_CALIBRATION.md`
- `results/ds02_real_daily_futures`

待补：未看到独立 `tests/test_ds02.py`；DS02 是否完全属于收线确认型，以及挂单器如何接入，仍需补齐。

### 定式03 回测状态

状态：部分完整，近期有关键修正。

证据：

- `src/backtest_ds03.py`
- `src/batch_backtest_ds03.py`
- `src/plot_ds03_sandbox.py`
- `scripts/plot_live_ds03_sandbox.py`
- `scripts/plot_live_ds03_sandbox_svg.py`
- `tests/test_ds03.py`
- `docs/DS03_CALIBRATION.md`
- `results/ds03_real_daily_futures`

当前重点：active high/low 与合法假峰/假极触发必须符合峰极OS，重点案例包括 IOUSDT、ETHUSDT。

### 定式04 回测状态

状态：部分完整。

证据：

- `src/backtest_ds04.py`
- `src/batch_backtest_ds04.py`
- `src/plot_ds04_sandbox.py`
- `tests/test_radar_ds04.py`
- `scripts/check_ds04_fg_sa_20260526.py`
- `docs/DS04_CALIBRATION.md`
- `results/ds04_real_daily_futures`

当前重点：DS04 开仓逻辑是九大定式中不按 OS 阵营方向过滤的例外，但离场与防守仍必须使用 OS。玻璃、纯碱等案例需要继续沙盒图复核。

### 定式05 回测状态

状态：部分完整，近期有关键修正。

证据：

- `src/backtest_ds05.py`
- `src/batch_backtest_ds05.py`
- `src/batch_backtest_ds05_crypto.py`
- `src/plot_ds05_sandbox.py`
- `src/batch_plot_ds05_sandbox.py`
- `tests/test_ds05.py`
- `tests/test_radar_ds05.py`
- `docs/DS05_CALIBRATION.md`
- `results/ds05_*`

当前重点：K2 是可能形成“极”的位置，不要求靠近旧 active extreme，也不能把 K2 当作峰。红枣等案例需要继续复核。

### 定式06 回测状态

状态：规则已补齐，回测存在，仍需更多市场验证。

证据：

- `src/backtest_ds06.py`
- `src/batch_backtest_ds06.py`
- `src/plot_ds06_sandbox.py`
- `tests/test_radar_ds06.py`
- `docs/DS06_CALIBRATION.md`
- `results/ds06_real_daily_futures`

当前重点：外扩峰式已按转势授权 + D/E/F 外扩启动整理，但服务器模拟盘和更多市场覆盖仍需验证。

### 定式07 回测状态

状态：规则已补齐，双周期回测存在，仍需排查旧逻辑残留。

证据：

- `src/backtest_ds07.py`
- `src/batch_backtest_ds07.py`
- `src/plot_ds07_sandbox.py`
- `tests/test_radar_ds07.py`
- `docs/DS07_CALIBRATION.md`
- `docs/DS07_DRAFT.md`
- `results/ds07_real_60m_futures`
- `results/fengji_total_a_stock_*_ds07_fixed`

当前重点：D1 战略授权 + H1 同向延续或反向并轨；禁止恢复旧的“启动前 H1 必须已同阵营”窄逻辑。A股 60分钟历史不足限制 DS07 历史结论。

### 定式08 回测状态

状态：部分完整。

证据：

- `src/backtest_ds08.py`
- `src/batch_backtest_ds08.py`
- `src/plot_ds08_sandbox.py`
- `tests/test_radar_ds08.py`
- `docs/DS08_CALIBRATION.md`
- `results/ds08_real_60m_futures`

待补：五点结构、否认、确定、触发、撤销规则需要继续用案例和沙盒图验证。

### 定式09 回测状态

状态：核心规则已修正，回测存在，雷达/挂单/模拟盘全链路仍待补齐。

证据：

- `src/backtest_ds09.py`
- `src/batch_backtest_ds09.py`
- `src/plot_ds09_sandbox.py`
- `tests/test_ds09.py`
- `docs/DS09_CALIBRATION.md`
- `docs/DS09_DRAFT.md`
- `docs/DS09_IN_TOTAL_PATTERN.md`
- `results/ds09_*`

当前重点：股票式/A股专属版本等同九重天。D1 是天，M15 是针；第一次刺穿 D1 边界只锁定，必须等 M15 第一进攻峰、防守极、二次攻击才入场。缺少 M15 数据时只跳过 DS09，不影响 DS01-DS08。

## 7. 图形验证要求

每个争议信号、关键回测样本、模拟挂单触发和最新交易，都应尽量生成沙盒图。

沙盒图必须展示：

- K线。
- 峰极线。
- 红蓝阵营。
- 买点。
- 卖点。
- 止损点。
- 防守点。
- 挂单点。
- 最近交易特写。
- 若是跨周期定式，需要展示 D1/H1 或 D1/M15 的对应关系。

当前绘图脚本：

```text
src/plot_ds01_sandbox.py
src/plot_ds02_sandbox.py
src/plot_ds03_sandbox.py
src/plot_ds04_sandbox.py
src/plot_ds05_sandbox.py
src/plot_ds06_sandbox.py
src/plot_ds07_sandbox.py
src/plot_ds08_sandbox.py
src/plot_ds09_sandbox.py
src/plot_fengji_structure.py
scripts/plot_crypto_ds01_trade_sandbox.py
scripts/plot_live_ds03_sandbox.py
scripts/plot_live_ds03_sandbox_svg.py
```

验证输出应归档到：

```text
results/sandbox/
```

或对应回测结果目录下的图片子目录。

## 8. 已知问题

- `rg` 在当前环境执行时出现 Access denied，文件搜索可用 PowerShell `Select-String` / `Get-ChildItem` 替代。
- A股 60分钟历史覆盖不足，限制 DS07/DS08 的完整历史级结论。
- 项目内未发现已冻结的 5m -> 60m 转换脚本，不能假装已经实现。
- CSV 字段存在 `date`、`timestamp`、`datetime`、中文字段、乱码字段等多种口径，需要通过统一读取函数或数据库导入函数标准化。
- `open_interest`、`settle` 等期货扩展字段是否参与回测：待确认。
- `src/quant` 与 `packages/fengji_core` 存在双路径实现/转发关系，需要持续确认权威源，避免逻辑分叉。
- DS01、DS03、DS05、DS07、DS09 最近都有规则修正，服务器代码是否全部同步：待实时检查。
- 旧文档中存在 DS09 旧口径“D1 + M5”或“DS09 暂不纳入总定式”的历史表述，当前应以 `docs/FENGJI_TOTAL_PATTERN_SPEC.md` 和 `峰极OS_九大定式规则总纲.md` 的最新 DS09 口径为准。
- 服务器运行状态、数据新鲜度、模拟盘是否正常都属于时间敏感事实，必须实时检查。
- 回测结果中 `bad_audits=0` 只说明结构审计未发现违规，不等于策略可直接实盘。

## 9. 下一步任务

- [ ] 补齐 A股 60分钟历史数据，或明确 A股正式筛选先按 DS01-DS06 日线版。
- [ ] 确认是否需要开发 5m -> 60m 转换脚本；若需要，先冻结国内期货夜盘 session 规则。
- [ ] 建立统一数据新鲜度检查脚本：覆盖本地、国内服务器、国外服务器。
- [ ] 清理并统一 CSV 字段映射，把中文列名、timestamp、datetime、date 的处理写入测试。
- [ ] 明确 `open_interest` 和 `settle` 是否进入国内期货回测/风控。
- [ ] 对 DS01-DS09 每个定式补齐至少一个标准沙盒图案例。
- [ ] 对最近争议信号生成并归档沙盒图：RENDERUSDT、IOUSDT、ETHUSDT、DOGEUSDT、LTCUSDT、红枣、玻璃、纯碱。
- [ ] 继续 A股板块回测，复跑失败股票，归档结果目录和汇总 CSV。
- [ ] 对总定式回测输出统一保留 `accepted_trades.csv`、`rejected_orders.csv`、`bad_audits.csv`、`summary.csv`、`by_strategy.csv`。
- [ ] 每次更新数据源、回测规则或核心定式后，同步更新 `CHANGELOG.md`、`TODO.md` 和相关峰极OS规则文档。

