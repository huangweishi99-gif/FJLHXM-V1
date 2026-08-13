# W11 异步回测 Web 接入报告

日期：2026-06-05

范围：

- `web/js/app.js`
- `web/backtest.html`

## 1. 结论

W11 Web 接入已完成本地 MVP：回测页不再直接调用同步 `chart-bundle` 作为主加载链路，而是先提交异步回测任务，再轮询任务状态，成功后使用 `result.bundle` 渲染 K 线、收益曲线、指标和买卖点。

本轮没有修改峰极OS、阵营转换、DS01-DS09、挂单器、模拟实盘、国内服务器或海外服务器运行逻辑。

## 2. 前端变更

`web/js/app.js` 新增共享 API 函数：

- `submitBacktestJob({ market, symbol, strategyId, years })`
- `fetchBacktestJob(jobId)`

`web/backtest.html` 调整：

- `loadAll()` 改为提交 `POST /api/v1/backtests`。
- 轮询 `GET /api/v1/backtests/{job_id}`。
- 支持状态文案：`回测任务已提交`、`回测任务排队中`、`回测计算中`、失败原因。
- 成功后读取 `finalJob.result.bundle` 渲染图表。
- 交易明细继续从 `/api/v1/backtests/trades` 读取，保持 PG 交易上下文链路不变。
- 当前图表背景仍固定使用 `TOTAL`，用户选择的定式继续用于交易明细过滤。

## 3. 验证结果

前端语法：

```text
node --check web\js\app.js
node --check web\js\config.js
node --check web\js\chart.js
BACKTEST_INLINE_SCRIPT_PARSE_OK=1
```

测试：

```text
python -m pytest tests\test_backtest_jobs.py tests\test_context_queries.py tests\test_chart_bundle.py tests\test_smoke_pg_api_consistency.py -q
9 passed in 18.84s
```

API smoke：

```text
JOB_CREATED 20cdde35-ba26-48de-8f40-92708d476d1f succeeded None
W11_WEB_API_SMOKE_OK bars=366 markers=1314 strategy=TOTAL
```

静态检查：

- `web/backtest.html` 主加载链路已调用 `FengJiApp.submitBacktestJob()`。
- `web/backtest.html` 轮询链路已调用 `FengJiApp.fetchBacktestJob()`。
- `web/backtest.html` 未再直接出现同步 `chart-bundle` 请求。

## 4. 已知限制

1. 当前后端仍是 FastAPI `BackgroundTasks` MVP，不是 Celery/Redis/独立 worker。
2. `backtest_jobs.cache_key` 尚未纳入数据版本、engine_version、参数版本或用户权限。
3. DS02/DS04-DS09 独立 chart-bundle 仍未产品化；Web 图表背景继续使用 `TOTAL`，交易明细按用户选择定式过滤。
4. 本轮未做浏览器截图级验收；需要后续用真实浏览器检查 queued/running 状态展示和加载体验。

## 5. 下一步

- W18 用户自选品种管线：先 crypto，后 A 股。
- W11 后续生产化：独立 worker、任务取消/重试、cache version、engine_version/data_version、用户权限与任务配额。
- W16-WS：把模拟监测从轮询升级为 WebSocket/准实时推送。
