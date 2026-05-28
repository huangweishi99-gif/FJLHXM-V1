# 峰极量化项目 / FengJi OS / FengJi Total Pattern

更新时间：2026-05-27

## 2026-05-27 总工程接手版摘要

### 项目简介

本项目是峰极OS总工程，覆盖：

- 峰极OS最高宪法
- 红蓝阵营与转势判断
- DS01-DS09 九大定式
- 总定式雷达
- 模拟挂单器
- 虚拟货币、国内期货、A股实盘数据
- 国内服务器与海外服务器模拟实盘部署
- 回测、沙盒图、测试验证
- Cursor / Codex 跨工具接手

核心原则：所有定式必须在峰极OS最高宪法之下执行策略。任何策略信号都不能绕过峰极线、峰/极、阵营转换和 OS 审计。

### 项目目录说明

```text
PROJECT_CONTEXT.md                  总交接上下文
AGENTS.md                           AI 接手规则
TODO.md                             当前任务和风险
CHANGELOG.md                        变更记录
峰极OS_CANONICAL_RULES.md            根目录峰极OS规则摘要
docs/                               规则、定式、回测审查文档
packages/fengji_core/               可复用峰极OS核心包，含 DS01-DS09
src/                                主程序、回测、雷达、挂单器、模拟盘
tests/                              pytest 测试
scripts/                            检查、绘图、部署、重启脚本
data/                               本地行情数据
results/                            回测结果和沙盒图
runtime/                            运行态产物、日志、远程检查快照
config/                             配置示例，不保存真实密钥
remote_domestic_optimize/            国内服务器同步/优化包
domestic_futures_ds07_update/        历史 DS07 更新包
```

### 如何让 Codex 接手

在 Codex 新会话中使用：

```text
请读取 C:\Users\guangwan\Documents\New project。先读 PROJECT_CONTEXT.md、AGENTS.md、TODO.md、CHANGELOG.md、README.md、峰极OS_最高宪法.md、峰极OS_阵营转换判断.md、峰极OS_九大定式规则总纲.md、峰极OS_CANONICAL_RULES.md，以及 docs/CANONICAL_RULES.md、docs/FENGJI_TOTAL_PATTERN_SPEC.md、docs/PLAN_A_ROADMAP.md。这个项目是峰极OS总工程，包含 DS01-DS09。不要删除文件，不要回滚已有改动，不要写入任何服务器密码、API Key、Token 或完整 webhook。读取后先汇报当前状态和下一步建议。
```

Codex 修改代码前必须先说明计划；修改后必须更新 `CHANGELOG.md` 和 `TODO.md`，并说明测试或未测试原因。

### 如何让 Cursor 接手

在 Cursor 中打开项目根目录：

```text
C:\Users\guangwan\Documents\New project
```

然后要求 Cursor 先读取：

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

Cursor 不应凭空继承旧聊天内容。旧聊天不可见时，只能依据项目文件、代码、测试、日志和用户本轮明确描述判断。

### 如何运行或验证项目

只读检查：

```powershell
Set-Location "C:\Users\guangwan\Documents\New project"
git status --short
Get-ChildItem -Force
```

安装依赖：

```powershell
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

运行核心测试：

```powershell
python -m pytest tests\test_os_engine.py tests\test_ds01.py tests\test_ds03.py tests\test_ds05.py -q
python -m pytest tests\test_pending_orders.py tests\test_futures_pending_orders.py tests\test_radar_ds04.py tests\test_radar_ds05.py tests\test_radar_ds06.py tests\test_radar_ds07.py tests\test_radar_ds08.py -q
```

如果 `python` 不在 PATH，可使用本机 Python 完整路径：

```powershell
& "C:\Users\guangwan\AppData\Local\Programs\Python\Python312\python.exe" -m pytest tests\ -q
```

服务器状态检查必须实时执行，不能引用旧日志。服务器地址、密码、Token、webhook 等只保存在本地私密配置或服务器环境变量中，不写入仓库文档。

### 安全注意事项

- 不写入服务器密码、API Key、Token、私钥、完整 webhook。
- 服务器只写用途和占位符，例如“国内服务器：已配置，具体地址见本地私密配置文件”。
- 当前工程只允许模拟盘和模拟挂单，不允许自动真实下单。
- 不删除未知文件，不批量回滚，不重写整个项目。
- 所有 DS01-DS09 的判断必须接受峰极OS最高宪法约束。

## 项目简介

本项目是峰极 OS、DS01-DS09、峰极总定式、回测、模拟实盘监测、模拟挂单、沙盒图审计和市场数据管线的工程仓库。

当前主线是 **方案 A：引擎稳定化**，不是 Web/移动端产品化。产品化规划见 `FJLHXM-V1.md`，但要等峰极 OS、总定式、测试、数据和监测链路稳定后再推进。

总目标：

```text
峰极总定式 = 当前最高峰极OS + DS01-DS09 全部信号 + 总控账本
```

所有定式必须在峰极 OS 最高宪法下执行策略。旧 Word 文档只作为历史素材或触发逻辑参考，不再决定 OS、峰极线、红蓝阵营或转势规则。

## 如何让 AI 接手本项目

新的 Cursor / Codex 会话必须先读取：

```text
PROJECT_CONTEXT.md
AGENTS.md
TODO.md
CHANGELOG.md
README.md
峰极OS_CANONICAL_RULES.md
峰极OS_最高宪法.md
峰极OS_阵营转换判断.md
峰极OS_九大定式规则总纲.md
docs/CANONICAL_RULES.md
docs/FENGJI_TOTAL_PATTERN_SPEC.md
docs/PLAN_A_ROADMAP.md
```

建议提示词：

```text
请先读取 PROJECT_CONTEXT.md、AGENTS.md、TODO.md、CHANGELOG.md、README.md、峰极OS_最高宪法.md、峰极OS_阵营转换判断.md、峰极OS_九大定式规则总纲.md、峰极OS_CANONICAL_RULES.md，以及 docs/CANONICAL_RULES.md 和 docs/FENGJI_TOTAL_PATTERN_SPEC.md。不要删除文件，不要回滚已有改动。所有定式必须在峰极OS最高宪法下执行。读取后先汇报当前状态和下一步建议。
```

接手后先做只读检查：

```powershell
Set-Location "C:\Users\guangwan\Documents\New project"
git status --short
Get-ChildItem -Force
```

## 当前状态摘要

- 峰极 OS 与 DS01-DS09 已成型，仍处于引擎稳定化阶段。
- DS01、DS03、DS05、DS07 最近有重要规则修正，需持续确认代码、雷达、挂单和模拟盘一致。
- A股热门20与多个板块已有回测结果，但 A股 60 分钟历史覆盖不足，DS07/DS08 历史级结论需谨慎。
- 海外虚拟货币与国内期货/A股模拟盘状态是时间敏感事实，必须实时 SSH 检查。
- 当前虚拟货币只允许模拟与观察，不允许真实下单。

## 重要文件说明

```text
PROJECT_CONTEXT.md                    给 Cursor/Codex 的完整接手上下文
AGENTS.md                             AI 接手规则和禁止事项
TODO.md                               当前任务、风险和建议提示词
CHANGELOG.md                          项目上下文沉淀记录
峰极OS_CANONICAL_RULES.md              根目录峰极 OS 规则摘要
docs/CANONICAL_RULES.md               当前工程最高规则
docs/FENGJI_TOTAL_PATTERN_SPEC.md     峰极总定式完整规格
docs/PLAN_A_ROADMAP.md                方案 A 引擎稳定化路线图
src/quant/os_engine.py                峰极 OS 身份引擎
src/quant/ds01.py                     DS01 挫棍
src/quant/ds03.py                     DS03 二四棒
src/quant/ds05.py                     DS05 指形战法
src/quant/ds07.py                     DS07 D1+H1 跨周期共振
src/unified_whitelist_engine.py       单品种峰极总定式账本
src/batch_unified_crypto_whitelist.py 虚拟货币批量总定式回测
src/batch_unified_whitelist_engine.py 国内期货批量总定式回测
src/backtest_a_stock_fengji.py        A股单股总定式回测
src/batch_backtest_a_stock_sector.py  A股板块批量回测
src/fengji_total_radar.py             总定式雷达
src/fengji_pending_orders.py          模拟挂单生成
src/fengji_pending_order_monitor.py   海外虚拟货币模拟挂单监控
src/fengji_futures_pending_order_monitor.py 国内期货/A股挂单监控
data_manager.py                       海外虚拟货币数据泵
data_manager_futures.py               国内期货数据泵
```

## 如何启动或运行

安装依赖：

```powershell
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

运行测试：

```powershell
python -m pytest tests\ -q
```

如果 PowerShell 中 Python 路径带空格，使用执行符 `&`：

```powershell
& "C:\Users\guangwan\AppData\Local\Programs\Python\Python312\python.exe" -m pytest tests\ -q
```

方案 A 安装验收：

```powershell
.\scripts\plan_a_verify.ps1
```

DS05 样本回测：

```powershell
python src\backtest_ds05.py --csv data\sample_ohlcv.csv --out-dir results\ds05_sample
```

峰极总定式单品种回测：

```powershell
python src\unified_whitelist_engine.py `
  --symbol 生猪 `
  --daily-csv "D:\BaiduNetdiskDownload\期货\实盘数据\实盘数据日K线\生猪_日线_5年.csv" `
  --h1-csv "D:\BaiduNetdiskDownload\期货\实盘数据\5-60分钟csv\生猪_60m.csv" `
  --m15-csv "D:\BaiduNetdiskDownload\期货\实盘数据\5-60分钟csv\生猪_15m.csv" `
  --out-dir results\unified_smoke\生猪
```

虚拟货币批量总定式回测：

```powershell
python src\batch_unified_crypto_whitelist.py `
  --symbols BTC-USDT,ETH-USDT,SOL-USDT `
  --days 180 `
  --leverage 2 `
  --margin-per-trade 200 `
  --out-dir results\unified_crypto_whitelist_core_180d
```

A股板块回测 PowerShell 示例：

```powershell
Set-Location "C:\Users\guangwan\Documents\New project"

& "C:\Users\guangwan\AppData\Local\Programs\Python\Python312\python.exe" ".\src\batch_backtest_a_stock_sector.py" `
  --boards "CPO概念" `
  --top-n 28 `
  --sort-by amount `
  --data-source auto `
  --db ".\data\market_data.sqlite" `
  --out-dir ".\results\fengji_total_a_stock_sectors_cpo_ds07_fixed"
```

生成 DS03 实盘触发沙盒 SVG：

```powershell
python scripts\plot_live_ds03_sandbox_svg.py `
  --data-dir data `
  --symbol IOUSDT `
  --timeframe 1d `
  --date 2026-05-27 `
  --side long `
  --fill-price 0.1719 `
  --trigger-price 0.1602 `
  --stop-price 0.1512 `
  --out results\sandbox\IOUSDT_DS03_20260527_long.svg
```

## 注意事项

- 不要删除已有文件。
- 不要回滚未提交改动。
- 不要把 API Key、Token、密码、私钥、完整 Webhook 写进文档、代码或日志。
- 不要用旧 Word 文档覆盖当前工程规则。
- 不要把 raw high/low 直接叫峰/极。
- 不要恢复旧 DS07 逻辑。
- 不要把模拟盘改为真实下单。

---

以下保留并整合原 README 的历史运行说明。

# FengJi OS DS01-DS08 Quant Backtest

This project implements a codable subset extracted from the two provided Word documents:

- FengJi OS constitution V5 runtime / patch version
- FengJi OS DS05 finger-pattern final whitepaper

The implemented strategy is DS05 "Finger Pattern": an extreme-zone counterattack pattern authorized by FengJi OS.

## Source Of Truth

The Word documents are historical references. If they conflict with the current project code, sandbox chart behavior, or [docs/CANONICAL_RULES.md](docs/CANONICAL_RULES.md), this project wins.

Current physical sandbox charts use `hardened_fengji_line` as the main FengJi line: hardened 3-3/T+3 HIGH/LOW nodes connected by straight line segments in peak-extreme-peak-extreme order.

All DS01-DS09 strategies in the current FengJi Total Pattern must inherit this project's current FengJi OS and red/blue camp transition rules. Uploaded documents are only references for each strategy's buy/sell trigger logic, not for OS constitution, line rules, or camp rules. DS09 (D1 + M15) is included when M15 data is available.

DS01-DS09 are the current FengJi Total Pattern. See the calibration documents in `docs/` and `docs/DS09_IN_TOTAL_PATTERN.md`.

The same red/blue camp state machine applies to every strategy and timeframe: daily, hourly, and 5-minute bars.

## Extracted Trading Rules

FengJi OS base:

- Raw nodes use 3-3 / T+3 confirmation. A node at bar T is only released after T+3 closes.
- If one bar is both HIGH and LOW, keep HIGH for bullish candle, keep LOW for bearish candle, discard doji.
- Hardened nodes must alternate HIGH and LOW.
- Consecutive HIGH keeps the higher one; consecutive LOW keeps the lower one.
- Adjacent opposite node `point_idx` distance must be at least `gap`, default 3. This means there must be at least two full K bars between a peak and an extreme.
- If multiple bars share the same highest high or lowest low inside the 3-3 window, the latest bar is the valid peak/extreme candidate.
- Camp is a state machine: red = long camp, blue = short camp, neutral = no authorization.
- Defense extreme break causes camp transition.
- Failed points enter `identity_nodes` as logs, but only legal PEAK/EXT nodes enter `identity_line`.

DS05 signal:

- Long only in red camp. Short only in blue camp.
- K2 and K3 must be in the same camp.
- Long: K2 makes a lower low near active red extreme, K3 does not break K2 low, and K3 breaks K2 high.
- Short: K2 makes a higher high near active blue extreme, K3 does not break K2 high, and K3 breaks K2 low.
- K2 must not gap away from K1.
- Extreme proximity uses ATR tolerance, default `0.80 * ATR`.
- Entry is same-bar trigger:
  - Long entry = `max(K3.open, K2.high)`
  - Short entry = `min(K3.open, K2.low)`
- Initial stop is K2 low for long, K2 high for short.
- Dynamic stop follows DS02-style rule:
  - Long stop only moves up on bullish candles, using that candle's low.
  - Short stop only moves down on bearish candles, using that candle's high.
- Trade audit must prove there is no short in red camp and no long in blue camp.

## Run

Install dependencies:

```powershell
pip install -r requirements.txt
```

Generate sample OHLCV data:

```powershell
python scripts/generate_sample_data.py --out data/sample_ohlcv.csv
```

Run DS05 backtest:

```powershell
python src/backtest_ds05.py --csv data/sample_ohlcv.csv --out-dir results/ds05_sample
```

If Python was installed through IDLE but `python` is not in PATH, use the helper script:

```powershell
.\run_ds05.ps1
```

Or call Python with its full path:

```powershell
& "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe" src\backtest_ds05.py --csv data\sample_ohlcv.csv --out-dir results\ds05_sample
```

Batch run local futures daily data:

```powershell
python src\batch_backtest_ds05.py --data-dir "D:\BaiduNetdiskDownload\期货\实盘数据\实盘数据日K线" --pattern "*日线*.csv" --out-dir results\ds05_real_daily
```

Realistic futures capital model:

```powershell
python src\batch_backtest_ds05.py `
  --data-dir "D:\BaiduNetdiskDownload\期货\实盘数据\实盘数据日K线" `
  --pattern "*日线*.csv" `
  --out-dir results\ds05_real_daily_futures `
  --initial-cash 100000 `
  --lots 1 `
  --commission-rate 0.0001 `
  --slippage-ticks 1
```

The futures model uses:

- Initial cash: 100,000
- Position size: fixed 1 lot
- PnL: price difference x contract multiplier x lots
- Fee: notional x 0.0001 per entry/exit
- Slippage: 1 adverse tick per fill
- Margin: notional x configured product margin rate
- Margin is a capital constraint, not a cash cost

Or:

```powershell
.\run_real_daily_ds05.ps1
```

Generate sandbox charts for the last N DS05 trades:

```powershell
python src\batch_plot_ds05_sandbox.py `
  --csv "D:\BaiduNetdiskDownload\期货\实盘数据\实盘数据日K线\棉花_日线_5年.csv" `
  --last 7 `
  --out-dir results\sandbox\cotton_last7 `
  --futures-mode
```

Run the FengJi Total Pattern whitelist ledger for one symbol:

```powershell
python src\unified_whitelist_engine.py `
  --symbol 生猪 `
  --daily-csv "D:\BaiduNetdiskDownload\期货\实盘数据\实盘数据日K线\生猪_日线_5年.csv" `
  --h1-csv "D:\BaiduNetdiskDownload\期货\实盘数据\5-60分钟csv\生猪_60m.csv" `
  --m15-csv "D:\BaiduNetdiskDownload\期货\实盘数据\5-60分钟csv\生猪_15m.csv" `
  --out-dir results\unified_smoke\生猪
```

Run the FengJi Total Pattern whitelist ledger in batch:

```powershell
python src\batch_unified_whitelist_engine.py `
  --whitelist 生猪,碳酸锂,乙二醇 `
  --daily-dir "D:\BaiduNetdiskDownload\期货\实盘数据\实盘数据日K线" `
  --minute-dir "D:\BaiduNetdiskDownload\期货\实盘数据\5-60分钟csv" `
  --out-dir results\unified_whitelist
```

Unified outputs:

- `candidate_trades.csv`
- `accepted_trades.csv`
- `rejected_orders.csv`
- `ledger_events.csv`
- `strategy_bad_trades.csv`
- `whitelist_summary.csv` for batch runs

Run the FengJi Total Pattern crypto whitelist review on OKX historical bars:

```powershell
python src\batch_unified_crypto_whitelist.py `
  --symbols BTC-USDT,ETH-USDT,SOL-USDT `
  --days 180 `
  --leverage 2 `
  --margin-per-trade 200 `
  --out-dir results\unified_crypto_whitelist_core_180d
```

Crypto whitelist admission is gated by historical live-data review first. DS09 is part of the FengJi Total Pattern; fetch M15 bars with `scripts/fetch_crypto_m15_for_ds09.py` before backtests. The current DS01-DS08 5-year review is documented in [docs/FENGJI_TOTAL_DS01_DS08_CRYPTO_5Y_REVIEW.md](docs/FENGJI_TOTAL_DS01_DS08_CRYPTO_5Y_REVIEW.md) (DS09+M15 full reruns use `batch_unified_crypto_whitelist.py` defaults).

The latest 30-day forward review is documented in [docs/CRYPTO_FORWARD30_M15_REVIEW.md](docs/CRYPTO_FORWARD30_M15_REVIEW.md). No crypto symbol is approved for live auto-trading yet; ETH and XRP only have restricted observation rules.

Run the all-in-one observation-only realtime monitor:

```powershell
python src\crypto_combined_monitor.py `
  --symbols ETH-USDT `
  --lookback-hours 24 `
  --out-dir results\crypto_combined_monitor
```

The canonical FengJi Total Pattern crypto system is documented in [docs/CRYPTO_COMBINED_SYSTEM.md](docs/CRYPTO_COMBINED_SYSTEM.md). It checks DS01-DS09 together and never places live orders.

The full FengJi Total Pattern specification is documented in [docs/FENGJI_TOTAL_PATTERN_SPEC.md](docs/FENGJI_TOTAL_PATTERN_SPEC.md).

The latest FengJi Total Pattern crypto 180-day review is documented in [docs/FENGJI_TOTAL_PATTERN_CRYPTO_180D_REVIEW.md](docs/FENGJI_TOTAL_PATTERN_CRYPTO_180D_REVIEW.md).

DS01 has been calibrated on the current OS. See [docs/DS01_DRAFT.md](docs/DS01_DRAFT.md) and [docs/DS01_CALIBRATION.md](docs/DS01_CALIBRATION.md).

DS02 has been calibrated on the current OS. See [docs/DS02_DRAFT.md](docs/DS02_DRAFT.md) and [docs/DS02_CALIBRATION.md](docs/DS02_CALIBRATION.md).

DS03 has been calibrated on the current OS. See [docs/DS03_DRAFT.md](docs/DS03_DRAFT.md) and [docs/DS03_CALIBRATION.md](docs/DS03_CALIBRATION.md).

DS04 has been calibrated on the current OS. See [docs/DS04_DRAFT.md](docs/DS04_DRAFT.md) and [docs/DS04_CALIBRATION.md](docs/DS04_CALIBRATION.md).

DS05 has been calibrated on the current OS. See [docs/DS05_CALIBRATION.md](docs/DS05_CALIBRATION.md).

DS06 has been calibrated on the current OS. See [docs/DS06_DRAFT.md](docs/DS06_DRAFT.md) and [docs/DS06_CALIBRATION.md](docs/DS06_CALIBRATION.md).

DS07 has been calibrated on the current OS. See [docs/DS07_DRAFT.md](docs/DS07_DRAFT.md) and [docs/DS07_CALIBRATION.md](docs/DS07_CALIBRATION.md).

DS08 has been calibrated on the current OS. See [docs/DS08_DRAFT.md](docs/DS08_DRAFT.md) and [docs/DS08_CALIBRATION.md](docs/DS08_CALIBRATION.md).

DS09 has been calibrated on the current OS. Current rule: D1 OS strategic camp + previous D1 boundary + M15 second-attack trigger. See [docs/DS09_DRAFT.md](docs/DS09_DRAFT.md) and [docs/DS09_CALIBRATION.md](docs/DS09_CALIBRATION.md).

Expected CSV columns:

```text
date,open,high,low,close,volume
```

## Outputs

When `--out-dir` is provided, the runner writes:

- `trades.csv`
- `bad_trades.csv`
- `equity.csv`
- `raw_nodes.csv`
- `identity_nodes.csv`
- `turns.csv`
- `os_log.csv`

`bad_trades.csv` should be empty for a valid DS05 run.

## Key Files

```text
packages/fengji_core/      FengJi OS + DS01-DS09 core (pip install -e)
docs/PLAN_A_ROADMAP.md     Plan A engine stabilization roadmap
scripts/plan_a_verify.ps1  One-click install verification
src/backtest_ds05.py       DS05 backtest CLI
src/quant/os_engine.py     FengJi OS identity engine
src/quant/ds05.py          DS05 signal, stop, camp audit
src/quant/data.py          CSV loading and ATR
src/unified_whitelist_engine.py  Single-symbol DS01-DS09 ledger
src/batch_unified_whitelist_engine.py  Batch whitelist ledger
src/batch_unified_crypto_whitelist.py  OKX crypto DS01-DS09 whitelist review
scripts/fetch_crypto_m15_for_ds09.py  Download OKX 15m bars for DS09
src/crypto_combined_monitor.py  All-in-one observation-only OKX crypto monitor
src/crypto_realtime_monitor.py  Research-only restricted observation monitor
src/backtest.py            Original moving-average demo
```

## Notes

The current implementation is offline and CSV-driven. The documents also mention crypto/futures data adapters, leverage, liquidation, contract multipliers, and market DNA whitelists. Those are intentionally kept outside the core DS05 logic so the OS and signal rules remain auditable.
