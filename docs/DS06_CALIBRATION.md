# DS06 Calibration - 政权革命 / 外扩峰

状态：`CALIBRATED`

校准依据：用户已确认 DS06 沙盒图正确。

## 当前最高 OS 迁移

- DS06 继承当前峰极 OS 最高宪法。
- 旧文档只读取 DS06 自身买卖逻辑，不读取旧 OS。
- 当前物理峰极线使用 `hardened_fengji_line`。
- 当前峰极间隔使用 `gap=3`，不是旧文档里的 `gap=4`。
- 同价高低点按当前 OS 规则取最新 K。

## 多头逻辑

1. 原先处于蓝阵营。
2. 价格向上突破旧蓝极，触发 `BLUE_TO_RED`。这只是转势授权，不是入场。
3. 转红后等待新红峰 D：D 必须是确认后的物理 `HIGH`。
4. D 确认后等待新红极 E：E 必须是 D 之后确认的物理 `LOW`，且 `D_price > E_price`。
5. E 确认前如果价格已经向上外扩 D，旧 D 作废，重新等待新的 D。
6. E 确认后，第一根 `high > D_price` 的 K 线是 F 外扩峰启动棍，按 `max(open, D_price)` 入场。
7. 初始止损守 K1/K2 低点，后续继承 DS03 最近 4 根 K 低点移动防守。

## 空头逻辑

1. 原先处于红阵营。
2. 价格向下跌破旧红极，触发 `RED_TO_BLUE`。这只是转势授权，不是入场。
3. 转蓝后等待新蓝峰 d：d 必须是确认后的物理 `LOW`。
4. d 确认后等待新蓝极 e：e 必须是 d 之后确认的物理 `HIGH`，且 `d_price < e_price`。
5. e 确认前如果价格已经向下外扩 d，旧 d 作废，重新等待新的 d。
6. e 确认后，第一根 `low < d_price` 的 K 线是 f 外扩峰启动棍，按 `min(open, d_price)` 入场。
7. 初始止损守 K1/K2 高点，后续继承 DS03 最近 4 根 K 高点移动防守。

## 审计硬条件

- 多头：`turn < D < E < entry`，`D_confirm < E_idx`，`E_confirm < entry`，`D_price > E_price`。
- 空头：`turn < d < e < entry`，`d_confirm < e_idx`，`e_confirm < entry`，`d_price < e_price`。
- 入场不是破旧极，而是 E/e 确认后的第一根外扩 D/d。
- 沙盒图必须显示 `TURN`、`D/d`、`D_CONFIRM`、`E/e`、`E_CONFIRM`、`F/f_ENTRY`、旧防守极和 DS03 守4止损线。

## 本轮校准结果

- 本地 30 个日线期货样本批量通过。
- `bad_trades=0`。
- 沙盒图样本：`results/sandbox/ds06/橡胶_trade_1.png` 至 `results/sandbox/ds06/橡胶_trade_7.png`。
