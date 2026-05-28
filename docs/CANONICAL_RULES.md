# Project Canonical Rules

本项目是当前峰极OS / DS01-DS09 峰极总定式的最新工程准绳。DS09（九重天，D1+M15）已校准并纳入总定式；缺少 M15 数据时仅跳过 DS09，不影响 DS01-DS08。

用户提供的 Word 文档均视为历史旧稿、素材或审计参考。若旧文档与本项目当前代码、沙盒图校准结果、README 或本文件冲突，一律以本项目为准。

## 最高宪法

所有当前纳入峰极总定式的定式 DS01-DS09 必须继承本项目当前峰极OS底层与红蓝阵营转换规则。

用户上传的旧文档只用于参考各个定式自己的买卖逻辑，不再参考其中任何峰极OS宪法、峰极线规则、红蓝阵营规则或转势规则。

如果某份旧文档里的定式买卖逻辑依赖旧OS定义，必须先把它迁移到本项目当前OS底座之后，才允许实现和回测。

当前最高底座包括：

- 3-3 / T+3 原始峰极确认。
- 同价最高/最低取最新K线。
- 硬化峰极线：同类吞并、峰极交替、至少 2 根完整K线隔离。
- 物理沙盒主线：`hardened_fengji_line`。
- 红蓝阵营转换：红极失守红转蓝，蓝极失守蓝转红。
- 中间失败点 a/f 只在破极后允许身份重定义。
- 所有交易必须通过阵营方向审计。

## 红蓝阵营状态机标准图口径

所有周期、所有定式都必须使用同一套红蓝阵营身份流转：

```text
适用范围 = DS01-DS09 × 日线 / 小时线 / 15分钟（DS09 执行周期）
```

红阵营：

```text
峰向上进攻
极向下防守
红极失守 = 红转蓝
```

蓝阵营：

```text
峰向下进攻
极向上防守
蓝极失守 = 蓝转红
```

标准身份例：

```text
红阵营:
1红极, 2红峰, 3红极, 4红峰, 5红极, 6红峰, 7红极, 8红峰, 9红极

红转蓝:
刺破红极9，红转蓝；a 重定义为蓝极

蓝阵营:
a蓝极, b蓝峰, c蓝极, d蓝峰, e蓝极, f蓝峰/失败下探点

蓝转红:
刺破蓝极e，蓝转红；f 重定义为红极，g 成为红峰
```

永久禁止：

```text
直接把几何高点叫峰
直接把几何低点叫极
脱离当前阵营判断峰极身份
未破防守极提前转势
```

## 当前最终口径

### 0. 峰极总定式

DS01-DS09 合并后正式命名为：峰极总定式。

完整规格见：

```text
docs/FENGJI_TOTAL_PATTERN_SPEC.md
```

最终目标不是九个互相独立的回测脚本，而是一个统一白名单监测引擎：

```text
监测对象 = 白名单品种
信号来源 = DS01-DS09
OS底座   = 当前最高峰极OS
执行约束 = 总控账本统一管理
```

总控硬规则：

- 所有定式必须继承当前最高峰极OS，不允许使用旧文档里的旧OS、旧峰极线、旧阵营规则或旧 `GAP=4`。
- 旧文档只读取各定式自己的买卖触发逻辑。
- 同一品种同一时刻只能有一个净方向：未全部平仓前，不允许开反仓。
- 同一品种同向开仓最多 3 笔；超过 3 笔的信号只记录，不执行。
- 每一笔仓位必须记录来源定式，例如 `DS01`、`DS02`、`DS03`。
- 每一笔仓位使用开仓定式自己的止损规则，直到该笔完全平仓。
- DS04 是抄底摸顶型三K夺权定式，开仓方向由 DS04 自身结构决定，不使用 OS 阵营方向作为前置过滤；这不代表脱离 OS，DS04 仍必须读取当前最高 OS 做峰极线、阵营背景、红极/蓝极防守升级和沙盒审计。
- 多个定式同日同方向触发时，必须进入固定优先级/审计队列，不允许隐式随机成交。
- 多个定式同日反方向触发时，若已有持仓，以“不反仓”优先；若无持仓，必须记录冲突并按固定优先级处理。
- 所有成交、拒单、冲突、资金不足、超过 3 笔、方向禁止，都必须写入订单审计日志。

合一引擎中的每笔持仓至少保存：

```text
symbol
direction
strategy_id
entry_idx / entry_date
entry_price
initial_stop
current_stop
stop_rule_id
lots
status
```

当前工程入口：

```text
src/unified_whitelist_engine.py
src/batch_unified_whitelist_engine.py
```

当前峰极总定式账本输出：

```text
candidate_trades.csv      # DS01-DS09 独立候选交易归一化结果
accepted_trades.csv       # 总控接受执行的交易
rejected_orders.csv       # 不反仓、同向超过3笔、缺数据等拒单
ledger_events.csv         # open / close / reject 事件流水
strategy_bad_trades.csv   # 各定式自身结构审计失败记录，正常应为空
whitelist_summary.csv     # 批量白名单汇总
```

虚拟货币白名单准入硬规则：

```text
没有历史实盘数据回测 = 不允许进入量化白名单
没有峰极总定式回测 = 不允许进入量化白名单
没有沙盒图人工确认 = 不允许实盘开仓
没有前向模拟期 = 不允许上真实仓位
```

虚拟货币默认资金规则：

```text
本金 = 1000 USDT
单笔保证金 = 200 USDT
默认杠杆 = 2x
最高杠杆 = 3x
保证金模式 = 逐仓
```

当前虚拟货币总定式回测入口：

```text
src/batch_unified_crypto_whitelist.py
```

DS09 口径（已纳入峰极总定式）：

```text
DS09 = D1 OS战略阵营 + 昨日D1战略边界 + M15 精确点火（九重天）
D1红阵营 + 昨日阴线 -> 今日突破昨日high后进入M15多头锁定流程
D1蓝阵营 + 昨日阳线 -> 今日跌破昨日low后进入M15空头锁定流程
第一次刺穿D1边界只锁定，不入场；M15必须等第一进攻峰、防守极、二次攻击
原 D1 + M5 回测/沙盒结果全部降级为旧口径参考
DS09 D1+M15 沙盒图已由用户确认正确
缺少 M15 数据时，DS09 记 data_missing，DS01-DS08 照常运行
crypto 15m 数据拉取：scripts/fetch_crypto_m15_for_ds09.py
详见：docs/DS09_IN_TOTAL_PATTERN.md
```

旧 180 天十币 DS01-DS09 初筛已降级为历史参考：

```text
ETH-USDT = 回测候选白名单，+23.84%，最大回撤 -14.92%
SOL-USDT = 回测候选白名单，+8.21%，最大回撤 -16.28%
XRP-USDT = 回测候选白名单，+7.84%，最大回撤 -18.22%
AVAX-USDT = 观察，+10.45%，最大回撤 -21.84%
LINK-USDT = 观察，+5.80%，最大回撤 -23.64%
BTC-USDT = 暂不进入白名单，-3.79%
DOGE-USDT = 暂不进入白名单，-3.66%
BNB-USDT = 暂不进入白名单，-6.73%
LTC-USDT = 暂不进入白名单，-19.14%
ADA-USDT = 黑名单/禁用，-37.30%
```

正式审查文件：

```text
docs/FENGJI_TOTAL_PATTERN_CRYPTO_180D_REVIEW.md
```

最近一次 30 天前向模拟结论：

```text
ETH-USDT 全定式前向未通过；仅 DS08,DS09 超严格观察口径小幅转正
XRP-USDT 全定式前向未通过；仅 DS09 超严格观察口径小幅转正但样本太少
SOL-USDT 前向未通过，暂停升级
当前不允许任何虚拟货币直接进入正式实盘白名单
```

峰极总定式实时监测层当前口径：

```text
主入口 = src/crypto_combined_monitor.py
输入 = 任意待回测/待监测虚拟货币品种
检测 = DS01-DS09 全部合并检测
执行 = 出现哪个定式信号，就用哪个定式的入场、止损、出场规则
排序 = 不按定式人为优先；同一时间冲突只由总控账本处理
自动下单 = 禁止
输出只能是 COMBINED_SIGNAL_OBSERVE_ONLY / NO_SIGNAL / ERROR
监测窗口必须以最新 H1 K线时间为基准
```

`src/crypto_realtime_monitor.py` 和 `data/crypto_m15_forward_observation_rules.csv` 只保留为研究观察工具，不是主系统，不得替代峰极总定式。

当前已校准定式：

```text
DS01
DS02
DS03
DS04
DS05
DS06
DS07
DS08
```

DS09 已纳入峰极总定式；运行前须准备 M15 数据，见 docs/DS09_IN_TOTAL_PATTERN.md。

### 1. 物理峰极线

物理沙盒图主峰极线使用：

```text
hardened_fengji_line
```

含义：

- 使用 3-3 / T+3 释放后的原始 HIGH/LOW 节点。
- 再经过硬化：同类吞并、峰极交替、两根K线隔离。
- 相邻合法硬化峰极点之间用直线线段连接。
- 主图表现为连续的“峰-极-峰-极”折线。
- 峰和极之间至少间隔 2 根完整K线，即 `point_idx` 差值至少为 3。
- 如果 3-3 窗口内出现两个或多个同样最高价/最低价，按最新的那根K线作为峰点或极点。

这条线才是物理沙盒图里的主峰极线。

### 2. identity_line 的定位

`identity_line` 不作为物理沙盒主折线。

它用于身份审计：

- 过滤失败点提前入线。
- 检查峰/极身份是否按规则进入合法骨架。
- 辅助排查阵营转势和 a/f 身份重定义。

### 3. tagged_line 的定位

`tagged_line` 只作为旧通用版连线检查参考。

它不是最终主峰极线。

### 4. DS05 交易规则

DS05 仍按当前代码实现：

- 红阵营只做多。
- 蓝阵营只做空。
- K2/K3 必须同阵营。
- K2 不要求靠近旧 active extreme；K2 本身是可能形成的“极”，用于防守和转势判断。
- K3 夺权后触发。
- 初始止损守 K2。
- 动态止损只用顺方向K线尾部推进。
- `bad_trades.csv` 必须为空。

### 5. DS04 特例口径

DS04《夹棍/隔山炮》是抄底摸顶型三K夺权定式，不是阵营内顺势推进定式。

因此：

- DS04 开仓方向由 K1/K2/K3 夹棍夺权结构决定。
- DS04 不使用红阵营只做多、蓝阵营只做空作为开仓前置过滤。
- DS04 必须继续使用当前最高 OS：`hardened_fengji_line`、阵营背景、身份点、红极/蓝极。
- DS04 初始防守为三K极限点。
- 后续防守升级只接受有利方向的红极/蓝极：多头只用更高红极上移，空头只用更低蓝极下移。
- DS04 的审计重点不是红多蓝空，而是 K2 最弱、无缺口、K3 收盘夺权、K4 开盘执行、止损只向有利方向移动。

### 6. 旧文档使用原则

旧文档可以用于：

- 找历史概念。
- 找图例。
- 找旧代码线索。
- 做差异审计。

旧文档不再直接决定最终实现。

最终实现以这些文件为准：

```text
README.md
docs/CANONICAL_RULES.md
src/quant/os_engine.py
src/quant/ds05.py
src/backtest_ds05.py
src/batch_backtest_ds05.py
src/plot_ds05_sandbox.py
src/quant/ds06.py
src/backtest_ds06.py
src/batch_backtest_ds06.py
src/plot_ds06_sandbox.py
src/quant/ds07.py
src/backtest_ds07.py
src/batch_backtest_ds07.py
src/plot_ds07_sandbox.py
src/quant/ds08.py
src/backtest_ds08.py
src/batch_backtest_ds08.py
src/plot_ds08_sandbox.py
src/quant/ds09.py
src/backtest_ds09.py
src/batch_backtest_ds09.py
src/plot_ds09_sandbox.py
```

## 国内期货资金模型

当前真实期货回测口径：

```text
初始资金 = 100000
每次开仓 = 固定 1 手
手续费 = 成交额万分之一，开平各收一次
滑点 = 每次成交 1 tick 不利滑点
盈亏 = 价差 × 合约乘数 × 手数
保证金 = 成交价 × 合约乘数 × 手数 × 保证金率
```

保证金只作为开仓资金约束，不作为成本扣除。

合约乘数、最小变动价位、保证金率维护在：

```text
src/quant/futures_specs.py
```

保证金率使用偏保守的期货公司风控默认值。若用户提供自己的期货公司保证金/手续费表，应以账户实际规则覆盖此表。
