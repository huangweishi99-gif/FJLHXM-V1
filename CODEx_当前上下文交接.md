# Codex 当前上下文交接

更新时间：2026-05-26

工作区：

```text
C:\Users\guangwan\Documents\New project
```

## 项目当前阶段

项目目前处在“方案 A：引擎稳定化阶段”，还未正式进入 Web / 移动端产品化开发。

方案 A 目标：先把峰极 OS、DS01-DS09、峰极总定式、数据、测试和监测脚本做稳。等 A2 单元测试和 A3 十币 180d 总定式回测验收稳定后，再启动 FJLHXM-V1 产品化。

产品化方案 B 已有规划文档：

```text
FJLHXM-V1.md
```

当前路线图文档：

```text
docs\PLAN_A_ROADMAP.md
```

## 已完成/接近完成

1. 峰极 OS + DS01-DS09 + 峰极总定式已经成型。
2. DS09 已纳入峰极总定式；有 M15 数据时参与合一判断，无 M15 时跳过。
3. 总定式规格以 `docs\FENGJI_TOTAL_PATTERN_SPEC.md` 为准。
4. `packages\fengji_core` 初版已建立，`src\quant` 作为兼容层 re-export。
5. 测试文件已建立：
   - `tests\test_os_engine.py`
   - `tests\test_ds05.py`
   - `tests\test_ds09.py`
6. crypto 十币 180d 总定式结果已有一版：
   - `results\plan_a_crypto_180d\crypto_whitelist_summary.csv`
   - 结果中 ETH、SOL、XRP 为正收益
   - 该批次 `bad_audits=0`
7. 国内期货 15 个品种 5 年 DS01-DS08 总定式结果已有：
   - `results\fengji_total_ds01_ds08_futures_15_5y\whitelist_summary.csv`
   - 该批次 `bad_audits=0`
8. A 股方向已有多个批量结果：
   - 热门 20 股
   - CPO
   - 算力
   - 半导体
   - 机器人
   - 低空经济
   - 军工
   - 航空装备
   - 最新结果集中在 `results\fengji_total_a_stock_sectors_*_ds07_fixed`

## A 股回测进展补充

A 股已经不是“刚开始”，而是完成了热门股样本与多个题材板块的批量验证。

主要代码：

```text
src\backtest_a_stock_fengji.py
src\batch_backtest_a_stock_fengji.py
src\batch_backtest_a_stock_sector.py
```

主要审查文档：

```text
docs\FENGJI_TOTAL_A_STOCK_HOT20_REVIEW.md
```

A 股当前执行规则：

```text
峰极总定式 = DS01-DS08
只做多，不做空
初始资金 = 20000
每次尽量满仓
买入 = 100股整数倍
T+1 卖出
佣金 = 0.03%，最低 5 元
印花税 = 卖出 0.05%
过户费 = 双边 0.001%
滑点 = 单边 0.03%
```

热门 20 股 fixed 结果：

```text
results\fengji_total_a_stock_hot20_ds07_fixed\a_stock_hot20_summary.csv
```

热门 20 股前排：

```text
300502 新易盛：交易 86，收益 +449.63%，最大回撤 -45.44%，bad_audits=0
601138 工业富联：交易 82，收益 +181.02%，最大回撤 -45.58%，bad_audits=0
603019 中科曙光：交易 86，收益 +173.53%，最大回撤 -28.43%，bad_audits=0
300059 东方财富：交易 77，收益 +156.70%，最大回撤 -43.40%，bad_audits=0
002594 比亚迪：交易 85，收益 +98.34%，最大回撤 -30.27%，bad_audits=0
300308 中际旭创：交易 77，收益 +84.23%，最大回撤 -33.30%，bad_audits=0
002371 北方华创：交易 63，收益 +71.58%，最大回撤 -21.04%，bad_audits=0
002414 高德红外：交易 95，收益 +69.89%，最大回撤 -42.02%，bad_audits=0
```

热门 20 股文档里的初步分层：

```text
优先复核：中科曙光、北方华创、比亚迪、中际旭创
高收益但回撤偏大观察：新易盛、工业富联、东方财富、高德红外
暂不进入股票模拟盘：其余表现弱或回撤/样本问题较明显的股票
```

已跑过的板块 fixed 批量结果：

```text
results\fengji_total_a_stock_sectors_cpo_ds07_fixed
results\fengji_total_a_stock_sectors_suanli_ds07_fixed
results\fengji_total_a_stock_sectors_semiconductor_ds07_fixed
results\fengji_total_a_stock_sectors_robot_ds07_fixed
results\fengji_total_a_stock_sectors_virtual_robot_ds07_fixed
results\fengji_total_a_stock_sectors_low_altitude_ds07_fixed
results\fengji_total_a_stock_sectors_evtol_ds07_fixed
results\fengji_total_a_stock_sectors_military_ds07_fixed
results\fengji_total_a_stock_sectors_aviation_equipment_ds07_fixed
```

板块前排样例：

```text
CPO：新易盛、长芯博创、光库科技、工业富联、中天科技
算力：新易盛、寒武纪、工业富联、中科曙光、协创数据
半导体：寒武纪、海光信息、北方华创、华天科技、华虹公司
虚拟机器人：东方财富、大智慧、同花顺、润建股份、科蓝软件
航空装备：迈信林、炼石航空、光启技术、博云新材、爱乐达
```

重要限制：东方财富接口当前 60 分钟线只返回最近约 128 根，因此 A 股 DS07/DS08 的小时线部分还不能算完整历史级验证。当前 A 股更可靠的正式口径应先按 DS01-DS06 日线版筛选，或者先补齐历史 60 分钟线再确认 DS01-DS08 全口径。

## 当前路线图状态

| 里程碑 | 状态 | 备注 |
|---|---|---|
| A0 安装验收 | 待复验 | `scripts\plan_a_verify.ps1` 已存在 |
| A1 fengji_core 包 | 基本完成 | 初版包与兼容层已建立 |
| A2 单元测试 | 进行中 | 测试文件已存在，但当前环境需要修 pytest/Python 调用 |
| A3 DS09 数据 + 十币 180d 总定式回测 | 接近完成 | `results\plan_a_crypto_180d` 已有结果，需按验收口径确认 |
| A4 SQLite 行情库导入 | 待做 | 参考 `docs\LOCAL_MARKET_DATA_DB.md` |
| A5 7x24 监测稳定 | 待做 | 目标是 `crypto_combined_monitor` 定时稳定运行 |

## 上一轮检查到的问题

在 PowerShell 中直接运行：

```powershell
pytest -q
```

失败，原因是 `pytest` 不在 PATH。

尝试用完整 Python 路径运行：

```powershell
& 'C:\Users\guangwan\AppData\Local\Programs\Python\Python312\python.exe' -m pytest -q
```

失败，报错：

```text
Access is denied
```

注意：已有一些命令前缀曾被批准过，包括通过该 Python 路径运行项目脚本和 pip。新会话应优先排查 Python 可执行权限、PATH、或直接使用项目已批准/可用的运行方式。

## 建议下一步

1. 先修复测试运行环境。
2. 运行：

```powershell
.\scripts\plan_a_verify.ps1
```

3. 如果 A0/A2 全绿，确认 A3 十币 180d 回测结果是否满足验收。
4. 之后推进 A4：

```powershell
python src\market_data_store.py import --help
```

5. 再推进 A5：

```powershell
python src\crypto_combined_monitor.py --symbols DEFAULT --days 180 --out-dir results\crypto_combined_monitor
```

## 关键文件

```text
README.md
FJLHXM-V1.md
docs\PLAN_A_ROADMAP.md
docs\CANONICAL_RULES.md
docs\FENGJI_TOTAL_PATTERN_SPEC.md
docs\DS09_IN_TOTAL_PATTERN.md
docs\LOCAL_MARKET_DATA_DB.md
packages\fengji_core
src\unified_whitelist_engine.py
src\batch_unified_crypto_whitelist.py
src\batch_unified_whitelist_engine.py
src\crypto_combined_monitor.py
src\market_data_store.py
scripts\plan_a_verify.ps1
```

## 当前 Git 状态

上一轮检查时：

```text
git status --short
```

输出为空，说明工作区当时是干净的。

最近提交：

```text
a227420 第一次提交
```

本文件是交接用新文件，创建后会使工作区变为未提交状态。
