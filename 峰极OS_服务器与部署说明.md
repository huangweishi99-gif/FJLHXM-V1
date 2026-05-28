# 峰极OS_服务器与部署说明.md

更新时间：2026-05-27

本文用于交接峰极OS总工程的国内服务器、国外服务器、部署脚本、模拟实盘运行环境和安全边界。本文不记录服务器密码、API Key、Token、交易所密钥、数据源密码、完整 webhook、私钥、服务器 IP、域名或登录用户名。所有敏感连接信息均以“见本地私密配置文件/环境变量/服务器控制台”处理。

## 1. 部署目标

峰极OS总工程需要国内服务器和国外服务器分工运行，原因如下：

- 海外虚拟货币数据和模拟盘更适合部署在国外服务器，减少交易所行情接口访问限制和网络延迟。
- 国内期货/A股数据、天勤数据源、Windows Server 运行环境和本地看板更适合部署在国内服务器。
- 本地开发机用于代码修改、规则沉淀、回测、沙盒图和交接文档；服务器用于长期运行数据泵、雷达、挂单监控、模拟实盘和通知。
- 当前部署目标是“模拟实盘 + 模拟挂单 + 数据监控”，不是自动真实下单。
- 每次回答“服务器是否正常运行”都必须实时检查进程、日志和数据新鲜度，不能引用旧日志或旧聊天作为当前事实。

## 2. 国内服务器

### 2.1 用途

国内服务器用于运行国内期货/A股相关链路：

- 国内期货数据泵。
- 国内期货/A股模拟实盘。
- 峰极总定式雷达循环。
- 国内期货/A股模拟挂单监控。
- 商业终端 Dash 看板。
- 国内期货日盘/夜盘运行窗口管理。
- A股无夜盘的运行区分。

服务器连接地址、登录用户、SSH 密钥、密码、控制台入口均不写入本文，见本地私密配置文件、用户本机 SSH 配置或云服务器控制台。

### 2.2 运行模块

国内服务器当前相关模块包括：

- `data_manager_futures.py`：国内期货数据泵，使用天勤连接，已包含交易时段窗口控制。
- `src/fengji_radar_order_loop.py`：雷达刷新与挂单生成循环。
- `src/fengji_futures_pending_order_monitor.py`：国内期货/A股模拟挂单触发监控。
- `峰极总定式01-08国内期货A股模拟实盘.py`：国内期货/A股模拟实盘主入口，服务器实际文件名需以服务器目录为准。
- `商业终端_Dash.py`：商业终端看板，服务器实际文件名需以服务器目录为准。

### 2.3 数据来源

当前国内期货数据泵依据 `data_manager_futures.py`：

- 数据源：天勤。
- 数据源账号、密码必须通过环境变量或服务器本地私密配置提供。
- 期货市场默认按开盘前 30 分钟开始、收盘后停止的窗口运行。
- 日盘、夜盘窗口已在代码中有基础控制。
- A股无夜盘；若未来单独运行 A股数据泵，需用独立市场模式和独立时间表。

注意：当前代码中存在数据源账号类默认配置痕迹，需后续移动到环境变量或服务器本地私密配置，不应继续保留在可提交代码中。

### 2.4 是否用于模拟实盘

是。国内服务器用于国内期货/A股模拟实盘、模拟挂单触发、模拟账本和通知。

当前相关状态文件和日志一般位于服务器运行态目录，具体路径见服务器本地部署目录。常见文件包括：

- `runtime/fengji_futures/state_futures_v2.json`
- `runtime/fengji_futures/trades_futures_astock.csv`
- `runtime/fengji_pending_orders/pending_orders.json`
- `runtime/fengji_pending_orders/futures_pending_state.json`
- `runtime/fengji_pending_orders/events.jsonl`
- `runtime/logs/*.log`

### 2.5 是否用于真实实盘

当前不用于真实实盘。所有国内链路必须按“只模拟，不真实下单”理解。

如果未来接入真实实盘，必须单独开发真实交易执行器，单独配置账户权限，单独进行人工确认和风控验收，不能直接把当前模拟挂单监控改成真实下单。

### 2.6 当前状态

根据项目文件，国内服务器部署链路已存在，包含启动、重启、检查、SSH 修复和 OpenSSH 安装脚本。

当前实时运行状态：待实时 SSH 检查。本文不把历史日志作为当前状态。

### 2.7 敏感连接信息存放位置

国内服务器敏感信息只允许存放在：

- 用户本机 SSH 配置。
- 本地私密配置文件。
- 服务器环境变量。
- 云服务器控制台。
- 服务器本地不提交的私密配置文件。

禁止写入仓库 Markdown、代码、脚本模板、日志输出和聊天回复。

## 3. 国外服务器

### 3.1 用途

国外服务器用于运行海外虚拟货币链路：

- 虚拟货币数据泵。
- 峰极总定式海外虚拟货币模拟实盘。
- 峰极总定式雷达循环。
- 虚拟货币模拟挂单监控。
- 飞书通知或其他通知通道。

服务器连接地址、登录用户、SSH 密钥、密码、控制台入口均不写入本文，见本地私密配置文件、用户本机 SSH 配置或云服务器控制台。

### 3.2 运行模块

国外服务器当前相关模块包括：

- `data_manager.py`：虚拟货币数据同步，按 1d、1h、15m 周期同步本地 CSV。
- `src/峰极总定式01-08策略海外模拟实盘.py`：海外虚拟货币主模拟盘入口。
- `src/fengji_radar_order_loop.py`：雷达刷新与挂单生成循环。
- `src/fengji_pending_order_monitor.py`：虚拟货币模拟挂单触发监控。
- `src/fengji_total_radar.py`：生成 `runtime/fengji_radar/radar.csv/json`。
- `src/fengji_pending_orders.py`：生成 `runtime/fengji_pending_orders/pending_orders.csv/json`。

### 3.3 数据来源

当前国外服务器虚拟货币数据泵依据 `data_manager.py`：

- 数据源：Binance 行情接口。
- 周期：`1d`、`1h`、`15m`。
- 数据目录：服务器项目目录下的 `data`。
- 默认循环：每轮同步结束后等待 10 分钟。

模拟挂单监控依据 `src/fengji_pending_order_monitor.py`：

- 读取 `runtime/fengji_pending_orders/pending_orders.json`。
- 拉取现价或读取测试价格文件。
- 触发后写入模拟成交、事件日志和模拟账本。

### 3.4 是否用于模拟实盘

是。国外服务器用于海外虚拟货币模拟实盘、模拟挂单触发、模拟账本和通知。

常见运行态文件包括：

- `paper_run.log`
- `data_sync.log`
- `radar_order_loop.log`
- `pending_order_monitor.log`
- `runtime/fengji_paper/state.json`
- `runtime/fengji_pending_orders/state.json`
- `runtime/fengji_pending_orders/fills.csv`
- `runtime/fengji_pending_orders/events.jsonl`
- `runtime/fengji_pending_orders/closed_trades.csv`

### 3.5 是否用于真实实盘

当前不用于真实实盘。国外服务器当前链路只允许模拟盘和模拟挂单触发。

如果未来接入交易所真实账户，必须单独建立：

- 真实交易执行器。
- 只读/交易权限拆分。
- API Key 环境变量。
- 风控阈值。
- 人工二次确认流程。
- 异常撤单与断线保护。

### 3.6 当前状态

根据项目文件，国外服务器部署链路已存在，包含源码同步脚本和运行时重启脚本。

当前实时运行状态：待实时 SSH 检查。本文不把历史日志作为当前状态。

### 3.7 敏感连接信息存放位置

国外服务器敏感信息只允许存放在：

- 用户本机 SSH 配置。
- 本地私密配置文件。
- 服务器环境变量。
- 云服务器控制台。
- 服务器本地不提交的私密配置文件。

示例：通知 webhook 应放在服务器运行态私密环境文件或环境变量中，不得写入仓库脚本。

## 4. 环境变量与私密配置

以下信息必须放在环境变量、本地私密配置文件、服务器本地不提交配置或云服务器控制台中：

- API Key。
- Secret。
- Token。
- 服务器密码。
- SSH 私钥。
- 完整 webhook。
- 交易所密钥。
- 数据源账号与密码。
- 飞书机器人 webhook。
- 云服务器控制台访问凭证。
- 任何带有登录权限、交易权限、资金权限的信息。

当前项目中应使用或保留的环境变量名示例：

- `FEISHU_WEBHOOK`：海外虚拟货币模拟盘/挂单监控通知。
- `FENGJI_FEISHU_WEBHOOK`：国内期货/A股挂单监控通知。
- `TQ_PHONE`：天勤账号标识，必须由环境变量或私密配置提供。
- `TQ_PASS`：天勤密码，必须由环境变量或私密配置提供。
- `MARKET_MODE`：国内数据泵市场模式，例如期货或 A股模式。

环境变量名本身可以写入文档；环境变量值严禁写入文档。

## 5. 启动与停止流程

### 5.1 国内服务器启动

推荐入口以服务器实际部署目录为准。项目中已有脚本：

- `scripts/start_factory_ascii.bat`：国内服务器启动工厂；会停止匹配的旧进程，再启动数据泵、国内期货/A股模拟盘、雷达循环、挂单监控和 Dash。
- `run_data_manager_futures.cmd`：启动国内期货数据泵。
- `run_data_manager_futures.ps1`：国内期货数据泵 PowerShell 入口，写入数据泵运行日志和错误日志。
- `scripts/run_futures_radar_loop.cmd`：启动国内雷达循环。
- `scripts/run_futures_pending_monitor.cmd`：启动国内期货/A股模拟挂单监控。
- `scripts/run_futures_astock_paper_ascii.cmd`：启动国内期货/A股模拟盘包装入口，具体调用服务器本地模拟盘脚本。

注意：这些脚本内部包含服务器本地部署路径，视为部署配置；不要把连接凭证或真实 webhook 写入脚本。

### 5.2 国内服务器停止

当前没有独立的正式停止脚本。已有启动/重启脚本会按进程命令行关键字停止旧进程，再重新启动。

手动停止时应在服务器上按模块确认后停止：

- 数据泵：匹配 `data_manager_futures`。
- 国内模拟盘：匹配国内期货/A股模拟实盘文件名。
- 雷达循环：匹配 `fengji_radar_order_loop.py`。
- 挂单监控：匹配 `fengji_futures_pending_order_monitor.py`。
- Dash：匹配 `Dash.py`。

停止前必须确认不是用户正在查看或调试的前台进程。

### 5.3 国内服务器重启与检查

已有脚本：

- `scripts/restart_domestic_futures_runtime.ps1`：重启国内模拟盘、雷达循环和挂单监控；不等同于完整启动工厂，数据泵和 Dash 是否启动需另查。
- `scripts/restart_domestic_radar_loop.ps1`：只重启国内雷达循环。
- `check_domestic_paper_trading.ps1`：通过 SSH 检查国内服务器模拟盘状态、状态文件、事件、日志和数据泵进程。
- `scripts/check_domestic_runtime_status.ps1`：在国内服务器本地检查进程和日志。

排查时优先看：

- 进程是否存在。
- 状态文件更新时间是否新鲜。
- 运行日志是否持续更新。
- 错误日志是否有新异常。
- 数据目录最新 CSV 修改时间是否接近市场更新窗口。

### 5.4 国外服务器启动

已有脚本：

- `scripts/restart_overseas_runtime.sh`：在国外服务器项目目录执行，重启雷达循环、虚拟货币模拟挂单监控和海外主模拟盘。
- `sync_src_to_server.ps1`：本地打包 `src` 并同步到国外服务器，远端会备份旧 `src` 后解压新代码。

注意：

- `scripts/restart_overseas_runtime.sh` 当前不负责启动 `data_manager.py`，只在最终进程检查中包含数据泵关键字。国外数据泵是否由单独守护进程、手动命令或其他任务管理：待确认。
- `sync_src_to_server.ps1` 属于代码同步工具，不是运行状态检查工具。同步后需要重启相关进程才能加载新代码。

### 5.5 国外服务器停止

`scripts/restart_overseas_runtime.sh` 会先停止匹配的雷达循环、挂单监控和海外主模拟盘进程，然后再启动。若只想停止而不启动，需要在服务器上人工执行进程停止命令，并逐项确认：

- `fengji_radar_order_loop.py`
- `fengji_pending_order_monitor.py`
- `峰极总定式01-08策略海外模拟实盘.py`
- `data_manager.py`，若由当前会话管理。

当前没有独立的国外服务器停止脚本：待补齐。

### 5.6 查看日志

国内服务器常见日志：

- `runtime/logs/data_manager_futures_run.log`
- `runtime/logs/data_manager_futures_err.log`
- `runtime/logs/paper_futures_run.log`
- `runtime/logs/paper_futures_err.log`
- `runtime/logs/futures_radar_order_loop.log`
- `runtime/logs/futures_radar_order_loop_err.log`
- `runtime/logs/futures_pending_order_monitor.log`
- `runtime/logs/futures_pending_order_monitor_err.log`

国外服务器常见日志：

- `data_sync.log`
- `paper_run.log`
- `radar_order_loop.log`
- `pending_order_monitor.log`

查看日志时只输出必要片段。若日志中出现 webhook、Token、密码、账号、密钥或服务器连接信息，必须先脱敏。

### 5.7 排查异常

排查顺序：

1. 检查服务器是否能 SSH 连通；连接信息见本地私密配置或云控制台。
2. 检查数据泵进程是否运行。
3. 检查数据文件最新修改时间。
4. 检查雷达循环进程和 `runtime/fengji_radar/radar.csv/json` 更新时间。
5. 检查挂单文件 `runtime/fengji_pending_orders/pending_orders.csv/json` 更新时间。
6. 检查挂单监控进程和 `events.jsonl`、`fills.csv`、`closed_trades.csv`。
7. 检查主模拟盘状态文件和日志。
8. 检查错误日志。
9. 若刚同步过代码，确认进程已经重启。
10. 若策略行为异常，生成沙盒图复核峰极线、阵营、定式、买点、卖点、防守点和挂单点。

## 6. 安全红线

绝对禁止：

- 把服务器密码写入代码、Markdown、脚本、日志或聊天输出。
- 把 API Key、Secret、Token、交易所密钥、数据源密码写入仓库。
- 把完整 webhook 写入仓库。
- 把 SSH 私钥写入仓库。
- 在文档中明文写服务器 IP、域名、登录用户名或控制台入口。
- 把模拟盘脚本直接改成真实下单脚本。
- 未经用户明确确认就执行真实下单、真实撤单、真实账户资金查询或 API 权限修改。
- 用旧日志判断当前服务器状态。
- 同步代码前不备份远端关键目录。
- 在服务器上批量删除未知文件。
- 把国内期货、A股、海外虚拟货币的交易时间、风控参数、手续费、滑点、保证金规则混用。
- 绕过 `峰极OS_最高宪法.md`、阵营转换和九大定式规则直接部署策略。

已发现项目中存在敏感信息痕迹，需移动到本地私密配置或环境变量；后续提交前必须清理。

## 7. 当前待完成事项

- [ ] 实时 SSH 检查国内服务器数据泵、模拟盘、雷达循环、挂单监控和 Dash 是否正常运行。
- [ ] 实时 SSH 检查国外服务器数据泵、主模拟盘、雷达循环、挂单监控是否正常运行。
- [ ] 确认国内服务器和国外服务器代码版本与本地最新 DS01、DS03、DS05、DS07、DS09 规则一致。
- [ ] 把脚本中的 webhook、服务器连接默认值、数据源账号默认值等敏感信息移出仓库，改为环境变量或本地私密配置。
- [ ] 为国外服务器补齐独立数据泵启动/停止/守护说明。
- [ ] 为国内服务器补齐独立停止脚本，避免只能通过重启脚本停止旧进程。
- [ ] 明确国内期货日盘/夜盘数据泵自动运行表；A股无夜盘。
- [ ] 明确服务器守护方式：计划任务、systemd、screen/tmux、nohup、Windows 启动项或手动脚本。
- [ ] 建立统一健康检查输出：进程、日志、数据新鲜度、雷达更新时间、挂单更新时间、模拟账本更新时间。
- [ ] 每次部署后记录版本、文件清单、重启时间和验证结果。

