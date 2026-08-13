# W18 Watchlist Runtime Job MVP

日期：2026-06-05

## 范围

本段完成 watchlist runtime 后台 Job / 文件级缓存 MVP。目标是让 Web 监测页优先读取预计算缓存，缓存不存在时再回退到 HTTP 内实时计算。

安全边界：

- 不写 `paper_state`。
- 不创建 fills / closes。
- 不触发挂单。
- 不真实下单。
- 不重启国内/海外服务器。
- 不修改峰极OS、阵营转换、DS01-DS09、风控或挂单规则。

## 实现

### 文件级缓存 helper

新增文件：`services/watchlist_runtime_file_cache.py`

能力：

- `runtime_cache_path(user_id, cache_dir=None)`
- `load_watchlist_runtime_cache(user_id, cache_dir=None)`
- `save_watchlist_runtime_cache(user_id, payload, cache_dir=None)`

安全处理：

- `user_id` 会转为安全文件名。
- 写入使用 `.tmp` 原子替换。
- 默认缓存目录：`runtime/watchlist_runtime_cache/`
- 可通过环境变量 `FENGJI_WATCHLIST_RUNTIME_CACHE_DIR` 覆盖。

### 后台 job 脚本

新增文件：`scripts/run_watchlist_runtime_job.py`

用法：

```powershell
python scripts\run_watchlist_runtime_job.py --user-id demo-user --limit 100
```

参数：

- `--user-id`：必填。
- `--status`：默认 `pending_runtime`。
- `--limit`：默认 100。
- `--cache-dir`：可选输出目录。
- `--no-signal-preview`：只生成轻量 snapshot，不跑 preview。

输出 payload：

- `user_id`
- `mode=read_only_observation`
- `runtime_binding=file_cache_signal_preview`
- `status_filter`
- `generated_at`
- `count`
- `items`

### API 优先读缓存

文件：`services/api/main.py`

`GET /api/v1/paper-watchlist/runtime` 新增 query：

```text
prefer_runtime_cache=true|false
```

行为：

- `prefer_runtime_cache=false`：沿用原逻辑。
- `prefer_runtime_cache=true`：
  - 如果文件缓存存在且 `status_filter` 匹配，直接返回缓存。
  - 如果缓存不存在或状态不匹配，回退到实时构建。

返回字段新增：

```json
{
  "runtime_cache": {
    "status": "hit|miss|bypass",
    "source": "file|null"
  }
}
```

### Web 接入

文件：

- `web/js/app.js`
- `web/monitor.html`

改动：

- `fetchPaperWatchlistRuntime()` 新增 `preferRuntimeCache`。
- 监测页请求 runtime 时启用：
  - `includeSignalPreview: true`
  - `preferRuntimeCache: true`
- 缓存不存在时，后端自动回退实时计算，页面不报错。

## 测试

新增测试：

- `test_watchlist_runtime_file_cache_roundtrip`
- `test_get_paper_watchlist_runtime_prefers_file_cache_when_enabled`

覆盖：

- 文件缓存写入/读取。
- `user_id` 文件名安全化。
- API 命中文件缓存时不再调用 DB list helper。
- API 按 `limit` 裁剪缓存 items。

## 验证

已执行：

```powershell
python -m py_compile services\watchlist_runtime_file_cache.py services\watchlist_runtime.py services\api\main.py scripts\run_watchlist_runtime_job.py
python -m pytest tests\test_custom_instruments.py -q
node --check web\js\app.js
node -e "const fs=require('fs'); const html=fs.readFileSync('web/monitor.html','utf8'); const blocks=[...html.matchAll(/<script>([\s\S]*?)<\/script>/g)].map(m=>m[1]); new Function(blocks.join('\n')); console.log('MONITOR_INLINE_SCRIPT_PARSE_OK=1');"
python -m pytest tests\test_custom_instruments.py tests\test_monitor_quotes.py tests\test_monitor_domestic.py -q
python -m pytest tests\test_custom_instruments.py tests\test_monitor_quotes.py tests\test_monitor_domestic.py tests\test_backtest_jobs.py tests\test_chart_bundle.py tests\test_context_queries.py tests\test_smoke_pg_api_consistency.py -q
python scripts\run_watchlist_runtime_job.py --user-id demo-user --limit 5 --cache-dir runtime\watchlist_runtime_cache_smoke
```

结果：

- `tests/test_custom_instruments.py`：28 passed
- monitor 相关回归：32 passed
- 最终相关回归：41 passed
- job smoke：`WATCHLIST_RUNTIME_JOB_OK ... count=0 ...`

说明：本地 `demo-user` 当前无 `pending_runtime` watchlist 行，因此 job smoke 写出的 count 为 0；脚本、DB 查询、缓存写入链路通过。临时 smoke 缓存目录已删除。

## 限制

- 这是文件级缓存 MVP，不是调度系统。
- 尚未接 Windows 计划任务、cron 或队列。
- 尚未做跨用户批量 job。
- 尚未把缓存 metadata 入 PG。
- 尚未扩展 A股/期货/美股自选 runtime。

## 下一步

1. 增加 runtime job 调度方式：Windows 计划任务 / cron / API 后台任务三选一。
2. 增加缓存新鲜度校验与前端显示。
3. 扩展更多市场的数据解析与 runtime preview。
4. 与 W16-WS 对齐，把缓存更新事件推送给前端。
