# DS02 Calibration Record

DS02 阴阳相吃已经完成当前项目口径下的工程审计与沙盒图人工校准。

## 当前状态

```text
CALIBRATED
```

已通过：

- DS02 已迁移到当前项目最高 OS 底座。
- `gap = 3`，不采用旧文档 `GAP=4`。
- `hardened_fengji_line` 作为物理沙盒主线。
- 同价高低点采用最新 K。
- 红蓝阵营方向审计通过：红阵营只做多，蓝阵营只做空。
- 国内期货 30 品种 `bad_trades = 0`。
- 沙盒图人工复核通过。

## 定式逻辑

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

## 工程审计

国内期货 30 品种当前 OS 口径批量结果：

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

## 沙盒复核包

已生成并由用户确认正确：

```text
results/sandbox/ds02_calibration/lithium_carbonate_first8/ds02_lithium_carbonate_first8_contact.png
results/sandbox/ds02_calibration/rubber_last8/ds02_rubber_last8_contact.png
```

覆盖样本：

```text
碳酸锂前 8 笔：早期 DS02 信号、空头与多头混合、初始双K止损与动态止损。
橡胶后 8 笔：后段盈利样本、多空混合、红蓝阵营方向与出场路径。
```

人工复核结论：

```text
PASS_SANDBOX_REVIEW
```

## 固化结论

```text
DS02_CALIBRATED_ON_CURRENT_FENGJI_OS
```

后续实现 DS03-DS09 时，不允许为了其他定式修改 DS02 已校准行为。若必须改 OS 底座，需要重新生成并人工复核 DS01、DS02、DS05 沙盒图，并重跑方向审计。
