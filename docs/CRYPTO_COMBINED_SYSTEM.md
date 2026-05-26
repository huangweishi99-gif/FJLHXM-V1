# Crypto FengJi Total Pattern System

状态：`CANONICAL`

本文件明确主系统口径：DS01-DS09 合并后正式命名为“峰极总定式”，避免误解为“某个币只跑某几个定式”。

DS09（D1 + M15）已纳入峰极总定式；监测与回测前须拉取 15m 数据，见 `docs/DS09_IN_TOTAL_PATTERN.md`。

## 核心原则

```text
输入一个虚拟货币品种
先拉取历史实盘K线
再用峰极总定式统一回测
出现哪个定式信号，就使用哪个定式的买卖逻辑和止损规则
```

主系统不允许：

```text
人为指定 ETH 只跑 DS08/DS09
人为指定 XRP 只跑 DS09
把分定式过滤结果当成正式白名单准入
没有历史实盘数据就进入量化白名单
没有峰极总定式回测就进入量化白名单
```

## 总控规则

- DS01-DS09 全部同时检测（DS09 需 M15）。
- 同品种未全部平仓前，不允许开反仓。
- 同品种同方向最多 3 笔。
- 每笔仓位绑定来源定式 `strategy_id`。
- 每笔仓位使用开仓定式自己的止损规则。
- 所有成交、拒单、冲突写审计表。
- 当前只允许观察信号，不允许自动实盘下单。

## 新币种回测

当要求回测一个新币种时，使用全定式入口：

```powershell
python src\batch_unified_crypto_whitelist.py `
  --symbols NEW-USDT `
  --days 180 `
  --leverage 2 `
  --margin-per-trade 200 `
  --out-dir results\unified_crypto_new_symbol_m15
```

这个命令默认使用峰极总定式，即 DS01-DS09 全部定式（自动拉取 15m）。

## 实时监测

当要求监测一个币种时，使用全定式入口：

```powershell
python src\crypto_combined_monitor.py `
  --symbols NEW-USDT `
  --lookback-hours 24 `
  --out-dir results\crypto_combined_monitor
```

输出中 `strategy_id` 说明当前触发的是哪个定式。

## 研究观察口径

`src/crypto_realtime_monitor.py` 和 `data/crypto_m15_forward_observation_rules.csv` 只是研究观察工具。

它们不得作为主系统，不得替代峰极总定式。
