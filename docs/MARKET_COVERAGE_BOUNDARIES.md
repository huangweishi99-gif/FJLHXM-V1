# 市场数据覆盖边界（A股 60m · 国内期货日夜盘）

更新时间：2026-07-07

本文固化 Phase 2 **D6** 口径：哪些定式在数据不足时必须降级、国内期货数据泵窗口、各品种夜盘结束参考时刻。不替代交易所公告；细则冲突时以交易所为准。

## 1. A股 60 分钟（H1）与定式门槛

| 定式 | 最低数据要求 | 数据不足时 |
|------|-------------|-----------|
| DS01–DS06 | 日线 D1 | 可运行（日线定式） |
| DS07、DS08 | D1 + H1/60m ≥ **500** 根 | **跳过** DS07/DS08 |
| DS09 | D1 + M15 ≥ **800** 根 | **跳过** DS09 |

工程常量见 `fengji_core.market_coverage`：

- `A_STOCK_H1_MIN_ROWS_DS07_DS08 = 500`
- `A_STOCK_M15_MIN_ROWS_DS09 = 800`

### 已知缺口

- 东方财富等源下载 60m 时，常见仅 **~128 根**（约 1 个月），不足以做 DS07/DS08 **历史级**结论。
- `src/backtest_a_stock_fengji.py` 已接入 `filter_strategies_for_a_stock_data()`：H1 行数不足时自动降级为 DS01–DS06。
- A股 **无夜盘**；若未来单独跑 A股数据泵，使用 `MARKET_MODE=astock` 与 `A_STOCK_WINDOWS`（见 `data_manager_futures.py`）。

### 正式筛选临时口径（2026-07-07）

在补齐更长 60m 历史或接入替代数据源之前：

- **板块/批量回测报告**中，H1&lt;500 的股票标注 `h1_coverage=partial`，DS07/DS08 结果 **不得** 作为全历史验收依据。
- 雷达/模拟实盘：国内期货侧已用 15m/1h/1d 真泵数据；A股若仅日线缓存，雷达应只输出 DS01–DS06 相关信号（待独立 A股泵上线后复查）。

## 2. 国内期货数据泵运行窗口

来源：`data_manager_futures.py` → `FUTURES_WINDOWS` / `is_market_update_time()`。

| 窗口 | 本地时间 | 星期 | 说明 |
|------|---------|------|------|
| 日盘上午 | 08:30 – 11:35 | 一至五 | 开盘前 30min 开始抓取 |
| 日盘下午 | 13:00 – 15:15 | 一至五 | 收盘后略延 |
| 夜盘上段 | 20:30 – 23:59 | 一至五 | 21:00 开盘前预热 |
| 夜盘下段 | 00:00 – 02:35 | 二至六 | 覆盖最长夜盘品种 |

非上述窗口：`IDLE_SLEEP_SECONDS=60`，不写 CSV。

`MARKET_MODE=astock` 时使用 `A_STOCK_WINDOWS`（09:00–11:35、12:30–15:05，仅工作日）。

## 3. 国内期货品种夜盘结束参考表

数据泵按 **最长夜盘 02:30** 统一运行；下表供 DS09 `session_date`、夜盘验收与人工审计参考。

夜盘开盘统一 **21:00**；日盘见 `FUTURES_DAY_SESSION`。

| 夜盘结束 | 品种代码 |
|---------|---------|
| **23:00** | SA FG CJ OI SH SR SF MA TA UR CF PG LH JD PP EB EG JM M P V SI LC |
| **23:30** | RB FU SP RU BR |
| **01:00** | NI AO EC |
| **02:30** | AU AG SC |

代码表：`fengji_core.market_coverage.FUTURES_NIGHT_END_BY_SYMBOL`。

DS09 夜盘 session 映射见 `fengji_core.ds09.assign_cn_futures_session_date` 与 `docs/LC_DS09_ACCEPTANCE.md`。

## 4. 验收

```powershell
python scripts\verify_d6_market_coverage_boundaries.py
python -m pytest tests\test_market_coverage_boundaries.py -q
```

报告目录：`results/sandbox/d6_phase2_YYYYMMDD/`（`d6_report.json` + `SUMMARY.md`）。

## 5. 相关文档

- `峰极OS_数据与回测说明.md` §1 股票数据已知限制
- `docs/RADAR_REFRESH_SCHEDULE.md` — 雷达/泵刷新频率
- `docs/PENDING_ORDER_CANCEL_RULES.md` — 挂单撤销规则（D5）
