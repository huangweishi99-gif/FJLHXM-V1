# W18 Watchlist Runtime Preview Cache

日期：2026-06-05

## 范围

本段完成 watchlist runtime 只读信号预览的第一版缓存层，目标是避免 Web 监测页每次刷新都重复执行重型 `chart_bundle` preview。

安全边界不变：

- 不写 `paper_state`。
- 不创建 fills / closes。
- 不触发挂单。
- 不重启国内/海外服务器。
- 不修改峰极OS、阵营转换、DS01-DS09、风控或挂单规则。

## 实现

文件：`services/watchlist_runtime.py`

新增：

- `WATCHLIST_SIGNAL_PREVIEW_CACHE_TTL_SECONDS = 300`
- 进程内 `_SIGNAL_PREVIEW_CACHE`
- `clear_watchlist_signal_preview_cache()`
- `_signal_preview_cache_key()`

缓存 key 绑定：

- D1 CSV 绝对路径
- D1 CSV `mtime_ns`
- D1 CSV `size`
- preview 策略：`TOTAL`
- preview 窗口：`1` 年

因此，只要 D1 CSV 文件发生变化，cache key 会自然变化，不会继续复用旧 preview。

## 返回字段

`signal_preview` 新增：

```json
{
  "cache": {
    "status": "miss|hit",
    "ttl_seconds": 300,
    "generated_at": "..."
  },
  "data_version": {
    "path": "...",
    "mtime_ns": 0,
    "size": 0
  }
}
```

说明：

- `miss`：本次执行真实 `chart_bundle` preview。
- `hit`：本次复用进程内缓存。
- `data_version`：用于追溯当前 preview 绑定的数据版本。

## 测试

新增测试：

- `test_watchlist_signal_preview_uses_cache_for_unchanged_d1_csv`

覆盖：

- 第一次 preview 为 `cache.status=miss`
- 第二次同一 D1 CSV 为 `cache.status=hit`
- `build_chart_bundle()` 只调用一次

## 验证

已执行：

```powershell
python -m py_compile services\watchlist_runtime.py services\api\main.py
python -m pytest tests\test_custom_instruments.py -q
python -m pytest tests\test_custom_instruments.py tests\test_monitor_quotes.py tests\test_monitor_domestic.py -q
python -m pytest tests\test_custom_instruments.py tests\test_monitor_quotes.py tests\test_monitor_domestic.py tests\test_backtest_jobs.py tests\test_chart_bundle.py tests\test_context_queries.py tests\test_smoke_pg_api_consistency.py -q
```

结果：

- `tests/test_custom_instruments.py`：26 passed
- monitor 相关回归：30 passed
- 最终相关回归：39 passed

真实 XRPUSDT cache smoke：

```text
W18_SIGNAL_PREVIEW_CACHE_SMOKE ready miss hit True ...
```

## 限制

- 当前是进程内 TTL cache，不是跨进程持久化 cache。
- API 服务重启后 cache 会清空。
- 尚未拆为后台 worker/job。
- 尚未为 A股、期货、美股自选品种建立 runtime preview。

## 下一步

1. 设计并落地 runtime 后台 Job：避免 HTTP 请求直接承担 preview 计算。
2. 将 cache 从进程内推进到 PG 或文件级持久缓存，明确失效规则。
3. 扩展市场：A股、国内期货、更多 crypto 数据源。
4. 与 W16-WS 对齐：由后台 runtime job 推送更新到 WebSocket。
