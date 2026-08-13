# W18 用户自选品种 Crypto D1/H1/M15 多周期拉数

日期：2026-06-05

## 范围

本次扩展用户自选 crypto 拉数能力，从仅 D1 扩展为 D1/H1/M15 三周期。只处理数据准备，不修改峰极OS、阵营转换、DS01-DS09、现有挂单器、现有模拟盘进程或服务器脚本。

## 已完成

- `services/crypto_ingest.py` 新增统一多周期拉数：
  - `normalize_timeframe()`
  - `fetch_okx_candle_rows()`
  - `ingest_crypto_timeframe_csv()`
  - `ingest_crypto_timeframes()`
  - `crypto_timeframe_csv_path()`
  - `missing_crypto_timeframes()`
- 保留兼容入口 `ingest_crypto_daily_csv()`，仍可按旧逻辑只拉 D1。
- 多周期默认写入：
  - D1：`data/overseas_1d/{SYMBOL}.csv`
  - H1：`data/1h/{SYMBOL}.csv`
  - M15：`data/15m/{SYMBOL}.csv`
- `POST /api/v1/custom-instruments/request` 现在会检查 D1/H1/M15 任一缺失；只要有缺失，就先创建 `ingesting` 请求并后台补齐多周期。
- `run_custom_crypto_request_once()` 改为调用 `ingest_crypto_timeframes()`，拉完 D1/H1/M15 后再创建 backtest job。
- `request_json.missing_timeframes` 会记录创建请求时缺失的周期，便于审计。

## 数据格式

CSV 字段仍保持：

- `timestamp`
- `open`
- `high`
- `low`
- `close`
- `volume`

时间格式：

- D1：`YYYY-MM-DD`
- H1/M15：UTC `YYYY-MM-DD HH:MM:SS`

## 验证

```powershell
python -m py_compile services\crypto_ingest.py services\api\main.py services\db\custom_instruments.py tests\test_custom_instruments.py
python -m pytest tests\test_custom_instruments.py -q
python -m pytest tests\test_custom_instruments.py tests\test_backtest_jobs.py tests\test_chart_bundle.py tests\test_context_queries.py tests\test_smoke_pg_api_consistency.py -q
```

结果：

- `tests\test_custom_instruments.py`：18 passed
- W18/W11 相关回归：27 passed

真实 OKX smoke：

```text
W18_CRYPTO_MULTI_TF_INGEST_OK XRPUSDT
D1: rows=1825 end=2026-06-04
H1: rows=8760 end=2026-06-05 01:00:00
M15: rows=8640 end=2026-06-05 01:15:00
```

## 当前限制

- H1 默认拉 365 天，M15 默认拉 90 天；不是全历史。
- 当前 Web 回测图仍主要使用 D1 chart-bundle；H1/M15 为后续 watchlist runtime binding、准实时观察和多周期定式准备。
- OKX 网络请求仍由 FastAPI BackgroundTasks 执行，生产化需要独立 worker/队列和重试。
- 当前仅支持 crypto；A 股、国内期货自选拉数仍待后续。

## 下一步

1. 设计并实现 watchlist runtime binding：读取 `paper_watchlist.pending_runtime`，生成只读模拟信号流。
2. Web 监测页接入用户 watchlist，明确区分“观察候选”和“实际模拟持仓”。
3. 增加暂停/取消 watchlist 接口。
4. 后续补独立 worker、失败重试和 Admin 审核。
