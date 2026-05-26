# DS03 Draft

DS03 二四棒已完成当前项目最高 OS 口径下的工程审计与沙盒图人工校准。

## 继承关系

DS03 必须继承当前项目最高 OS：

- `hardened_fengji_line`
- 当前红蓝阵营转换规则
- 当前峰极确认与硬化规则
- `gap = 3`
- 同价最新

旧文档只参考 DS03 自身买卖逻辑，不参考旧 OS、旧 `GAP=4` 或旧 Runtime。

## 当前买卖逻辑

多头：

- 开仓前一根 K 线必须已经处于红阵营。
- 以前一根 K 线可见的 `active_high` 作为触发峰。
- 当前 K 线盘中刺穿该 `active_high`。
- 成交价为 `max(open, active_high)`。
- 初始止损守二：`min(low[i-1], low[i])`。
- 动态止损守四：最近 4 根 K 线最低点，只上移不下移。

空头：

- 开仓前一根 K 线必须已经处于蓝阵营。
- 以前一根 K 线可见的蓝峰作为触发点；工程字段为 `active_low`，但身份是 `BLUE_PEAK`，不是蓝极。
- 当前 K 线盘中跌破该 `active_low`。
- 成交价为 `min(open, active_low)`。
- 初始止损守二：`max(high[i-1], high[i])`。
- 动态止损守四：最近 4 根 K 线最高点，只下压不上移。

## 严格版说明

当前实现不使用旧文档的 `GAP=4`。  
当前实现不允许同一根 K 线先建立阵营、再立刻触发 DS03。  
DS03 触发必须使用上一根 K 线已经可见的阵营与 `active_high / active_low`。

日线回测无法知道同一根 K 线内先突破还是先止损，因此开仓当根不做同根止损；守四在收盘后更新，供下一根 K 线使用。

## 状态

```text
CALIBRATED
```

## 当前工程审计

国内期货 30 品种已跑通当前 OS 口径：

```text
result_dir  = results/ds03_real_daily_futures
rows        = 30
bad_trades  = 0
failed      = 0
```

表现较好的样本：

```text
橡胶 +195.99%
生猪 +163.61%
棉花 +101.91%
碳酸锂 +93.27%
PTA +58.43%
氧化铝 +42.38%
玻璃 +38.57%
LPG +35.20%
```

表现较差的样本：

```text
沪镍 -87.88%
鸡蛋 -45.70%
乙二醇 -31.45%
红枣 -26.20%
菜粕 -19.36%
菜油 -18.59%
焦煤 -17.16%
豆粕 -8.44%
```

该结果符合 DS03 推进型定式特征：趋势连续推进品种表现较好，高插针、高反杀品种表现较差。

## 当前沙盒复核包

已生成 DS03 沙盒图，并由用户确认正确：

```text
results/sandbox/ds03_calibration/lithium_carbonate_first8/ds03_lithium_carbonate_first8_contact.png
results/sandbox/ds03_calibration/rubber_last8/ds03_rubber_last8_contact.png
```

人工检查项：上一根已授权阵营、刺穿红峰/蓝峰、成交价、守二、守四、出场路径。

冻结记录见：

```text
docs/DS03_CALIBRATION.md
```
