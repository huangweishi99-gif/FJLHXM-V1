# DS03 Calibration Record

DS03 二四棒已经完成当前项目口径下的工程审计与沙盒图人工校准。

## 当前状态

```text
CALIBRATED
```

已通过：

- DS03 已迁移到当前项目最高 OS 底座。
- `gap = 3`，不采用旧文档 `GAP=4`。
- `hardened_fengji_line` 作为物理沙盒主线。
- 同价高低点采用最新 K。
- 红阵营破红峰做多，蓝阵营破蓝峰做空。
- 极只负责防守和转势，不作为 DS03 进攻触发点。
- 国内期货 30 品种 `bad_trades = 0`。
- 沙盒图人工复核通过。

## 定式逻辑

多头：

- 开仓前一根 K 线必须已经处于红阵营。
- 以前一根 K 线可见的红峰作为触发点；工程字段为 `active_high`。
- 当前 K 线盘中刺穿该红峰。
- 成交价为 `max(open, active_high)`。
- 初始止损守二：`min(low[i-1], low[i])`。
- 动态止损守四：最近 4 根 K 线最低点，只上移不下移。

空头：

- 开仓前一根 K 线必须已经处于蓝阵营。
- 以前一根 K 线可见的蓝峰作为触发点；工程字段为 `active_low`，身份是 `BLUE_PEAK`，不是蓝极。
- 当前 K 线盘中跌破该蓝峰。
- 成交价为 `min(open, active_low)`。
- 初始止损守二：`max(high[i-1], high[i])`。
- 动态止损守四：最近 4 根 K 线最高点，只下压不上移。

## 严格版说明

当前实现不允许同一根 K 线先建立阵营、再立刻触发 DS03。  
DS03 触发必须使用上一根 K 线已经可见的阵营与进攻峰。  
日线回测无法确认同一根 K 线内先突破还是先止损，因此开仓当根不做同根止损；守四在收盘后更新，供下一根 K 线使用。

## 工程审计

国内期货 30 品种当前 OS 口径批量结果：

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

## 沙盒复核包

已生成并由用户确认正确：

```text
results/sandbox/ds03_calibration/lithium_carbonate_first8/ds03_lithium_carbonate_first8_contact.png
results/sandbox/ds03_calibration/rubber_last8/ds03_rubber_last8_contact.png
```

人工复核结论：

```text
PASS_SANDBOX_REVIEW
```

## 固化结论

```text
DS03_CALIBRATED_ON_CURRENT_FENGJI_OS
```

后续实现 DS06-DS09 或合一引擎时，不允许把 DS03 误改成破极开仓定式。若必须改 OS 底座，需要重新生成并人工复核 DS01、DS02、DS03、DS04、DS05 沙盒图，并重跑审计。
