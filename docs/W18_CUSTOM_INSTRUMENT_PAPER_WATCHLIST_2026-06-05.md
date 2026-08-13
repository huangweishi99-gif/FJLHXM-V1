# W18 用户自选品种 enable_paper 模拟观察 Watchlist

日期：2026-06-05

## 范围

本次实现用户自选品种 `enable_paper=true` 后的模拟观察登记链路。只登记观察候选，不接真实下单，不改峰极OS、阵营转换、DS01-DS09、现有挂单器、现有模拟盘进程或服务器脚本。

## 已完成

- 新增 Alembic 迁移 `005_paper_watchlist.py`，创建 `paper_watchlist` 表。
- 新增 ORM 模型 `PaperWatchlist`。
- 新增 DB helper `services/db/paper_watchlist.py`：
  - `create_or_get_paper_watchlist_entry()`
  - `list_paper_watchlist()`
  - 默认状态 `pending_runtime`
- `custom_instrument_requests` 状态刷新逻辑增强：
  - 回测 job 成功且 `enable_paper=false`：状态变为 `backtested`。
  - 回测 job 成功且 `enable_paper=true`：登记 watchlist，状态变为 `paper_enabled`。
  - watchlist 元信息写入 `request_json.paper_watchlist`，响应顶层返回 `paper_watchlist`。
- `run_custom_crypto_request_once()` 在后台回测结束后主动刷新 request，确保缺 CSV 拉数链路也能自动进入 `paper_enabled`。
- 新增只读接口：
  - `GET /api/v1/paper-watchlist?user_id=...&status=pending_runtime`

## 数据结构

`paper_watchlist` 当前字段：

- `id`
- `request_id`
- `user_id`
- `plan_id`
- `market`
- `symbol`
- `name`
- `strategies_json`
- `status`
- `source`
- `params_json`
- `created_at`
- `updated_at`

当前 `status=pending_runtime` 表示“已登记为模拟观察候选，但尚未绑定真实运行中的雷达/模拟盘调度器”。

## 安全边界

- 不启动真实实盘。
- 不调用交易所下单。
- 不写入现有国内/海外 `paper_state`。
- 不改变现有固定 SYMBOLS 监测列表。
- 不把 API Key、Token、服务器密码、Webhook 写入文档或代码。

## 验证

```powershell
python -m py_compile services\api\main.py services\db\custom_instruments.py services\db\paper_watchlist.py services\db\models.py tests\test_custom_instruments.py migrations\versions\005_paper_watchlist.py
python -m pytest tests\test_custom_instruments.py -q
python -m pytest tests\test_custom_instruments.py tests\test_backtest_jobs.py tests\test_chart_bundle.py tests\test_context_queries.py tests\test_smoke_pg_api_consistency.py -q
python -m alembic upgrade head
```

结果：

- `tests\test_custom_instruments.py`：16 passed
- W18/W11 相关回归：25 passed
- Alembic：`004 -> 005` 成功
- 端到端 smoke：
  - `W18_ENABLE_PAPER_SMOKE_OK ... status=paper_enabled watchlist=1 symbol=ETHUSDT`

## 当前限制

- Watchlist 只登记候选，尚未被雷达/模拟盘运行时消费。
- 当前只支持 crypto 自选品种链路。
- 还没有用户级 watchlist 数量限制、并发控制、取消观察、暂停/恢复观察接口。
- 正式上线前必须接 W17-prod 的服务端 Auth/订阅，不应继续信任前端传入的 `user_id/plan_id`。

## 下一步

1. 补 crypto 1H/15m 多周期拉数，为后续观察提供更完整数据。
2. 设计 watchlist runtime binding：由后台任务读取 `paper_watchlist.pending_runtime`，生成只读模拟信号流。
3. 增加取消观察/暂停观察接口。
4. 后续 Web 监测页读取 watchlist，并明确区分“用户观察候选”和“实际模拟持仓”。
