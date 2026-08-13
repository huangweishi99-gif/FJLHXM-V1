# W18 用户自选品种管线 Crypto MVP 报告

日期：2026-06-05

范围：

- `migrations/versions/004_custom_instrument_requests.py`
- `services/db/models.py`
- `services/db/custom_instruments.py`
- `services/api/main.py`
- `tests/test_custom_instruments.py`

## 1. 结论

W18 第一段 MVP 已完成：支持用户提交 crypto 自选品种请求，在本地已有 CSV 的前提下，自动创建 `custom_instrument_requests` 记录，关联 `backtest_jobs`，并通过 GET 接口轮询到 `backtested`。

后续同日已补 W18 第二段 crypto 缺 CSV 拉数 worker，见 `docs/W18_CUSTOM_INSTRUMENT_CRYPTO_INGEST_2026-06-05.md`。本第一段报告保留为已有 CSV 闭环记录。

## 2. 数据库

新增 Alembic 迁移：

```text
migrations/versions/004_custom_instrument_requests.py
```

新增表：

```text
custom_instrument_requests
```

关键字段：

- `id`
- `user_id`
- `plan_id`
- `market`
- `symbol`
- `status`
- `strategies_json`
- `years`
- `enable_paper`
- `backtest_job_id`
- `error_message`
- `request_json`
- `created_at / updated_at / finished_at`

本地迁移结果：

```text
alembic upgrade head
004 (head)
```

## 3. API

新增：

```http
POST /api/v1/custom-instruments/request
GET  /api/v1/custom-instruments/requests/{request_id}
```

W18 MVP 当前边界：

- 只支持 `CRYPTO`。
- `ETH` 会规范化为 `ETHUSDT`；`btc-usdt` 会规范化为 `BTCUSDT`。
- 免费档请求会被拒绝。
- 若本地已有 crypto CSV，则创建关联 backtest job。
- 若本地没有 CSV，第一段记录为待补；同日第二段已改为进入 `ingesting` 并后台拉取 OKX D1 CSV，见 `docs/W18_CUSTOM_INSTRUMENT_CRYPTO_INGEST_2026-06-05.md`。

## 4. 状态流转

当前已落地：

```text
backtesting -> backtested
backtesting -> failed
```

待后续落地：

```text
queued -> ingesting -> backtesting -> backtested
backtested -> paper_enabled
```

## 5. 验证结果

编译：

```text
python -m py_compile services\api\main.py services\db\models.py services\db\custom_instruments.py migrations\versions\004_custom_instrument_requests.py
```

聚焦测试：

```text
python -m pytest tests\test_custom_instruments.py tests\test_backtest_jobs.py -q
8 passed
```

相邻测试：

```text
python -m pytest tests\test_custom_instruments.py tests\test_backtest_jobs.py tests\test_chart_bundle.py tests\test_context_queries.py tests\test_smoke_pg_api_consistency.py -q
15 passed in 13.96s
```

接口 smoke：

```text
CUSTOM_CREATED b95739fc-a2d0-4406-b9bf-333b0b147041 backtesting ETHUSDT dc8492df-dece-4e35-b8c0-eda1a4510b80
CUSTOM_POLL 0 backtested succeeded
W18_CUSTOM_CRYPTO_SMOKE_OK request=b95739fc-a2d0-4406-b9bf-333b0b147041 job=dc8492df-dece-4e35-b8c0-eda1a4510b80 bars=366
```

## 6. 已知限制

1. 本报告记录第一段已有 CSV MVP；OKX D1 拉数 worker 已在第二段补齐，但 1H/15m 仍未补。
2. 请求配额只做了免费档阻断；标准档 3 次/月、专业档 20 次/月的服务端计数尚未实现。
3. `enable_paper=true` 只记录请求，尚未创建动态 watchlist 或模拟盘观察任务。
4. 还没有 Web 表单接入；当前只能通过 API 提交。
5. 生产级并发控制、失败重试、审计日志和 Admin 审核尚未实现。

## 7. 下一步

- W18 第三段：Web 回测页增加“提交自选品种”入口，并显示 request/job 状态。
- W18 第四段：实现服务端配额计数和 `enable_paper` 到模拟观察 watchlist 的安全链路。
