# DS02 Draft

DS02 阴阳相吃已完成当前项目最高 OS 口径下的工程审计与沙盒图人工校准。

## 继承关系

DS02 必须继承当前项目最高 OS：

- `hardened_fengji_line`
- 当前红蓝阵营转换规则
- 当前峰极确认与硬化规则
- `gap = 3`
- 同价最新

旧文档只参考 DS02 自身买卖逻辑，不参考旧 OS、旧 `GAP=4` 或旧 Runtime。

## 当前买卖逻辑

多头：

- 必须处于红阵营。
- K1 为阴线。
- K2 为阳线。
- K2 收盘价高于 K1 最高价。
- K2 收盘确认后，次日开盘做多。
- 初始止损守 K1/K2 两根 K 线共同最低点。
- 动态止损只用阳线低点上移，阴线不推动止损。

空头：

- 必须处于蓝阵营。
- K1 为阳线。
- K2 为阴线。
- K2 收盘价低于 K1 最低价。
- K2 收盘确认后，次日开盘做空。
- 初始止损守 K1/K2 两根 K 线共同最高点。
- 动态止损只用阴线高点下移，阳线不推动止损。

## 状态

```text
CALIBRATED
```

## 当前工程审计

国内期货 30 品种已跑通当前 OS 口径：

```text
result_dir  = results/ds02_real_daily_futures
rows        = 30
trades      = 4682
bad_trades  = 0
net_pnl     = 13847.0345
median_ret  = -9.75%
```

表现较好的样本：

```text
橡胶 +163.11%
生猪 +129.51%
碳酸锂 +42.43%
棉花 +41.32%
硅铁 +23.75%
螺纹钢 +23.45%
```

表现较差的样本：

```text
沪镍 -86.56%
菜油 -51.48%
鸡蛋 -49.53%
红枣 -37.66%
菜粕 -35.64%
```

沙盒图已生成并人工确认正确，检查项包括 K1/K2、次日开盘入场、双K初始止损、顺方向K线尾部移动止损和阵营方向。

```text
results/sandbox/ds02_calibration/lithium_carbonate_first8/ds02_lithium_carbonate_first8_contact.png
results/sandbox/ds02_calibration/rubber_last8/ds02_rubber_last8_contact.png
```

冻结记录见：

```text
docs/DS02_CALIBRATION.md
```
