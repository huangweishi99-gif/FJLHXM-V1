# Crypto Realtime Monitor - M15

状态：`OBSERVATION_ONLY`

本模块用于虚拟货币观察名单实时监测，不自动下单。

## 当前监测范围

读取文件：`data/crypto_m15_forward_observation_rules.csv`

```text
ETH-USDT -> DS08,DS09
XRP-USDT -> DS09
```

## 硬规则

- 默认刷新 OKX 历史实盘K线。
- DS09 使用 `D1 + M15`。
- 只监测前向观察口径，不监测已失败或禁用品种。
- 输出信号也只标记为 `OBSERVE_SIGNAL_ONLY`。
- `auto_trade` 永远为 `DISABLED`，不允许自动实盘下单。
- 监测窗口以最新 M15 K线时间为基准，不以最近历史信号时间为基准。

## 运行命令

```powershell
python src\crypto_realtime_monitor.py `
  --lookback-hours 24 `
  --out-dir results\crypto_realtime_monitor
```

## 输出

```text
results/crypto_realtime_monitor/latest_monitor_signals.csv
results/crypto_realtime_monitor/<run_id>/monitor_signals.csv
```

## 最近一次监测

时间：2026-05-20 北京时间午间。

```text
ETH-USDT = NO_SIGNAL
XRP-USDT = NO_SIGNAL
auto_trade = DISABLED
```
