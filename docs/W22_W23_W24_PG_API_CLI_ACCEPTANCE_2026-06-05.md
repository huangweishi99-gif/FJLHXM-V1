# W22/W23/W24 PG/API/CLI 对账验收报告

日期：2026-06-05

范围：

- `services/api/main.py`
- `services/db/context_queries.py`
- `web/backtest.html`
- `scripts/smoke_pg_api_consistency.py`
- `tests/test_context_queries.py`
- `tests/test_smoke_pg_api_consistency.py`
- `tests/test_context_stats_calibration.py`
- `tests/test_chart_bundle.py`

## 1. 结论

W22/W23/W24 在 API/PG/CLI smoke 与 Web 字段链路层通过。

本轮完成：

- PG vs API 信号强弱一致性从 W14 的 6 条扩展到 12 条，覆盖 A股、虚拟货币、期货、美股各 3 条。
- 四市场端点链路通过：`symbol-summary`、`trades`、`signals/{trade_id}/strength`、`bucket-trades`、`buckets`、`chart-bundle`。
- Web CSV 字段链路补齐 `exit_price`，避免交易明细和同桶 CSV 导出时平仓价列为空。
- `symbol-summary` 增加 `has_chart_data`，前端默认优先选择有本地 K 线 CSV 的样本，避免 PG 有样本但图表数据缺失的品种阻断页面。
- 回测页图表请求固定为 `TOTAL`，交易明细仍按用户选择的定式筛选，避免 DS02/DS04-DS09 尚未实现 chart-bundle 时阻断 Web 页面。

本轮不修改峰极OS、阵营转换、DS01-DS09 策略逻辑、雷达、挂单器或模拟实盘执行逻辑。

## 2. PG 数据基线

当前本地 PG 容器：

```text
fengji_pg Up healthy 0.0.0.0:5432->5432/tcp
```

当前 PG 样本分布：

```text
trade_context_snapshots:
A_STOCK 43690
CRYPTO 5899
FUTURES 8658
US_STOCK 133594

context_bucket_stats:
A_STOCK 1413
CRYPTO 1363
FUTURES 1261
US_STOCK 1689
```

说明：数据用于 Web 信号强弱、同桶样本、bucket 展示和对账 smoke；统计结果只用于展示和筛选，不反向修改峰极OS、九大定式或风控。

## 3. PG/API 一致性

执行：

```powershell
python scripts\smoke_pg_api_consistency.py --port 8053 --sample-plan A_STOCK=3,CRYPTO=3,FUTURES=3,US_STOCK=3
```

结果：

```text
PG_API_CONSISTENCY_OK=12/12
A_STOCK=3
CRYPTO=3
FUTURES=3
US_STOCK=3
base_url=http://127.0.0.1:8053
```

对账字段包含：

- `trade_id`
- `strategy_id`
- `market`
- `symbol`
- `setup_key`
- `entry_time`
- `net_pnl`
- `r_multiple`
- `bucket_key`
- `signal_tier`
- `bucket_count`
- `bucket_win_rate_smoothed`
- `signal_score`

## 4. 端点链路 smoke

临时启动 FastAPI 后，四市场端点链路结果：

```text
ENDPOINT_SMOKE_CHECKS=24
ENDPOINT_SMOKE_OK
```

关键输出：

```text
SUMMARY A_STOCK count=20 chartable=20 top=2475 dt=0.19s
TRADES A_STOCK/2475 count=5 exit_price_key=True dt=0.06s
STRENGTH A_STOCK/2475 tier=INSUFFICIENT_DATA bucket_count=29 dt=0.03s
BUCKET_TRADES A_STOCK/2475 count=2 exit_price_key=True dt=0.06s
BUCKETS A_STOCK/DS07 count=5 dt=0.05s
CHART A_STOCK/2475/TOTAL bars=726 markers=1068 dt=9.81s

SUMMARY CRYPTO count=17 chartable=8 top=AVAXUSDT dt=0.04s
TRADES CRYPTO/SOLUSDT count=5 exit_price_key=True dt=0.07s
STRENGTH CRYPTO/SOLUSDT tier=INSUFFICIENT_DATA bucket_count=2 dt=0.08s
BUCKET_TRADES CRYPTO/SOLUSDT count=2 exit_price_key=True dt=0.21s
BUCKETS CRYPTO/DS01 count=5 dt=0.05s
CHART CRYPTO/SOLUSDT/TOTAL bars=1097 markers=1248 dt=12.34s

SUMMARY FUTURES count=15 chartable=15 top=豆粕 dt=0.09s
TRADES FUTURES/豆粕 count=5 exit_price_key=True dt=0.05s
STRENGTH FUTURES/豆粕 tier=INSUFFICIENT_DATA bucket_count=15 dt=0.06s
BUCKET_TRADES FUTURES/豆粕 count=4 exit_price_key=True dt=0.32s
BUCKETS FUTURES/DS02 count=5 dt=0.03s
CHART FUTURES/豆粕/TOTAL bars=170 markers=130 dt=1.42s

SUMMARY US_STOCK count=20 chartable=20 top=AAPL dt=0.29s
TRADES US_STOCK/AAPL count=5 exit_price_key=True dt=0.06s
STRENGTH US_STOCK/AAPL tier=WEAK bucket_count=1780 dt=0.06s
BUCKET_TRADES US_STOCK/AAPL count=5 exit_price_key=True dt=0.11s
BUCKETS US_STOCK/DS01 count=5 dt=0.06s
CHART US_STOCK/AAPL/TOTAL bars=753 markers=1188 dt=11.54s
```

## 5. 本轮修复

### 5.1 Web CSV 平仓价字段

问题：

- `web/backtest.html` 的 CSV 列包含 `exit_price`。
- PG 表没有独立 `exit_price` 列，但导入时会把 CSV 非核心字段保存在 `context_json`。
- API 原先没有把 `context_json.exit_price` 透传到 `trades` 和 `bucket-trades` 返回，导致 CSV 平仓价列为空。

修复：

- `services/db/context_queries.py` 新增 `_context_float()`，从 `context_json` 安全解析 `exit_price`。
- `list_trades_with_strength()` 与 `list_bucket_trades()` 均返回 `exit_price`。
- `tests/test_context_queries.py` 增加解析测试。

### 5.2 样本概览与图表数据可用性

问题：

- `symbol-summary` 由 PG 样本生成，可能返回 PG 有样本但本地缺 K 线 CSV 的品种，例如本轮 crypto top 为 `AVAXUSDT`，但本地未找到对应日线 CSV。
- 用户点选这类品种时，交易明细可返回，但 chart-bundle 会 404。

修复：

- `services/api/main.py` 增加 `_with_chart_data_flag()`。
- `/api/v1/backtests/symbol-summary` 返回 `has_chart_data` 与 `chart_source_file`。
- `web/backtest.html` 样本列表对缺 K 线品种显示“缺K线”，默认选择时优先选择有图表数据的品种。

### 5.3 DS02-DS09 chart-bundle 阻断

问题：

- 当前 `src/chart_bundle.py` 只完整支持 `TOTAL`、`DS01`、`DS03`。
- 回测页订阅档位允许选择 DS02-DS09；如果图表请求直接使用该定式，会出现 `chart-bundle not implemented`。

修复：

- `web/backtest.html` 图表包固定请求 `TOTAL`。
- 交易明细 API 仍按用户选择的定式筛选。
- 页面语义为：用峰极总定式图表作为背景和 OS 展示，右侧交易明细按当前选择定式过滤。

## 6. 测试与静态验证

执行：

```powershell
python -m pytest tests\test_smoke_pg_api_consistency.py tests\test_context_queries.py tests\test_context_stats_calibration.py tests\test_chart_bundle.py -q
```

结果：

```text
11 passed in 15.31s
```

Python 编译：

```powershell
python -m py_compile services\api\main.py services\db\context_queries.py
```

结果：通过。

前端脚本检查：

```powershell
node --check web\js\app.js
node --check web\js\config.js
node --check web\js\chart.js
BACKTEST_INLINE_SCRIPT_PARSE_OK=1
```

结果：通过。

## 7. 已知限制

1. `TOTAL chart-bundle` 仍为同步计算，A股、crypto、美股样本耗时约 9.8-12.3 秒，用户体验和生产稳定性都应由 W11 异步 Worker/缓存解决。
2. DS02/DS04-DS09 的独立 chart-bundle 尚未产品化；当前 Web 图表使用 `TOTAL` 兜底，交易明细仍可按定式筛选。
3. crypto PG 样本中部分品种缺本地日线 CSV；本轮只做 `has_chart_data` 标记和前端优先选择，不自动下载补齐。
4. 本轮仍是本地 PG + 本地 FastAPI 验收，不代表生产 PG、正式用户权限、正式支付或多用户隔离已完成。

## 8. 下一步

进入 **W11 `POST /backtests` 异步回测 Worker**：

- 建立 `backtest_jobs` 状态流转。
- 将当前同步 chart-bundle/回测计算迁入 Worker 或缓存管线。
- Web 提交回测后显示 queued/running/succeeded/failed。
- 记录失败原因、缓存键、订阅年限限制。
- 避免 10 秒级同步图表/回测计算阻塞页面。
