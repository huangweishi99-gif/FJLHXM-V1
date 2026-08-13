# W11 异步回测 Worker 后端 MVP 报告

日期：2026-06-05

范围：

- `migrations/versions/003_backtest_jobs.py`
- `services/db/models.py`
- `services/db/backtest_jobs.py`
- `services/api/main.py`
- `tests/test_backtest_jobs.py`

## 1. 结论

W11 后端 MVP 已完成：本地 PG 已新增 `backtest_jobs` 表，FastAPI 已支持提交异步回测任务和查询任务状态。

当前实现是 **FastAPI BackgroundTasks MVP**：

- `POST /api/v1/backtests` 创建 job，返回 `202`。
- job 状态从 `queued` 进入 `running`，后台调用现有 `build_chart_bundle()`。
- 成功后写回 `status=succeeded` 和 `result_json`。
- 失败后写回 `status=failed` 和 `error_message`。
- 同参数重复提交会复用最近一次成功结果，直接生成 `succeeded` 缓存 job。

本轮没有引入 Celery、Redis、独立 worker 进程，也没有修改峰极OS、阵营转换、九大定式或回测策略算法。

## 2. 数据库变更

新增 Alembic 迁移：

```text
migrations/versions/003_backtest_jobs.py
```

新增表：

```sql
backtest_jobs (
    id TEXT PRIMARY KEY,
    user_id TEXT,
    market TEXT NOT NULL,
    symbol TEXT NOT NULL,
    strategy_id TEXT NOT NULL,
    years BIGINT NOT NULL CHECK (years BETWEEN 1 AND 5),
    status TEXT NOT NULL,
    cache_key TEXT NOT NULL,
    params_json JSONB NOT NULL,
    result_json JSONB,
    error_message TEXT,
    created_at TIMESTAMPTZ DEFAULT now(),
    started_at TIMESTAMPTZ,
    finished_at TIMESTAMPTZ
)
```

索引：

- `idx_backtest_jobs_status_created`
- `idx_backtest_jobs_cache_key`
- `idx_backtest_jobs_symbol`

本地迁移结果：

```text
alembic upgrade head
Running upgrade 002 -> 003, backtest_jobs

alembic current
003 (head)
```

## 3. API

### 3.1 提交任务

```http
POST /api/v1/backtests
```

请求示例：

```json
{
  "market": "CRYPTO",
  "symbol": "ETHUSDT",
  "strategy_id": "TOTAL",
  "years": 1
}
```

说明：

- `years` 限制为 1-5。
- `strategy_id` 若不在当前 chart-bundle 支持集合 `TOTAL/DS01/DS03`，会回退为 `TOTAL`，避免未产品化定式图表包阻断任务。
- 提交前会检查本地 K 线 CSV 是否存在，缺失则返回 404。

### 3.2 查询任务

```http
GET /api/v1/backtests/{job_id}
```

返回 job 状态、参数、结果摘要和错误信息。

注意：动态路由已放在固定路由 `chart-bundle/trades/symbol-summary` 之后，避免截获已有回测页固定 API。

## 4. Job smoke

临时启动 FastAPI 后执行：

```text
POST /api/v1/backtests
GET /api/v1/backtests/{job_id}
```

结果：

```text
API_READY http://127.0.0.1:8055
JOB_CREATED 7a871ffe-d876-4dc9-9d48-7fae8c9c05a4 queued CRYPTO ETHUSDT TOTAL 1
JOB_POLL 0 queued
JOB_POLL 1 running
JOB_POLL 2 running
JOB_POLL 3 running
JOB_POLL 4 running
JOB_POLL 5 running
JOB_POLL 6 running
JOB_POLL 7 running
JOB_POLL 8 running
JOB_POLL 9 running
JOB_POLL 10 succeeded
JOB_SUCCEEDED bars=366 markers=1314 strategy=TOTAL
JOB_CACHED b84fcfb9-2437-4993-befe-d37d063b61f6 succeeded True
W11_JOB_SMOKE_OK
```

## 5. 路由 smoke

复核 `GET /api/v1/backtests/{job_id}` 没有破坏原有固定路由：

```text
ROUTE_CHART_OK DS03 366
ROUTE_SUMMARY_OK 3 AVAXUSDT
ROUTE_TRADES_OK 1 ETHUSDT
ROUTE_JOB_OK 7a871ffe-d876-4dc9-9d48-7fae8c9c05a4 succeeded
W11_ROUTE_SMOKE_OK
```

## 6. 测试

编译：

```powershell
python -m py_compile services\api\main.py services\db\models.py services\db\backtest_jobs.py migrations\versions\003_backtest_jobs.py
```

结果：通过。

单元测试：

```powershell
python -m pytest tests\test_backtest_jobs.py tests\test_context_queries.py tests\test_chart_bundle.py tests\test_smoke_pg_api_consistency.py -q
```

结果：

```text
9 passed in 15.28s
```

## 7. 已知限制

1. 当前是 FastAPI BackgroundTasks MVP，不是 Celery/Redis/独立 worker 生产实现。
2. 任务结果先存完整 `chart_bundle` 到 `result_json`，后续需要根据体积和前端读取方式拆成 metrics/trades/equity/chart 或对象存储。
3. Web 回测页尚未接入 `POST /api/v1/backtests`，仍直接调用同步 `chart-bundle`。
4. 当前 cache 只按 `market/symbol/strategy_id/years` 生成，未纳入数据文件版本、engine_version、参数版本或用户权限。
5. DS02/DS04-DS09 独立 chart-bundle 尚未产品化，提交 API 会回退 `TOTAL`。

## 8. 下一步

继续 W11 第二阶段：

- Web 回测页增加“提交回测任务”入口。
- 前端轮询 `GET /api/v1/backtests/{job_id}` 展示 queued/running/succeeded/failed。
- 成功后从 `result.bundle` 渲染 K 线、收益曲线和指标。
- 给 job 增加 engine_version/data_version/cache_version。
- 评估是否把 BackgroundTasks 替换为独立 worker 进程或 Celery/Redis。
