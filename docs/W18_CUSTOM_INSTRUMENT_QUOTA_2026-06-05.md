# W18 用户自选品种服务端配额计数

日期：2026-06-05

## 范围

本次只处理 W18 用户自选品种管线的服务端月度配额，不修改峰极OS、阵营转换、DS01-DS09、挂单器、模拟实盘或服务器脚本。

## 已完成

- 在 `services/db/custom_instruments.py` 增加服务端配额 helper：
  - `CUSTOM_PLAN_LIMITS = {"standard": 3, "pro": 20}`
  - `normalize_custom_plan()`
  - `custom_month_bounds()`
  - `count_custom_requests_this_month()`
  - `check_custom_request_quota()`
- 在 `POST /api/v1/custom-instruments/request` 创建请求前增加配额拦截：
  - 免费档禁止提交，返回 403。
  - 未知档位禁止提交，返回 403。
  - 标准/专业档必须带稳定 `user_id`，否则返回 400。
  - 超出当月配额返回 429。
  - 已授权请求会把 quota 快照写入 `request_json.quota`，并在响应中以 `quota` 字段返回。
- 配额计数使用 `custom_instrument_requests.created_at` 的 UTC 当前自然月窗口。
- 当前计数口径为同一 `user_id` 当月所有自选请求总数，用当前 plan 决定上限，避免仅靠前端 localStorage 统计。

## 当前限制

- 当前 plan/user 仍来自演示级前端参数，不是真实 Auth/JWT；正式上线前必须接入 W17-prod 的服务端订阅状态。
- 目前只限制月度次数，尚未实现单用户并发 1、失败重试 2 次、管理员审核。
- 当前仍只完成 crypto D1 自选拉数与回测，1H/15m 和 A 股/期货自选仍待补。
- `enable_paper` 到模拟观察 watchlist 尚未完成。

## 验证

```powershell
python -m py_compile services\api\main.py services\db\custom_instruments.py tests\test_custom_instruments.py
python -m pytest tests\test_custom_instruments.py -q
python -m pytest tests\test_custom_instruments.py tests\test_backtest_jobs.py tests\test_chart_bundle.py tests\test_context_queries.py tests\test_smoke_pg_api_consistency.py -q
```

结果：

- `tests\test_custom_instruments.py`：13 passed
- W18/W11 相关回归：22 passed

## 下一步

1. W18 第五段：实现 `enable_paper` 到模拟观察 watchlist 的安全链路。
2. 补 `paper_watchlist` 或等价表/文件，明确用户、市场、symbol、策略、周期、状态和来源 request。
3. 暂不接真实下单；只进入模拟观察。
4. 后续再补 1H/15m crypto 拉数，A 股自选和国内期货自选需等数据口径完全稳定后开放。
