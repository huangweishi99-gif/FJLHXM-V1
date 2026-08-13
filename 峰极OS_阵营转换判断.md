# 峰极OS_阵营转换判断.md

更新时间：2026-05-27

文件状态：峰极OS红蓝阵营、转势状态机、阵营转换判断专项规则文件。

适用范围：峰极OS、DS01-DS09、回测、雷达、挂单器、模拟实盘、沙盒图、Cursor/Codex 接手。

本文件服从 `峰极OS_最高宪法.md`。若本文件与旧聊天、旧Word、旧脚本、旧服务器文件冲突，必须以当前最高宪法、当前项目代码、测试和用户本轮明确确认口径为准。

## 1. 阵营定义

### 红阵营

红阵营在代码中表示为：

```text
RED = 1
```

红阵营含义：

- 市场处于向上进攻状态。
- 红峰 `RED_PEAK` 是向上进攻点。
- 红极 `RED_EXT` 是向下防守点。
- 跌破红极，才允许红转蓝。
- 红阵营中，除DS04开仓特例外，方向型定式只能按各自规则寻找多头机会。

### 蓝阵营

蓝阵营在代码中表示为：

```text
BLUE = -1
```

蓝阵营含义：

- 市场处于向下进攻状态。
- 蓝峰 `BLUE_PEAK` 是向下进攻点。
- 蓝极 `BLUE_EXT` 是向上防守点。
- 突破蓝极，才允许蓝转红。
- 蓝阵营中，除DS04开仓特例外，方向型定式只能按各自规则寻找空头机会。

### 中性/未确认状态

中性状态在代码中表示为：

```text
NEUTRAL = 0
```

中性状态含义：

- 尚未通过峰极OS确认红/蓝阵营。
- 不允许方向型定式直接开仓。
- 必须先通过合法峰极结构和突破行为种下初始阵营。

## 2. 转势状态机

### 状态列表

当前项目代码中的核心状态：

```text
NEUTRAL
RED
BLUE
RED_TO_BLUE
BLUE_TO_RED
FAILED_HIGH
FAILED_LOW
```

`RED_TO_BLUE` 和 `BLUE_TO_RED` 是转势事件，不是长期阵营值。长期阵营仍落到 `RED` 或 `BLUE`。

### 状态转换条件

初始种阵营：

```text
NEUTRAL + high > last_hardened_high -> RED
NEUTRAL + low < last_hardened_low -> BLUE
```

红阵营内部：

```text
HIGH > red_peak -> 新 RED_PEAK
LOW > red_ext   -> 新 RED_EXT，红极上移
HIGH 未突破 red_peak 但高于 red_ext -> FAILED_HIGH
low < red_ext   -> RED_TO_BLUE
```

蓝阵营内部：

```text
LOW < blue_peak -> 新 BLUE_PEAK
HIGH < blue_ext -> 新 BLUE_EXT，蓝极下移
LOW 未跌破 blue_peak 但低于 blue_ext -> FAILED_LOW
high > blue_ext -> BLUE_TO_RED
```

### 转势确认条件

阵营转换只能由防守极失守触发：

```text
红极失守 = 红转蓝
蓝极失守 = 蓝转红
```

发生红转蓝时：

- 若存在 `last_failed_high`，该失败高点可重定义为 `BLUE_EXT`。
- 若不存在 `last_failed_high`，可按当前代码回退使用旧红峰重定义为 `BLUE_EXT`。

发生蓝转红时：

- 若存在 `last_failed_low`，该失败低点可重定义为 `RED_EXT`。
- 若不存在 `last_failed_low`，可按当前代码回退使用旧蓝峰重定义为 `RED_EXT`。

### 确认延迟

峰极点必须先经过 3-3 / T+3 释放：

```text
t = i - 3
candidate at t is visible only when processing i
gap = 3
```

含义：

- 峰和极之间至少间隔2根完整K线。
- 不允许用尚未释放的峰极点开仓、止损或转势。
- 不允许用回测结束后才知道的节点反推历史交易。

### 不能使用未来函数

禁止：

- 用未来K线确认当前峰极点。
- 用当日收盘后才确定的信息触发盘中M15入场。
- 用当前D1完整日线结果提前指导当天M15交易。
- 把未释放节点、普通几何高低点、旧手动画线当成OS峰极节点。

对DS09特别规定：

- D1战略阵营必须来自进入当日前已完成的D1 OS状态。
- 今日M15只能使用昨日D1边界和安全D1阵营，不得读取今日完整D1结果。

## 3. 峰极线与阵营关系

### 峰极线如何影响阵营判断

当前主峰极线是：

```text
hardened_fengji_line
```

它由 `src/quant/os_engine.py` 和 `packages/fengji_core/fengji_core/os_engine.py` 中的硬化逻辑生成：

- 原始3-3/T+3节点。
- 同类HIGH/LOW吞并。
- HIGH/LOW交替。
- `gap=3`。

阵营判断必须建立在这条硬化峰极线和身份节点之上。

### 峰点/极点如何影响攻防方向

```text
峰 = 攻击方向
极 = 防守点
```

红阵营：

- 红峰负责向上攻击。
- 红极负责防守和转势。

蓝阵营：

- 蓝峰负责向下攻击。
- 蓝极负责防守和转势。

### 错误峰极线如何导致阵营错误

峰极线错误会直接造成：

- 红/蓝阵营误判。
- active high / active low 误判。
- DS01 左线过滤误判。
- DS03 假峰/假极触发误判。
- DS05 K2 可能成极位置误判。
- DS07 D1/H1 共振误判。
- DS08 五点结构误判。
- DS09 D1/M15 两级结构误判。

争议信号必须先画沙盒图审计峰极线，再讨论定式是否成立。

## 4. 九大定式如何调用阵营判断

### 定式01 如何依赖阵营

- 红阵营 + 昨日阳棍 + 今日突破昨日高点 + 左30线段数 `<= 2` 才允许多头开仓。
- 蓝阵营 + 昨日阴棍 + 今日跌破昨日低点 + 左30线段数 `<= 2` 才允许空头开仓。
- 不允许跳过阵营，只按K线阴阳开仓。

### 定式02 如何依赖阵营

- 红阵营只检查阳吃阴多头结构。
- 蓝阵营只检查阴吃阳空头结构。
- 当前次日开盘/收盘确认等执行边界仍以DS02专门文档和代码为准。

### 定式03 如何依赖阵营

- 红阵营只做多，触发点来自 `active_high` 或合法 `FAILED_HIGH` 假峰。
- 蓝阵营只做空，触发点来自 `active_low` 或合法 `FAILED_LOW` 假极/失败低点。
- 假峰/假极必须来自OS硬化结构，不能用普通局部高低点替代。

### 定式04 如何依赖阵营

- DS04 开仓方向由 K1/K2/K3 夹棍夺权结构决定。
- DS04 是当前唯一明确允许开仓不以前置OS阵营方向过滤的定式。
- DS04 不等于脱离OS：离场、防守点升级、止损移动、沙盒图审计仍必须使用OS。

### 定式05 如何依赖阵营

- 红阵营只做多。
- 蓝阵营只做空。
- K2/K3 必须同阵营。
- K2 是可能形成“极”的位置，不是峰候选，不要求靠近旧 active extreme。

### 定式06 如何依赖阵营

- DS06 必须先发生合法转势。
- 蓝转红后等待新红峰D、新红极E，再外扩D触发多头。
- 红转蓝后等待新蓝峰d、新蓝极e，再外扩d触发空头。
- 转势只是授权，不是入场。

### 定式07 如何依赖阵营

- D1提供战略授权：`d1_camp` 来自上一根已收盘日线安全阵营。
- H1提供战术触发：必须通过 DS03 二四棒同向判定（`resolve_ds03_attack` 返回同向 side），触发 `LONG_CONTINUE`/`SHORT_CONTINUE`。
- D1/H1都必须分别运行完整OS。
- 只允许H1同向延续：H1启动前必须已与D1同阵营（`prev_h1_camp == d1_camp`）。
- 禁止反向并轨：不得从反向阵营破防守极完成并轨（ALIGN_TURN 已废止）。

### 定式08 如何依赖阵营

- DS08使用当前OS硬化骨架中的五点结构。
- 阵营背景必须记录和审计。
- 五点结构触发和防守点必须来自OS节点，禁止脱离OS画形态。

### 定式09 如何依赖阵营

DS09 等同股票式/A股专属版本/九重天，当前冻结口径：

多头：

```text
进入当日前已完成的D1 OS阵营为红
昨日D1为阴线
今日M15第一次 high > 昨日high 只锁定
锁定后寻找第一个M15 red_peak
red_peak 后必须形成 red_ext 防守极
之后价格二次 high > red_peak，按 max(open, red_peak) 入场
止损守 red_ext，后续红极只允许上移
```

空头：

```text
进入当日前已完成的D1 OS阵营为蓝
昨日D1为阳线
今日M15第一次 low < 昨日low 只锁定
锁定后寻找第一个M15 blue_peak
blue_peak 后必须形成 blue_ext 防守极
之后价格二次 low < blue_peak，按 min(open, blue_peak) 入场
止损守 blue_ext，后续蓝极只允许下移
```

## 5. 当前项目中的相关代码文件

核心OS文件：

- `packages/fengji_core/fengji_core/os_engine.py`：当前可复用核心包中的OS引擎，定义 `RED=1`、`BLUE=-1`、`NEUTRAL=0`、T+3、硬化峰极线、身份节点、转势事件、OS日志。
- `src/quant/os_engine.py`：兼容层，当前内容与核心OS逻辑保持一致，用于旧脚本导入。

定式调用文件：

- `packages/fengji_core/fengji_core/ds01.py` / `src/quant/ds01.py`：DS01左线、阵营方向和一棍止损。
- `packages/fengji_core/fengji_core/ds03.py` / `src/quant/ds03.py`：DS03 active high/low 与 failed peak/low。
- `packages/fengji_core/fengji_core/ds05.py` / `src/quant/ds05.py`：DS05 K2可能成极。
- `packages/fengji_core/fengji_core/ds07.py` / `src/quant/ds07.py`：DS07 D1/H1桥接和共振。
- `packages/fengji_core/fengji_core/ds09.py` / `src/quant/ds09.py`：DS09 D1 OS阵营 + M15点火；`src/quant/ds09.py` 当前为 re-export。

回测与雷达文件：

- `src/backtest_ds01.py` 至 `src/backtest_ds09.py`：各定式回测入口。
- `src/unified_whitelist_engine.py`：DS01-DS09合一总控账本。
- `src/fengji_total_radar.py`：雷达/挂单候选预览，当前已覆盖DS01、DS03、DS04、DS05、DS06、DS07、DS08；DS09雷达挂单覆盖仍待补充。

测试文件：

- `tests/test_os_engine.py`：OS基础测试。
- `tests/test_ds01.py`、`tests/test_ds03.py`、`tests/test_ds05.py`、`tests/test_ds09.py`：重点定式测试。
- `tests/test_radar_ds04.py`、`tests/test_radar_ds05.py`、`tests/test_radar_ds06.py`、`tests/test_radar_ds07.py`、`tests/test_radar_ds08.py`：雷达相关测试。

## 6. 日志与验证

阵营判断必须能导出：

```text
idx
date
camp
active_high
active_low
red_peak_idx / red_peak_price
red_ext_idx / red_ext_price
blue_peak_idx / blue_peak_price
blue_ext_idx / blue_ext_price
last_failed_high_idx / last_failed_high_price
last_failed_low_idx / last_failed_low_price
```

峰极线验证必须能导出：

```text
raw_nodes.csv
identity_nodes.csv
turns.csv
os_log.csv
```

沙盒图必须展示：

- K线。
- `hardened_fengji_line`。
- 红蓝阵营背景。
- 峰点、极点。
- 转势点。
- 买点/卖点。
- 初始止损。
- 当前防守点。
- 挂单点，若存在。

验证顺序：

1. 单元测试。
2. 小样本回测。
3. 沙盒图审计。
4. 模拟盘日志。
5. 服务器当前进程、数据新鲜度和挂单日志。

## 7. 已知问题与待确认

- `packages/fengji_core` 与 `src/quant` 存在双入口风险；当前方向是核心逻辑逐步迁入 `packages/fengji_core`，`src/quant` 做兼容层。
- DS09 旧文档曾写“D1不提供OS阵营方向”，已按用户2026-05-27最新口径修正为“D1必须提供OS战略阵营”。需要确认国内/海外服务器是否已同步。
- `src/fengji_total_radar.py` 当前未覆盖DS09雷达挂单候选，后续需要补齐 D1安全阵营 + M15 锁定/进攻峰/防守极/二次攻击流程。
- DS04开仓不使用OS阵营前置过滤，但离场和防守升级必须使用OS；后续测试需要防止该特例被误扩展到其他定式。
- 左三线已于 2026-08-13 用户审阅确认冻结（启动棍向左最近 3 段峰极线段内穿过线段数 <= 2 通过；独立术语与左30无线并存），详见最高宪法 §5.3。
- 服务器运行状态是时间敏感事实，必须实时检查，不能使用旧日志作当前结论。
