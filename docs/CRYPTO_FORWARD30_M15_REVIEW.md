# Crypto Forward 30D Review - M15

状态：`REVIEWED`

目的：在 180 天历史结构预热基础上，只统计最近 30 天入场交易，验证回测候选白名单是否具备前向稳定性。

## 基础口径

- 总定式：DS01-DS09
- DS09：D1 + M15
- 本金：`1000 USDT`
- 单笔保证金：`200 USDT`
- 杠杆：`2x`
- 评分窗口：最近 30 天
- 结构预热窗口：180 天

## 全定式前向结果

| symbol | trades | total_return | max_drawdown | bad_audits | 结论 |
|---|---:|---:|---:|---:|---|
| ETH-USDT | 18 | -2.81% | -4.83% | 0 | 全定式前向未通过 |
| XRP-USDT | 15 | -7.07% | -7.01% | 0 | 全定式前向未通过 |
| SOL-USDT | 17 | -10.53% | -9.21% | 0 | 全定式前向未通过 |

## 正贡献定式过滤结果

| symbol | allowed strategies | trades | total_return | max_drawdown | 结论 |
|---|---|---:|---:|---:|---|
| ETH-USDT | DS01,DS03,DS05,DS07,DS08,DS09 | 19 | -0.27% | -2.93% | 接近打平，仍未通过 |
| XRP-USDT | DS03,DS07,DS08,DS09 | 14 | -3.12% | -2.97% | 未通过 |
| SOL-USDT | DS01,DS03,DS07 | 12 | -6.90% | -5.53% | 未通过 |

## 超严格观察口径

这是事后过滤得到的观察口径，不能直接作为实盘准入依据，只能进入继续前向观察。

| symbol | allowed strategies | trades | total_return | max_drawdown | bad_audits | 结论 |
|---|---|---:|---:|---:|---:|---|
| ETH-USDT | DS08,DS09 | 8 | +0.80% | -0.29% | 0 | 观察中的前向候选 |
| XRP-USDT | DS09 | 4 | +0.19% | -0.32% | 0 | 观察中的前向候选，样本太少 |

## 当前结论

- 不允许把 ETH/SOL/XRP 直接升级为正式实盘白名单。
- ETH-USDT 只允许继续观察 `DS08,DS09`。
- XRP-USDT 只允许继续观察 `DS09`。
- SOL-USDT 前向未通过，降级观察/暂停。
- 下一步应做实时监测层，但默认只提示，不自动下真实仓。
