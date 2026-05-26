# Crypto Unified DS01-DS09 Review - 180D

状态：`SUPERSEDED_BY_DS09_M15_REVISION`

重要更正：2026-05-19 用户校正 DS09 副周期应为 15分钟线，不是 5分钟线。本文件中包含 DS09=5m 的总定式回测结果，不能作为最终白名单准入依据，只能作为旧口径参考。必须按 D1 + M15 重跑后重新评审。

本轮目的：用九定式合一总控，在 OKX 历史实盘K线上初筛虚拟货币白名单。

## 固定风控参数

- 本金：`1000 USDT`
- 单笔保证金：`200 USDT`
- 杠杆：`2x`
- 手续费估算：单边 `0.05%`
- 滑点估算：单边 `0.03%`
- 保证金模式口径：逐仓
- 同品种未平仓前不允许开反仓
- 同品种同向最多 3 笔
- 定式来源：`DS01-DS09`
- OS 底座：当前最高峰极 OS

## 数据口径

- 数据源：OKX 历史实盘K线
- 回测窗口：180 天
- 周期：
  - D1：180 根
  - H1：4320 根
  - M5：51840 根，旧口径，已作废
- 输出文件：
  - `results/unified_crypto_core_180d_combined.csv`
  - `results/unified_crypto_whitelist_core_180d/ETH-USDT`
  - `results/unified_crypto_whitelist_core_180d/SOL-USDT`
  - `results/unified_crypto_whitelist_btc_180d/BTC-USDT`

## 初筛结果

| symbol | total_return | max_drawdown | trades | win_rate | liquidations | bad_audits | 初判 |
|---|---:|---:|---:|---:|---:|---:|---|
| ETH-USDT | +22.32% | -13.65% | 84 | 34.52% | 0 | 0 | 回测候选白名单 |
| SOL-USDT | +10.67% | -15.42% | 81 | 30.86% | 0 | 0 | 回测候选白名单 |
| BTC-USDT | -4.44% | -7.29% | 64 | 34.38% | 0 | 0 | 暂不进入白名单 |

## 分定式观察

ETH-USDT：

- 正贡献：DS01、DS03、DS05、DS07、DS08。
- 拖累：DS02、DS04。
- DS09 在本轮无接受交易。

SOL-USDT：

- 正贡献：DS01、DS03、DS07。
- 拖累：DS02、DS04、DS05、DS08。
- DS09 在本轮无接受交易。

BTC-USDT：

- 正贡献：DS05、DS07。
- 拖累：DS01、DS02、DS03、DS04、DS06、DS08、DS09。
- 总收益为负，不能进入量化白名单。

## 白名单准入结论

本轮只完成“历史实盘数据 + 总定式回测”的初筛。

ETH-USDT 与 SOL-USDT 只能进入 `回测候选白名单`，不能直接实盘。继续升级为正式白名单前，必须完成：

- 至少 3 张关键交易沙盒图人工确认。
- 前向模拟不少于 30 天。
- 继续保持 `bad_audits=0`。
- 无强平。
- 最大回撤不超过账户可承受阈值。

BTC-USDT 本轮不通过，保留观察，不进入量化白名单。
