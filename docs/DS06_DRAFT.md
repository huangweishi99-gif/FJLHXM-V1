# DS06 Draft - 政权革命 / 外扩峰

状态：`PROMOTED_TO_CALIBRATED`

本草案已在用户确认 DS06 沙盒图正确后升级为正式校准记录。最终口径见 `docs/DS06_CALIBRATION.md`。

## 当前最高 OS 迁移

- 使用当前峰极 OS 最高宪法，不使用旧文档的 `gap=4`。
- 当前物理线为 `hardened_fengji_line`，`gap=3`，峰极点之间至少 2 根完整 K 线隔离。
- 旧文档只保留 DS06 自身买卖逻辑：破旧极转势后，等待新阵营 D/E 结构，再交易第一根外扩 D/d 的启动棍。

## 多头

1. 原先在蓝阵营。
2. 蓝极被向上突破，发生 `BLUE_TO_RED`。这只是转势，不入场。
3. 转红后等待新红峰 D：D 必须是确认后的物理 `HIGH`，且 `point_idx`、`confirm_idx` 都在转势 K 之后。
4. D 确认后等待新红极 E：E 必须是 D 之后确认的物理 `LOW`，且 `D_price > E_price`。
5. E 确认前如果价格已经向上外扩 D，旧 D 作废，重新等待新的 D。
6. E 确认后，第一根 `high > D_price` 的 K 线为 F 外扩峰启动棍，按 `max(open, D_price)` 成交。
7. 初始止损守 K1/K2 低点，后续继承 DS03 最近 4 根 K 低点移动防守。

## 空头

1. 原先在红阵营。
2. 红极被向下突破，发生 `RED_TO_BLUE`。这只是转势，不入场。
3. 转蓝后等待新蓝峰 d：d 必须是确认后的物理 `LOW`，且 `point_idx`、`confirm_idx` 都在转势 K 之后。
4. d 确认后等待新蓝极 e：e 必须是 d 之后确认的物理 `HIGH`，且 `d_price < e_price`。
5. e 确认前如果价格已经向下外扩 d，旧 d 作废，重新等待新的 d。
6. e 确认后，第一根 `low < d_price` 的 K 线为 f 外扩峰启动棍，按 `min(open, d_price)` 成交。
7. 初始止损守 K1/K2 高点，后续继承 DS03 最近 4 根 K 高点移动防守。

## 审计硬条件

- 多头：`turn < D < E < entry`，`D_confirm < E_idx`，`E_confirm < entry`，`D_price > E_price`。
- 空头：`turn < d < e < entry`，`d_confirm < e_idx`，`e_confirm < entry`，`d_price < e_price`。
- 入场不是破旧极，而是 E/e 确认后的第一根外扩 D/d。
- 沙盒图必须标出 `TURN`、`D/d`、`D_CONFIRM`、`E/e`、`E_CONFIRM`、`F/f_ENTRY`、旧防守极、DS03 守4止损线。
