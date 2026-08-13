# W18 用户自选品种 Crypto 拉数 Worker 报告

日期：2026-06-05

范围：

- `services/crypto_ingest.py`
- `services/db/custom_instruments.py`
- `services/api/main.py`
- `tests/test_custom_instruments.py`

## 1. 结论

W18 第二段已完成：当用户提交的 crypto 自选品种本地没有 D1 CSV 时，API 会创建 `ingesting` 请求，后台通过 OKX history-candles 下载 D1 数据，写入 `data/overseas_1d/{SYMBOL}.csv`，随后自动创建 backtest job，并最终轮询到 `backtested`。

本轮没有修改峰极OS、阵营转换、DS01-DS09、挂单器、模拟实盘、国内服务器或海外服务器运行逻辑。

## 2. 拉数实现

新增：

```text
services/crypto_ingest.py
```

功能：

- `okx_inst_id("xrp") -> "XRP-USDT"`
- 调用 OKX `/api/v5/market/history-candles`
- 下载 `1D`，默认约 1825 天
- 输出字段：`timestamp,open,high,low,close,volume`
- 原子写入：先写 `.tmp`，再 `os.replace`
- 输出目录：`data/overseas_1d`

## 3. API 状态流转

缺 CSV 时：

```text
POST /api/v1/custom-instruments/request
  -> status=ingesting
  -> run_custom_crypto_request_once()
  -> OKX D1 CSV 写入
  -> create_backtest_job()
  -> status=backtesting
  -> run_backtest_job_once()
  -> GET request 刷新为 backtested / failed
```

已有 CSV 时仍走上一阶段：

```text
backtesting -> backtested
```

## 4. 验证结果

编译：

```text
python -m py_compile services\api\main.py services\db\custom_instruments.py services\crypto_ingest.py tests\test_custom_instruments.py
```

聚焦测试：

```text
python -m pytest tests\test_custom_instruments.py tests\test_backtest_jobs.py -q
10 passed
```

相邻测试：

```text
python -m pytest tests\test_custom_instruments.py tests\test_backtest_jobs.py tests\test_chart_bundle.py tests\test_context_queries.py tests\test_smoke_pg_api_consistency.py -q
17 passed in 15.53s
```

真实接口 smoke：

```text
CUSTOM_INGEST_CREATED 3ae1a27e-a1fb-46f9-80cf-cdc04702876b ingesting XRPUSDT None
CUSTOM_INGEST_POLL 8 backtesting running
CUSTOM_INGEST_POLL 12 backtested succeeded
W18_CUSTOM_CRYPTO_INGEST_SMOKE_OK request=3ae1a27e-a1fb-46f9-80cf-cdc04702876b job=2dd94d9f-2444-42fb-af5c-3614a9895ebc rows=1825 bars=366
```

生成数据：

```text
data/overseas_1d/XRPUSDT.csv
rows=1825
```

## 5. 已知限制

1. 当前只下载 D1，未同步 1H/15m；因此适合 Web 回测 D1 图表与 TOTAL/DS01/DS03 当前 chart-bundle，不能声称已满足所有多周期定式实盘监测。
2. 当前使用 FastAPI BackgroundTasks，不是独立 worker/Celery/Redis。
3. 标准/专业每月配额计数未完成。
4. Web 表单未接入。
5. `enable_paper=true` 仍未创建动态 watchlist 或模拟观察任务。
6. OKX 接口失败时会写入 request `failed`，但尚未实现自动重试队列。

## 6. 下一步

- W18 第三段：Web 回测页增加“提交自选品种”入口，展示 request 状态和错误原因。
- W18 第四段：服务端配额计数，标准档 3 次/月、专业档 20 次/月。
- W18 第五段：如要支持 DS07/DS08/实盘观察，补 1H/15m 拉数与动态 watchlist。
