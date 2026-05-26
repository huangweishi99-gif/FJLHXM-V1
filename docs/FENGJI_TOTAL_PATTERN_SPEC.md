# 峰极总定式完整规格

状态：`CANONICAL`

峰极总定式 = DS01-DS09 在当前最高峰极 OS 下的统一交易系统。

DS09（九重天，D1 + M15）已校准并纳入峰极总定式；缺少 M15 行情时仅跳过 DS09。详见 `docs/DS09_IN_TOTAL_PATTERN.md`。

## 1. 总定义

```text
峰极总定式 = 当前最高峰极OS + DS01-DS09 全部信号 + 总控账本
```

它不是第十个新定式，也不是把定式揉成一个形态；它是已校准定式的统一运行框架。

输入一个品种时，必须同时检测 DS01-DS09：

```text
出现 DS01 信号 -> 用 DS01 的入场、出场、止损
出现 DS02 信号 -> 用 DS02 的入场、出场、止损
...
出现 DS08 信号 -> 用 DS08 的入场、出场、止损
出现 DS09 信号 -> 用 DS09 的入场、出场、止损（须具备 M15 数据）
```

不得人为规定某个币种只跑某几个定式。

## 2. OS 底座

所有定式共用当前最高峰极 OS：

- 3-3 / T+3 原始峰极确认。
- 同价最高/最低取最新 K 线。
- `gap=3`，峰极之间至少 2 根完整 K 线。
- 物理峰极线为 `hardened_fengji_line`。
- 峰永远是进攻方向。
- 极永远是阵营防守点。
- 红极失守 = 红转蓝。
- 蓝极失守 = 蓝转红。
- 失败 a/f 点只允许破极后身份重定义。

## 3. 周期口径

虚拟货币当前默认周期：

```text
DS01-DS06 = D1
DS07     = D1 + H1
DS08     = H1
```

DS09 = D1 + M15，已纳入峰极总定式；旧 D1 + M5 结果全部作废，只能作为旧口径参考。

## 4. 总控账本

峰极总定式对所有定式信号做统一账本裁决：

- 同一品种未全部平仓前，不允许开反仓。
- 同一品种同方向最多 3 笔。
- 每笔仓位记录 `strategy_id`。
- 每笔仓位使用开仓定式自己的止损规则。
- 所有成交、拒单、冲突、超过 3 笔、方向禁止都写审计。
- 当前虚拟货币阶段只允许观察，不允许自动实盘下单。

输出文件：

```text
candidate_trades.csv
accepted_trades.csv
rejected_orders.csv
ledger_events.csv
strategy_bad_trades.csv
crypto_scored_accepted_trades.csv
crypto_by_strategy.csv
crypto_whitelist_summary.csv
```

## 5. 虚拟货币资金规则

默认回测资金规则：

```text
本金 = 1000 USDT
单笔保证金 = 200 USDT
默认杠杆 = 2x
最高杠杆 = 3x
保证金模式 = 逐仓
手续费估算 = 单边 0.05%
滑点估算 = 单边 0.03%
```

任何超过 3x 的结果不作为白名单准入依据。

## 6. 白名单准入

一个虚拟货币品种进入量化白名单前，必须按顺序通过：

```text
1. 有历史实盘数据
2. 峰极总定式 180 天回测
3. bad_audits = 0
4. 最大回撤不超过阈值
5. 最近 30 天前向模拟通过
6. 关键交易沙盒图人工确认
7. 才能进入正式实盘白名单
```

任何一步失败，都只能进入观察或禁用。

## 7. 新币种回测命令

```powershell
python src\batch_unified_crypto_whitelist.py `
  --symbols NEW-USDT `
  --days 180 `
  --leverage 2 `
  --margin-per-trade 200 `
  --out-dir results\fengji_total_pattern_NEW_180d
```

这个命令默认运行 DS01-DS08 全部定式。

## 8. 实时监测命令

```powershell
python src\crypto_combined_monitor.py `
  --symbols NEW-USDT `
  --lookback-hours 24 `
  --out-dir results\crypto_combined_monitor
```

实时监测输出中的 `strategy_id` 表示触发的是哪个定式。

## 9. 禁止事项

```text
禁止把分定式过滤结果当成主系统
禁止指定某币只跑某几个定式作为正式口径
禁止未通过前向模拟直接实盘
DS09 与 DS01-DS08 一并计入峰极总定式白名单判断；无 M15 数据时 DS09 不参与
禁止自动下真实订单
```
