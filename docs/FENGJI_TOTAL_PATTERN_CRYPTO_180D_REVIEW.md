# 峰极总定式虚拟货币 180D 回测审查

状态：`REVIEWED`

本轮按峰极总定式正式规格重跑：

```text
DS01-DS09 全部启用
DS09 = D1 + M15
本金 = 1000 USDT
单笔保证金 = 200 USDT
杠杆 = 2x
数据 = OKX 历史实盘K线
窗口 = 180 天
```

输出目录：

```text
results/fengji_total_pattern_default_180d_m15
```

## 结果

| symbol | total_return | max_drawdown | trades | bad_audits | 分层 |
|---|---:|---:|---:|---:|---|
| ETH-USDT | +23.84% | -14.92% | 103 | 0 | 回测候选白名单 |
| AVAX-USDT | +10.45% | -21.84% | 90 | 0 | 观察，回撤超 20% |
| SOL-USDT | +8.21% | -16.28% | 93 | 0 | 回测候选白名单 |
| XRP-USDT | +7.84% | -18.22% | 99 | 0 | 回测候选白名单 |
| LINK-USDT | +5.80% | -23.64% | 101 | 0 | 观察，回撤超 20% |
| DOGE-USDT | -3.66% | -19.46% | 102 | 0 | 暂不进入白名单 |
| BTC-USDT | -3.79% | -7.51% | 56 | 0 | 暂不进入白名单 |
| BNB-USDT | -6.73% | -13.60% | 104 | 0 | 暂不进入白名单 |
| LTC-USDT | -19.14% | -20.68% | 110 | 0 | 暂不进入白名单 |
| ADA-USDT | -37.30% | -37.01% | 105 | 0 | 黑名单/禁用 |

## 分层名单

回测候选白名单：

```text
ETH-USDT
SOL-USDT
XRP-USDT
```

观察名单：

```text
AVAX-USDT
LINK-USDT
```

禁用/暂不进入：

```text
ADA-USDT
BTC-USDT
DOGE-USDT
BNB-USDT
LTC-USDT
```

## 结论

本轮峰极总定式 180 天回测筛出 3 个回测候选白名单：`ETH-USDT`、`SOL-USDT`、`XRP-USDT`。

但这只是历史回测初筛，不等于正式实盘白名单。正式实盘前仍必须通过最近 30 天前向模拟和沙盒图确认。
