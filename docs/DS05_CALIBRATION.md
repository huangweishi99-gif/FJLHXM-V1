# DS05 Calibration Record

DS05 指形战法已经完成当前项目口径下的校准。

## 校准结论

状态：

```text
CALIBRATED
```

校准依据：

- 玻璃最近半年峰极线与红蓝阵营检查通过。
- 棉花最近一年峰极线与红蓝阵营检查通过。
- PVC 最近一年峰极线与红蓝阵营已生成供检查。
- 棉花最后 7 笔 DS05 沙盒图检查通过。
- 2026-05-19 重新按 `RED_EXT / BLUE_EXT` 防守极唯一口径生成 DS05 复核沙盒图，检查通过。
- 30 个国内期货品种回测中 `bad_trades = 0`。
- 10 个热门虚拟货币回测中 `bad_trades = 0`。

## 固化规则

DS05 必须继承当前项目最高 OS：

- 3-3 / T+3 原始峰极确认。
- 同价最高/最低取最新K线。
- 峰极间至少隔 2 根完整K线。
- 物理主线为 `hardened_fengji_line`。
- 红极失守红转蓝，蓝极失守蓝转红。
- a/f 失败点只在破极后身份重定义。

DS05 自身买卖逻辑：

- 红阵营只做多，蓝阵营只做空。
- K2/K3 必须同阵营。
- K2 必须靠近当前阵营防守极：多头只锚定 `RED_EXT`，空头只锚定 `BLUE_EXT`。
- K3 夺权后触发。
- 初始止损守 K2。
- 动态止损只用顺方向K线尾部推进。

## 2026-05-19 复核沙盒图

已将 DS05 沙盒图标注从旧的 `active extreme` 改为明确的防守极口径：

```text
多头 = RED_EXT defense
空头 = BLUE_EXT defense
```

复核结果：

```text
棉花：101 笔，bad_trades = 0
沪镍：59 笔，bad_trades = 0
```

复核图：

```text
results/sandbox/ds05_recheck/cotton_last7/棉花_日线_5年_last7_contact.png
results/sandbox/ds05_recheck/nickel_last7/沪镍_日线_5年_last7_contact.png
```

人工复核结论：

```text
PASS_SANDBOX_REVIEW
```

## 回测口径

国内期货：

```text
初始资金 = 100000
每次开仓 = 固定 1 手
手续费 = 成交额万分之一
滑点 = 每次成交 1 tick 不利滑点
```

虚拟货币：

```text
初始资金 = 1000 U
每笔保证金 = 200 U
杠杆 = 5 倍
手续费 = 万分之五
滑点 = 万分之三
```

## 防误伤原则

后续实现 DS01-DS09 时，不允许修改 DS05 已校准行为。

若必须改 OS 底座，需要重新生成并人工复核：

- 玻璃结构图
- 棉花结构图
- 棉花最后 7 笔沙盒图
- 国内期货 30 品种 `bad_trades`
- 热门虚拟币 10 品种 `bad_trades`
