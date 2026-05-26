# DS04 Calibration Record

DS04 夹棍/隔山炮已经完成当前项目口径下的工程审计与沙盒图人工校准。

## 当前状态

```text
CALIBRATED
```

已通过：

- DS04 已迁移到当前项目最高 OS 底座。
- `gap = 3`，不采用旧文档 `GAP=4`。
- `hardened_fengji_line` 作为物理沙盒主线。
- 同价高低点采用最新 K。
- DS04 特例口径已确认：开仓方向由三K夹棍夺权结构决定，不使用 OS 阵营方向作为前置过滤。
- DS04 仍使用当前 OS 做峰极线、阵营背景、身份点、红极/蓝极防守升级和沙盒审计。
- 国内期货 30 品种 `bad_trades = 0`。
- 沙盒图人工复核通过。

## OS 特例口径

DS04 是抄底摸顶型三K夺权定式，不是阵营内顺势推进定式。

```text
DS04_OPEN_DIRECTION = K1/K2/K3_RECLAIM_STRUCTURE
DS04_NO_CAMP_DIRECTION_FILTER = TRUE
DS04_STILL_USES_CURRENT_FENGJI_OS = TRUE
```

这与当前最高 OS 不矛盾：OS 负责峰极、阵营背景、身份点、防守极升级与审计；DS04 自身结构负责开仓方向。

## 定式逻辑

多头：

- K1 为阳线。
- K2 为阴线。
- K3 为阳线。
- K2 实体长度严格小于 K1/K3，且全长不大于 K1/K3。
- K1/K2/K3 均不得与前一根形成价格缺口。
- K3 收盘价突破 K1 最高价。
- K4 开盘做多。
- 初始防守为 K1/K2/K3 三根 K 线最低点。
- 后续只接受更高的红极升级防守。

空头：

- K1 为阴线。
- K2 为阳线。
- K3 为阴线。
- K2 实体长度严格小于 K1/K3，且全长不大于 K1/K3。
- K1/K2/K3 均不得与前一根形成价格缺口。
- K3 收盘价跌破 K1 最低价。
- K4 开盘做空。
- 初始防守为 K1/K2/K3 三根 K 线最高点。
- 后续只接受更低的蓝极升级防守。

## 工程审计

国内期货 30 品种当前 OS 口径批量结果：

```text
result_dir  = results/ds04_real_daily_futures
rows        = 30
bad_trades  = 0
failed      = 0
```

表现较好的样本：

```text
碳酸锂 +132.61%
沪镍 +107.05%
棉花 +94.46%
焦煤 +37.59%
PTA +35.82%
合成橡胶 +24.39%
锰硅 +23.77%
烧碱 +20.29%
```

表现较差的样本：

```text
生猪 -80.27%
鸡蛋 -60.66%
LPG -52.20%
菜油 -44.04%
红枣 -30.28%
螺纹钢 -29.68%
纸浆 -22.16%
硅铁 -21.49%
```

## 沙盒复核包

已生成并由用户确认正确：

```text
results/sandbox/ds04_calibration/lithium_carbonate_first7/ds04_lithium_carbonate_first7_contact.png
results/sandbox/ds04_calibration/cotton_first7/ds04_cotton_first7_contact.png
```

覆盖样本：

```text
碳酸锂前 7 笔：强白名单样本，多空混合，覆盖三K初始防守与防守升级。
棉花前 7 笔：较稳样本，多空混合，覆盖 K4 开盘执行和红极/蓝极升级防守。
```

人工复核结论：

```text
PASS_SANDBOX_REVIEW
```

## 固化结论

```text
DS04_CALIBRATED_ON_CURRENT_FENGJI_OS
```

后续实现 DS06-DS09 或合一引擎时，不允许把 DS04 误改成红多蓝空顺势过滤定式。若必须改 OS 底座，需要重新生成并人工复核 DS01、DS02、DS04、DS05 沙盒图，并重跑审计。
