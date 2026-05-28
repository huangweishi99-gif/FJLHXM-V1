# DS09 纳入峰极总定式

状态：`CANONICAL`

自 2026-05-25 起，**DS09 九重天** 正式纳入峰极总定式，与 DS01–DS08 一并默认检测。

## 定式口径

```text
DS09 = D1 OS战略阵营 + 昨日D1战略边界 + M15 执行
副周期 = 15m（禁止再用 5m 旧口径）
一日一结构：每个 session_date 最多消费一次 DS09
股票式/A股专属版本 = 当前 DS09 九重天口径，不另立一套A股买卖规则
```

## 当前冻结逻辑

多头：

```text
进入当日前已完成的 D1 OS 阵营为红
昨日 D1 为阴线，昨日 high 为 P1
今日 M15 第一次 high > P1 只锁定，不入场
锁定后寻找 lock_idx 之后的第一个 M15 red_peak，作为 P2
P2 后必须形成 red_ext 防守极 V
价格二次 high > P2 时，按 max(open, P2) 入场做多
止损守 red_ext，后续红极只允许上移
```

空头：

```text
进入当日前已完成的 D1 OS 阵营为蓝
昨日 D1 为阳线，昨日 low 为 V1
今日 M15 第一次 low < V1 只锁定，不入场
锁定后寻找 lock_idx 之后的第一个 M15 blue_peak，作为向下进攻点
blue_peak 后必须形成 blue_ext 防守极 P
价格二次 low < blue_peak 时，按 min(open, blue_peak) 入场做空
止损守 blue_ext，后续蓝极只允许下移
```

## 数据要求

| 市场 | 日线 | 15 分钟 |
|------|------|---------|
| 海外 crypto | `{SYMBOL}_1D_{N}d.csv` | `{SYMBOL}_15m_{N}d.csv` |
| 国内期货 | `{品种}_日线_*.csv` | `{品种}_15m.csv` 或 `*15m*.csv` |
| A 股 | 日线库 / CSV | `{code}_15m_qfq.csv`（暂无则自动跳过 DS09） |

缺少 M15 时，合一引擎对 DS09 记 `data_missing`，**不影响** DS01–DS08 运行。

## 拉取 crypto 15m 数据

```powershell
python scripts\fetch_crypto_m15_for_ds09.py --symbols DEFAULT --days 180
python scripts\fetch_crypto_m15_for_ds09.py --symbols ETH-USDT,BTC-USDT --days 1825 --refresh
```

## 回测命令

单品种总定式（含 DS09）：

```powershell
python src\unified_whitelist_engine.py `
  --symbol ETH `
  --daily-csv data\crypto_okx\ETH-USDT_1D_180d.csv `
  --h1-csv data\crypto_okx\ETH-USDT_1H_180d.csv `
  --m15-csv data\crypto_okx\ETH-USDT_15m_180d.csv `
  --out-dir results\unified_ds09_smoke\ETH
```

加密白名单批量（默认已含 DS09）：

```powershell
python src\batch_unified_crypto_whitelist.py `
  --symbols ETH-USDT `
  --days 180 `
  --out-dir results\unified_crypto_ds09_test
```

期货 DS09 批量（需自备 M15 CSV）：

```powershell
python src\batch_backtest_ds09.py `
  --d1-dir "D:\...\实盘数据日K线" `
  --m15-dir "D:\...\5-60分钟csv" `
  --m15-pattern "*15m*.csv" `
  --out-dir results\ds09_real_m15_futures
```

## 默认策略列表

代码常量：`FENGJI_TOTAL_PATTERN_STRATEGIES` / `DEFAULT_STRATEGIES_CSV`（`src/unified_whitelist_engine.py`）

```text
DS01,DS02,DS03,DS04,DS05,DS06,DS07,DS08,DS09
```
