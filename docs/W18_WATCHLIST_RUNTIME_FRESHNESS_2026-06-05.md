# W18 Watchlist Runtime Cache Freshness

日期：2026-06-05

## 范围

本段完成 runtime 文件缓存的新鲜度展示，并明确下一阶段调度方案。当前仍不安装系统计划任务，只把 API/Web/设计/文档链路先打通。

安全边界：

- 不写 `paper_state`。
- 不创建 fills / closes。
- 不触发挂单。
- 不真实下单。
- 不重启国内/海外服务器。
- 不修改峰极OS、阵营转换、DS01-DS09、风控或挂单规则。

## API 新鲜度

文件：`services/watchlist_runtime_file_cache.py`

新增：

- `runtime_cache_age_seconds(payload, now=None)`

用途：

- 读取 cache payload 的 `generated_at`。
- 返回缓存年龄秒数。
- 兼容 timezone-aware ISO 字符串。

文件：`services/api/main.py`

`GET /api/v1/paper-watchlist/runtime` 新增 query：

```text
runtime_cache_max_age_seconds=600
```

命中文件缓存时，`runtime_cache` 返回：

```json
{
  "status": "hit|hit_stale",
  "source": "file",
  "generated_at": "...",
  "age_seconds": 12.3,
  "max_age_seconds": 600,
  "stale": false
}
```

说明：

- `hit`：命中文件缓存且未超过新鲜度阈值。
- `hit_stale`：命中文件缓存但超过阈值。
- `stale=true`：前端可提示用户观察缓存过期。

## Web 展示

文件：`web/monitor.html`

新增：

- `runtimeCacheMeta`
- `fmtAge()`
- `runtimeCacheText()`

监测页 footer 会追加：

- `观察缓存 12秒`
- `观察缓存 3分钟`
- `观察缓存过期 2小时`

缓存不存在时不显示该段，后端继续回退实时构建。

## 设计同步

文件：

- `scripts/build_fjlhxm_ui_pen.py`
- `FJLHXM-UI.pen`

03 Monitor 样例新增 footer 文案：

```text
更新 2026-06-05 14:30 · 实盘同步 · 观察缓存 12秒
```

已重新生成并 finalize `FJLHXM-UI.pen`。

## 调度方案裁定

当前不直接安装调度任务，原因：

- W18 仍在 Web/本地产品化阶段，未最终确定部署拓扑。
- 本地、国内服务器、海外服务器的数据源和运行窗口不同。
- 直接安装计划任务可能污染当前已很复杂的模拟实盘运行态。

建议下一段采用：

1. 本地开发：手动运行 `scripts/run_watchlist_runtime_job.py`。
2. 服务器/生产：再根据实际部署选择 Windows 计划任务、cron 或 API 后台任务。
3. WebSocket 阶段：由 runtime job 更新缓存后推送事件给前端。

## 验证

已执行：

```powershell
python -m py_compile services\watchlist_runtime_file_cache.py services\api\main.py scripts\run_watchlist_runtime_job.py
python -m pytest tests\test_custom_instruments.py -q
python -m pytest tests\test_custom_instruments.py tests\test_monitor_quotes.py tests\test_monitor_domestic.py -q
python -m pytest tests\test_custom_instruments.py tests\test_monitor_quotes.py tests\test_monitor_domestic.py tests\test_backtest_jobs.py tests\test_chart_bundle.py tests\test_context_queries.py tests\test_smoke_pg_api_consistency.py -q
node --check web\js\app.js
node -e "const fs=require('fs'); const html=fs.readFileSync('web/monitor.html','utf8'); const blocks=[...html.matchAll(/<script>([\s\S]*?)<\/script>/g)].map(m=>m[1]); new Function(blocks.join('\n')); console.log('MONITOR_INLINE_SCRIPT_PARSE_OK=1');"
python scripts\build_fjlhxm_ui_pen.py
python scripts\finalize_fjlhxm_ui_pen.py
```

结果：

- `tests/test_custom_instruments.py`：29 passed
- monitor 相关回归：33 passed
- 最终相关回归：42 passed
- `MONITOR_INLINE_SCRIPT_PARSE_OK=1`
- `FJLHXM-UI.pen finalized`

## 下一步

1. W18 更多市场：A股、国内期货、更多 crypto 数据源。
2. W16-WS：将 runtime cache 更新变成 WebSocket/准实时推送。
3. 生产化调度：根据部署环境再安装 Windows 计划任务或 cron。
