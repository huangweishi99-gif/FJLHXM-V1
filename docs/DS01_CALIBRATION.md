# DS01 Calibration Record

DS01 挫棍已经完成当前项目口径下的工程审计与沙盒图人工校准。

## 当前状态

```text
CALIBRATED
```

已通过：

- DS01 已迁移到当前项目最高 OS 底座。
- 首仓方向审计通过：红阵营只做多，蓝阵营只做空。
- 首仓左 30 无线过滤在触发价位置检查，已通过抽样和批量审计。
- 续棍不要求左 30 无线，最多 3 笔，已在订单数据中出现。
- 国内期货 30 品种 `bad_trades = 0`。
- 国内期货 30 品种 `future_violations = 0`。
- 一棍止损口径已确认。
- 沙盒图人工复核通过。

## 止损口径对照

本轮新增两个 DS01 止损模式用于对照：

```text
one_bar  = 当前旧回测口径，持仓后用上一根K线高/低点推进止损
trigger  = 固定守触发K高/低点，续棍后改守最新触发K高/低点
```

DS01 正式止损口径：

```text
多头开仓后，先守前一天信号K线最低点。
当日收盘后，把次日止损移动到当日最低点。
空头开仓后，先守前一天信号K线最高点。
当日收盘后，把次日止损移动到当日最高点。
```

这就是当前工程里的 `stop_mode=one_bar`。

国内期货 30 品种对照：

```text
one_bar:
  trades            = 5957
  bad_trades        = 0
  future_violations = 0
  net_pnl           = -859486.3945
  median_return     = -15.70%

trigger:
  trades            = 1639
  bad_trades        = 0
  future_violations = 0
  net_pnl           = -2351338.378
  median_return     = -94.13%
```

对照文件：

```text
results/ds01_stop_mode_comparison.csv
```

## 关键否决样本

棉花 trigger 模式第 67 笔：

```text
entry_date = 2016-04-12
exit_date  = 2020-03-19
direction  = long
entries    = 3
net_pnl    = -7059.14
```

沙盒图：

```text
results/sandbox/ds01_cotton_trigger_trade_67.png
```

这笔交易显示，固定守触发K会导致 DS01 挫棍跨多年持仓，并承受极大浮动风险。该行为不适合作为当前 DS01 校准口径。

## 当前结论

```text
REJECT_TRIGGER_STOP_AS_CURRENT_CALIBRATION_BASELINE
CONFIRM_ONE_BAR_STOP_AS_DS01_STOP_RULE
```

## 沙盒复核包

已按 `stop_mode=one_bar` 重新生成 DS01 沙盒图：

```text
results/sandbox/ds01_onebar_calibration/cotton_last7/cotton_last7_contact.png
results/sandbox/ds01_onebar_calibration/silicon_iron_first5/silicon_iron_first5_contact.png
results/sandbox/ds01_onebar_calibration/rapeseed_oil_last7/rapeseed_oil_last7_contact.png
```

覆盖样本：

```text
棉花最后 7 笔：红阵营多头、续棍、盈利与亏损退出。
硅铁前 5 笔：蓝阵营空头、红阵营多头、空头镜像止损。
菜油最后 7 笔：多空混合与不同峰极结构。
```

图中 `one-bar stop` 已按次日生效口径绘制：

```text
进场当天守前一天信号K线低/高点。
当日收盘后，次日才移动到当日低/高点。
```

人工复核结论：

```text
PASS_SANDBOX_REVIEW
```

## 固化结论

```text
DS01_CALIBRATED_ON_CURRENT_FENGJI_OS
```

后续实现 DS02-DS09 时，不允许为了其他定式修改 DS01 已校准行为。若必须改 OS 底座，需要重新生成并人工复核 DS01 沙盒图，并重跑国内期货 30 品种方向审计与未来函数审计。
