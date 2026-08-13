# W18 Watchlist Runtime 多市场只读快照

日期：2026-06-05

## 范围

本轮只扩展 `paper_watchlist` runtime 的本地 CSV 只读快照能力，不修改峰极OS最高宪法、阵营转换、DS01-DS09、挂单器、模拟实盘 `paper_state`、国内/海外服务器运行态。

## 已完成

- `services/watchlist_runtime.py` 新增按市场配置的 runtime 周期：
  - `CRYPTO`：继续读取 `D1/H1/M15`。
  - `A_STOCK`：读取 `D1`。
  - `FUTURES`：读取 `D1`。
  - `US_STOCK`：读取 `D1`。
- 新增 `runtime_timeframe_csv_candidates()` / `runtime_timeframe_csv_path()`，统一解析本地 CSV：
  - A股：`data/a_stock/{code}_1D_qfq.csv`，回退 `{code}_1D.csv`、`{code}.csv`。
  - 国内期货：优先 `data/futures/1d/{中文名}.csv`，再回退短代码、`USDT` 变体、`data/futures_lc/1d`、`data/1d`。
  - 美股：`data/us_stock/{symbol}_1D.csv`，回退 `{symbol}.csv`。
  - Crypto：沿用 `services/crypto_ingest.py` 的 D1/H1/M15 路径。
- 非 crypto 市场当前只返回只读数据快照，不接入 `signal_preview`；避免把 crypto D1 chart-bundle preview 口径误用于 A股、期货或美股。
- 修复 `services.watchlist_runtime` 作为包导入时的同目录模块路径问题，避免直接 smoke 时找不到 `crypto_ingest`。

## 当前输出

当本地 D1 CSV 存在且 OHLC 合法时，runtime 返回：

- `runtime_status=ready`
- `current_price`
- `latest_time`
- `timeframes.D1.ok=true`
- `signals[].message = D1 data ready for read-only observation`

当 D1 CSV 缺失时，runtime 返回：

- `runtime_status=data_missing`
- `timeframes.D1.error=missing_csv`
- `signals[].missing_timeframes=["D1"]`

## 验证

- `python -m py_compile services\watchlist_runtime.py services\api\main.py`：通过。
- `python -m pytest tests\test_custom_instruments.py -q`：32 passed。
- `python -m pytest tests\test_custom_instruments.py tests\test_monitor_quotes.py tests\test_monitor_domestic.py -q`：36 passed。
- `python -m pytest tests\test_custom_instruments.py tests\test_monitor_quotes.py tests\test_monitor_domestic.py tests\test_backtest_jobs.py tests\test_chart_bundle.py tests\test_context_queries.py tests\test_smoke_pg_api_consistency.py -q`：45 passed。
- 本地真实 CSV smoke：
  - `A_STOCK 000021`：ready。
  - `FUTURES LC`：ready。
  - `FUTURES LH`：ready。
  - `US_STOCK AAPL`：ready。
  - `CRYPTO XRPUSDT`：ready，仍返回 D1/H1/M15。

## 限制

- A股、国内期货、美股暂不接入只读信号预览。
- 本轮不新增数据拉取 worker，不做后台调度，不改 `paper_state`。
- 如果 watchlist 里登记的非 crypto 品种没有对应本地 D1 CSV，只会返回 `data_missing`，不会自动下载。

## 下一步

- 主线进入 W16-WS：WebSocket/准实时监测推送。
- 后续如要把非 crypto 接入信号预览，必须先明确对应市场的 chart-bundle/策略审计口径，不能直接复用 crypto preview 假定。
