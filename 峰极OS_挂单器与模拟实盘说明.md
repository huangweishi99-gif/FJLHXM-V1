# 峰极OS_挂单器与模拟实盘说明.md

更新时间：2026-07-08

本文用于交接峰极OS总工程中的挂单器、模拟实盘、交易执行与日志审计逻辑。所有内容必须服从 `峰极OS_最高宪法.md`、`峰极OS_阵营转换判断.md`、`峰极OS_九大定式规则总纲.md`。本文只描述当前项目已有实现和待开发边界，不包含任何 API Key、Token、服务器密码、完整 webhook 或私钥。

补充复核：2026-07-08 已用 `scripts/audit_paper_ledger_contract.py` 固化模拟开仓、平仓、止损、费用滑点和账本字段契约；已用 `scripts/audit_pending_order_contract.py` 固化挂单触发与冲突撤单契约。

## 1. 挂单器目标

挂单器的目标不是提前真实下单，而是在峰极OS最高宪法下，把已经可预计算的九大定式触发价转换为“模拟挂单候选”，并在后续价格或K线触达时模拟成交、记录账本、发送通知、撤销冲突挂单。

挂单器解决的问题：

- 避免只靠固定间隔数据同步才发现信号，尽量把“价格达到即触发”的定式提前转成触发价。
- 让 DS01、DS03、DS05、DS07、DS08 等可价格触发的定式在模拟盘中更接近真实挂单效果。
- 统一记录每个挂单的 `order_id`、`setup_key`、定式、方向、触发价、止损、防守点、阵营、原因和距离。
- 触发一笔后，对同品种冲突挂单做撤销记录，避免同一盘面被多个定式重复污染。
- 保持模拟实盘和真实实盘隔离。当前代码是模拟触发与模拟账本，不是真实交易执行器。

## 2. 挂单器架构

### 2.1 信号输入

当前主要信号入口来自雷达结果：

- `runtime/fengji_radar/radar.json`
- `runtime/fengji_radar/radar.csv`

雷达由 `src/fengji_total_radar.py` 生成，包含品种、定式、周期、方向、状态、触发价、当前价、距离、止损、阵营、原因、`setup_key` 等字段。`src/fengji_radar_order_loop.py` 负责循环执行雷达生成和挂单生成，默认每 300 秒刷新一次。

### 2.2 阵营判断输入

挂单器本身不重新定义红蓝阵营。阵营必须由峰极OS底层和雷达层给出，并通过字段传递：

- `os_camp`
- `side`
- `trigger_price`
- `stop_price`
- `latest_time`
- `reason`
- `setup_key`

如果雷达层的峰极线、红蓝阵营、转势状态机错误，挂单器会继承错误结果。因此挂单器前置依赖是：峰极线正确、阵营正确、定式候选正确。

### 2.3 定式信号输入

`src/fengji_pending_orders.py` 当前默认只接收 `status == PENDING` 的雷达行，并默认纳入：

- `DS01`
- `DS03`
- `DS04`
- `DS05`
- `DS07`
- `DS08`
- `DS09`

DS02 当前更偏收线确认或占位逻辑，尚未完整接入价格型挂单器。DS06 外扩峰式规则已补齐，但当前默认挂单策略集合尚未包含 DS06，仍需专门接入验证。

### 2.4 风控模块

风控主要分两层：

- 挂单生成层：过滤距离过远的候选，默认 `--max-distance-pct 0.08`；生成稳定 `order_id` 和 `setup_key`。
- 触发监控层：检查同品种已有持仓、DS01最多开仓次数、同方向/反方向冲突、止损触发、手续费、滑点、保证金、杠杆或合约乘数。

海外虚拟货币监控使用 `initial_cash`、`margin_per_trade`、`leverage`、`fee_rate`、`slippage_rate` 估算模拟盈亏。国内期货/A股监控使用手数、合约乘数、手续费、滑点等本地参数估算模拟盈亏。

### 2.5 下单模块

当前下单模块是“模拟成交模块”，不是交易所真实下单模块：

- 海外虚拟货币：`src/fengji_pending_order_monitor.py` 读取实时价格快照或测试价格文件，触达触发价后记录模拟成交。
- 国内期货/A股：`src/fengji_futures_pending_order_monitor.py` 读取本地K线高低点，判断是否穿越触发价后记录模拟成交。

真实下单模块尚未开发。任何真实账户接入必须单独设计、人工确认、独立配置、独立权限、独立日志。

### 2.6 撤单模块

当前撤单是模拟撤单。`src/fengji_pending_order_monitor.py` 和 `src/fengji_futures_pending_order_monitor.py` 在挂单触发后，共用 `cancel_conflicting_orders` 逻辑，把同品种其他冲突挂单写入 `events.jsonl`，撤销原因使用 `conflict_after_fill`。

当前实现口径：

- 非 DS01 挂单成交后，同品种其他未成交挂单都会标记撤销，无论同向或反向。
- DS01 挂单成交后，同品种同方向 DS01 挂单保留，用于 DS01 同向连续开仓；同品种反向 DS01 和其他定式挂单撤销。
- 撤销状态写入 `cancelled_order_ids`；如果原挂单有 `setup_key`，同步写入 `cancelled_setup_keys`。
- 撤销事件包含 `event_type=cancel`、`cancel_reason=conflict_after_fill`、`filled_order_id`，用于后续审计。
- DS01 最多开仓次数当前默认 `max_ds01_entries = 3`；国内链路另有 `max_open_positions_per_symbol = 3`。

### 2.7 日志模块

当前主要日志和账本文件包括：

- `runtime/fengji_pending_orders/pending_orders.json`
- `runtime/fengji_pending_orders/pending_orders.csv`
- `runtime/fengji_pending_orders/state.json`
- `runtime/fengji_pending_orders/futures_pending_state.json`
- `runtime/fengji_pending_orders/fills.csv`
- `runtime/fengji_pending_orders/events.jsonl`
- `runtime/fengji_pending_orders/closed_trades.csv`
- `runtime/fengji_paper/state.json`
- `runtime/fengji_futures/state_futures_v2.json`
- `runtime/fengji_futures/trades_futures_astock.csv`

服务器运行时还可能存在 `paper_run.log`、`data_sync.log`、`pending_order_monitor.log` 等运行日志。运行状态必须实时检查，不能用旧日志当作当前事实。

### 2.8 模拟实盘模块

当前存在两条模拟实盘链路：

- 主模拟盘：`src/峰极总定式01-08策略海外模拟实盘.py`，主要处理海外虚拟货币 DS01-DS08，当前文本和启动信息仍是 DS01-DS08。
- 挂单监控模拟盘：`src/fengji_pending_order_monitor.py` 与 `src/fengji_futures_pending_order_monitor.py`，分别面向海外虚拟货币和国内期货/A股的模拟挂单触发。

注意：主模拟盘中 `PENDING_MANAGED_STRATEGIES` 当前为 DS01、DS03、DS05、DS07、DS08；`DIRECT_OPEN_STRATEGIES` 为剩余总定式。DS09 尚未完整并入这条 DS01-DS08 主模拟盘链路。

## 3. 挂单器与九大定式关系

所有定式必须先通过峰极OS最高宪法、峰极线、阵营转换和定式规则生成合法候选，挂单器只消费合法候选，不负责修正错误策略。

### DS01 挫式棍

当前可进入挂单器。核心是红阵营向上突破启动棍高点或蓝阵营向下跌破启动棍低点，并满足左线约束。根据当前用户确认，左30线数规则应按“小于等于2段峰极连线可开仓”执行，具体以 `峰极OS_九大定式规则总纲.md` 和代码测试为准。

挂单器应支持 DS01 同方向最多开仓次数限制，当前监控默认 `max_ds01_entries = 3`。

### DS02 阴阳相吃式

当前资料显示 DS02 更偏收线确认型策略，雷达中可能存在占位或 `CONFIRM_ON_CLOSE` 类状态。挂单器尚未完整实现 DS02 的价格型挂单逻辑。

当前状态：待补齐。

### DS03 二四棒式

当前可进入挂单器。核心是红阵营突破有效进攻峰或合法“假峰”，蓝阵营跌破有效进攻低点或合法“假极/假低点”。挂单触发价来自雷达层的 `trigger_price`，止损来自对应防守点。

已知重点案例：

- IOUSDT 2026-05-26/2026-05-27：红阵营突破合法假峰。
- ETHUSDT 2026-05-27：蓝阵营跌破 active low。

### DS04 夹棍式

当前可由雷达输出并进入默认挂单集合，但需要注意 DS04 的特殊性：根据当前上下文，DS04 开仓逻辑是九大定式中唯一不要求用 OS 阵营方向过滤的例外；但离场、防守和后续管理仍必须服从峰极OS。

DS04 的“预挂单”如何跨市场处理仍需继续验证，尤其是国内期货/A股开盘跳空、夜盘与无夜盘差异。

当前状态：部分接入，需继续验证。

### DS05 指形式

当前可进入挂单器。用户已明确：DS05 的 K2 是可能形成“极”的位置，不要求靠近旧 active extreme，也不能把 K2 当作“峰”。峰永远是进攻方向，极永远是防守点和转势关键。

挂单器应消费 DS05 雷达输出的 K3 触发价和防守极，不得恢复旧的“K2 靠近当前红极/蓝极”错误逻辑。

### DS06 外扩峰式

规则总纲已补为转势授权后等待 D/E/F 或 d/e/f 外扩启动。当前雷达可预览 DS06 的外部突破候选，但挂单器默认策略集合尚未包含 DS06。

当前状态：规则已补齐，挂单器接入待验证/待补齐。

### DS07 共振式

当前可进入挂单器。现行口径是 D1 战略授权 + H1 通过 DS03 二四棒同向延续触发（`LONG/SHORT_CONTINUE`），要求启动前已同阵营（`prev_h1_camp==1`）；反向并轨已废止。

挂单器使用 H1 触发价作为挂单价，D1/H1 阵营关系通过雷达 `os_camp` 或 `reason` 审计。

### DS08 否认确定式

当前可进入挂单器。现有雷达可输出五点结构相关候选，挂单器根据触发价模拟成交。

当前状态：已接入挂单器，但五点结构、否认、确定、撤销规则仍需继续用案例和沙盒图验证。

### DS09 股票式 / A股专属版本 / 九重天

DS09 正确规则已由用户确认：D1 是天，M15 是针。D1 提供战略能量，M15 提供精确点火。

多头：D1 红阵营，昨日阴线，今日第一次 M15 high > 昨日 high 只锁定；锁定后寻找第一 M15 red_peak；再等待 red_ext 防守极；随后二次 high > red_peak 才入场做多，止损守 red_ext 且只允许上移。

空头：D1 蓝阵营，昨日阳线，今日第一次 M15 low < 昨日 low 只锁定；锁定后寻找第一 M15 blue_peak；再等待 blue_ext 防守极；随后二次 low < blue_peak 才入场做空，止损守 blue_ext 且只允许下移。

当前状态：规则已确认，但 DS09 雷达、挂单器、模拟盘全链路接入仍待开发/待补齐。不得把旧的“D1 不提供 OS 阵营方向”或“第一次刺穿即入场”逻辑写回代码。

## 4. 模拟实盘运行流程

### 4.1 读取数据

海外虚拟货币链路：

- 数据泵更新本地 `data` 目录。
- 主模拟盘读取 D1/H1/15m 等本地K线。
- 挂单监控可读取 Binance 现价接口，也可通过 `--price-file` 使用测试价格快照。
- 触发口径：多头现价 `>= trigger_price`，空头现价 `<= trigger_price`。

国内期货/A股链路：

- 数据泵更新本地 `data` 目录。
- 国内挂单监控读取 `data/<timeframe>/<symbol>.csv`。
- 默认按 `15m,1h,1d` 顺序读取最新K线，用高低点判断是否触达挂单价。
- 触发口径：多头 K 线 `high >= trigger_price`，空头 K 线 `low <= trigger_price`。
- 国内期货/A股链路按市场交易时段由数据泵与计划任务控制；挂单触发规则与海外共享订单状态、冲突撤单、`setup_key` 去重等核心契约，但价格来源和交易时间窗口不同。

### 4.2 生成信号

`src/fengji_total_radar.py` 扫描数据，输出雷达候选。候选必须包含：

- 品种
- 定式
- 周期
- 方向
- 状态
- 当前价
- 触发价
- 止损价
- 峰极阵营
- 理由
- `setup_key`

### 4.3 模拟挂单

`src/fengji_pending_orders.py` 从雷达 JSON/CSV 中筛选 `PENDING` 候选，按定式优先级和距离生成挂单清单：

- `pending_orders.json`
- `pending_orders.csv`

默认距离过滤为 8%。超过距离的候选不会进入挂单清单，除非运行时修改参数。

### 4.4 模拟成交

海外虚拟货币：

- `src/fengji_pending_order_monitor.py` 读取挂单清单。
- 拉取现价或读取测试价格快照。
- 多头价格大于等于触发价视为触发；空头价格小于等于触发价视为触发。
- 记录 `fills.csv` 和 `events.jsonl`。
- 更新 `runtime/fengji_paper/state.json`。

国内期货/A股：

- `src/fengji_futures_pending_order_monitor.py` 读取挂单清单。
- 读取本地最新K线的 high/low。
- K线范围穿越触发价视为模拟触发。
- 更新 `runtime/fengji_futures/state_futures_v2.json`。
- 记录 `runtime/fengji_futures/trades_futures_astock.csv`。

### 4.5 模拟平仓

当前平仓主要由止损触发处理：

- 多头：K线 low 或现价触及防守止损，模拟止损平仓。
- 空头：K线 high 或现价触及防守止损，模拟止损平仓。
- 平仓记录写入 `closed_trades.csv`、`events.jsonl` 和模拟账本。

后续需要继续确认各定式移动防守点、止盈、反向信号退出、同品种冲突撤单等规则是否全部接入。

### 4.6 记录日志

每次雷达刷新、挂单生成、触发、跳过、撤销、平仓都必须有可审计记录。最低要求：

- 触发前能看到候选为什么产生。
- 触发时能看到触发价、最新价、方向、阵营、防守点。
- 触发后能看到是否撤销其他挂单。
- 平仓时能看到退出原因、费用滑点、净盈亏。

### 4.7 与真实实盘隔离

当前项目中的挂单器和模拟盘只做模拟，不真实下单。真实交易接入必须单独开发，不得复用模拟配置直接连接真实账户。

真实实盘接入前必须满足：

- 交易 API Key 只放环境变量或本地私密配置。
- 真实账户权限与模拟账户权限隔离。
- 每个市场有独立风控参数。
- 每个真实下单动作有人工二次确认或明确授权流程。
- 每笔真实下单、撤单、成交、拒单均有不可覆盖日志。

## 5. 风控与安全

### 5.1 敏感信息

禁止把以下内容写入代码、文档、日志或聊天输出：

- API Key
- Secret
- Token
- 服务器密码
- 私钥
- 完整 webhook
- 未脱敏服务器访问凭证

当前项目中存在敏感信息，需移动到本地私密配置或环境变量。本文不展示任何具体敏感内容。

### 5.2 账户隔离

- 模拟账户和真实账户必须隔离。
- 国内服务器和海外服务器权限必须隔离。
- 国内期货、A股、海外虚拟货币不得混用资金、保证金、滑点、手续费、交易时间规则。
- 当前所有挂单触发均按“只模拟，不真实下单”理解。

### 5.3 爆仓、滑点、手续费、保证金

海外虚拟货币模拟盘当前显式使用：

- 初始本金
- 单笔保证金
- 杠杆
- 手续费率
- 滑点率

国内期货/A股模拟盘当前显式使用：

- 手数
- 合约乘数或市场乘数
- 手续费率
- 滑点率
- 单品种最大持仓数

爆仓逻辑需要继续确认。若进入真实实盘，必须单独实现逐仓/全仓、强平价、维持保证金、交易所风控和异常价格保护，不能只用当前模拟盈亏估算。

### 5.5 模拟账本字段与盈亏公式（2026-07-08 复核）

当前海外虚拟货币挂单监控入口为 `src/fengji_pending_order_monitor.py`，默认资金参数为：

- `--initial-cash 1000.0`
- `--margin-per-trade 200.0`
- `--leverage 2.0`
- `--fee-rate 0.0005`
- `--slippage-rate 0.0003`

海外模拟开仓字段至少包含：`source`、`trade_key`、`order_id`、`symbol`、`strategy_id`、`side`、`direction`、`entry_time`、`entry_price`、`initial_stop`、`current_stop`、`units`、`entries`、`legs`、`margin`、`leverage`、`notional`、`virtual_initial_cash`。其中 `notional = margin * leverage`。

海外模拟平仓字段至少包含：`closed_at`、`source`、`symbol`、`strategy_id`、`direction`、`side`、`entry_time`、`exit_time`、`entry_price`、`exit_price`、`initial_stop`、`exit_reason`、`entries`、`margin`、`leverage`、`notional`、`gross_pnl`、`costs`、`net_pnl`、`return_on_symbol_cash`、`equity_after`、`order_id`。当前公式为：`gross_pnl = notional * side * (exit_price - entry_price) / entry_price`，`costs = notional * (fee_rate + slippage_rate) * 2`，`net_pnl = gross_pnl - costs`。

当前国内期货/A股挂单监控入口为 `src/fengji_futures_pending_order_monitor.py`，默认资金参数为：

- `--lots 1`
- `--fee-rate 0.0001`
- `--slippage-rate 0.0002`

国内模拟开仓字段至少包含：`key`、`source`、`order_id`、`setup_key`、`symbol`、`strategy_id`、`side`、`direction`、`entry_time`、`entry_price`、`trigger_price`、`initial_stop`、`current_stop`、`stop_price`、`lots`、`multiplier`、`created_at`、`entry_bar`、`risk_rule`、`timeframe`、`setup`。

国内模拟交易 CSV 字段至少包含：`event_time`、`symbol`、`strategy_id`、`side`、`action`、`lots`、`entry_time`、`entry_price`、`exit_time`、`exit_price`、`net_pnl`、`equity`、`reason`、`trade_key`、`run_id`；平仓记录另含 `gross_pnl`、`costs`。当前公式为：`gross_pnl = (exit_price - entry_price) * side * multiplier * lots`，`costs = (entry_price + exit_price) * multiplier * lots * (fee_rate + slippage_rate)`，`net_pnl = gross_pnl - costs`。

止损触发口径：海外多头现价或止损 K 线触及/跌破 `current_stop` 或 `initial_stop` 平仓，空头现价或止损 K 线触及/突破止损平仓；国内多头按 K 线 `low <= stop`，空头按 K 线 `high >= stop`。当前退出原因主要为 `stop` 或止损 K 线派生原因；止盈、反向信号退出、爆仓和交易所拒单仍属待设计范围。

### 5.4 实盘操作确认

任何真实下单、真实撤单、真实账户资金查询、真实 API 权限修改，都必须先向用户明确说明操作内容、账户范围、风险和回滚方式，并取得确认。

## 6. 当前项目相关文件

### 6.1 雷达与挂单生成

- `src/fengji_total_radar.py`：峰极总定式雷达，生成 `runtime/fengji_radar/radar.csv/json`。
- `src/fengji_pending_orders.py`：把雷达候选转换为挂单清单，输出 `pending_orders.csv/json`。
- `src/fengji_radar_order_loop.py`：循环执行雷达刷新和挂单生成，默认 300 秒。

### 6.2 海外虚拟货币模拟实盘

- `src/峰极总定式01-08策略海外模拟实盘.py`：海外虚拟货币 DS01-DS08 主模拟盘入口，当前仍是 DS01-DS08 文本口径。
- `src/fengji_pending_order_monitor.py`：海外虚拟货币挂单触发监控，使用现价或测试价格文件模拟触发。
- `data_manager.py`：海外虚拟货币数据同步入口。
- `config/峰极总定式策略模拟实盘.config.example.json`：模拟盘配置样例，必须保持占位符，不得写真实密钥。

### 6.3 国内期货/A股模拟实盘

- `data_manager_futures.py`：国内期货/A股数据管理入口。
- `src/fengji_futures_pending_order_monitor.py`：国内期货/A股挂单触发监控，使用本地K线 high/low 模拟触发。
- `src/峰极总定式01-08国内期货A股模拟实盘.py`：国内期货/A股模拟盘入口，若本地或服务器存在，需按当前项目实际文件复核。
- `商业终端_Dash.py`：商业终端看板，若存在，需确认其读取的账本和状态文件与当前模拟盘一致。

### 6.4 核心规则与测试

- `峰极OS_最高宪法.md`：最高规则文件。
- `峰极OS_阵营转换判断.md`：红蓝阵营与转势状态机交接文件。
- `峰极OS_九大定式规则总纲.md`：DS01-DS09 规则总纲。
- `packages/fengji_core/fengji_core/`：核心包实现，需确认与 `src/quant` 是否存在双实现不同步。
- `tests/test_pending_orders.py`：挂单生成测试。
- `tests/test_futures_pending_orders.py`：国内期货/A股挂单监控测试。
- `tests/test_radar_ds05.py`、`tests/test_radar_ds04.py`、`tests/test_radar_ds06.py`、`tests/test_radar_ds07.py`、`tests/test_radar_ds08.py`：雷达相关测试。

### 6.5 运行脚本与服务器辅助

- `scripts/`：包含若干服务器重启、同步、检查脚本。存在敏感信息，需移动到本地私密配置或环境变量。
- `sync_src_to_server.ps1`：本地到服务器同步脚本，使用前必须确认不上传密钥或完整 webhook。
- `run_data_manager_futures.ps1`、`run_data_manager_futures.cmd`：国内数据管理启动脚本。

## 7. 当前状态

### 7.1 已完成

- 已有雷达到挂单清单的基础链路：`fengji_total_radar.py` -> `fengji_pending_orders.py`。
- 已有循环刷新入口：`fengji_radar_order_loop.py`。
- 已有海外虚拟货币模拟挂单监控：`fengji_pending_order_monitor.py`。
- 已有国内期货/A股模拟挂单监控：`fengji_futures_pending_order_monitor.py`。
- 已有模拟成交、模拟止损、模拟账本、事件日志、冲突撤单记录。
- DS01、DS03、DS04、DS05、DS07、DS08、DS09 已在挂单器默认集合中；DS09 全链路仍需按其 M15 点火规则继续验收。

### 7.2 未完成

- DS09 九重天虽已在默认挂单集合中，但雷达、挂单器、模拟盘全链路仍需继续按固定样本验收。
- DS02 阴阳相吃式尚未形成明确价格型挂单处理。
- DS06 外扩峰式规则已补齐，但未进入默认挂单集合，接入仍需验证。
- 真实交易下单器未开发，当前只有模拟触发。
- 爆仓、交易所拒单、滑点放大、断网重试、行情异常保护仍需单独设计。
- 国内期货日盘/夜盘、A股无夜盘的自动运行窗口仍需固化到任务调度或启动脚本。

### 7.3 待验证

- 本地、国内服务器、海外服务器是否都已经同步最新 DS01、DS03、DS05、DS07、DS09 规则。
- 当前同品种冲突撤单实现已由 `audit_pending_order_contract.py` 固化；是否需要改成其他最终规则仍待用户另行裁定。
- DS04 夹棍式在国内期货玻璃、纯碱等案例中是否能准确触发。
- RENDERUSDT、IOUSDT、ETHUSDT、DOGEUSDT、LTCUSDT 等争议案例是否均可通过沙盒图复核。
- `packages/fengji_core` 与 `src/quant` 的权威源关系。

### 7.4 风险点

- 旧 DS07、旧 DS05、旧 DS09、旧左30理解可能残留在文档、脚本或服务器代码中。
- 雷达错误会直接污染挂单器，挂单器不会自动修复峰极线或阵营错误。
- 服务器状态随时间变化，必须实时 SSH 检查。
- 仓库中存在敏感信息迹象，需继续脱敏，后续文档不得复制具体内容。
- 当前模拟盘不是实盘交易系统，不能直接接入真实账户。

