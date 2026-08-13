# W18 Watchlist Runtime 只读信号预览

日期：2026-06-05

## 范围

本段完成用户自选品种 watchlist runtime 的第一版“只读信号预览”。它用于 Web 监测页展示观察候选是否存在近期策略痕迹，不是模拟实盘开仓、不进入挂单器、不写状态。

安全边界：

- 不写 `paper_state`。
- 不创建 fills / closes。
- 不触发挂单。
- 不重启国内/海外服务器。
- 不修改峰极OS、阵营转换、DS01-DS09、风控或挂单规则。

## 实现

### 后端 runtime preview

文件：`services/watchlist_runtime.py`

- 新增 `build_watchlist_signal_preview()`：
  - 读取 crypto D1 CSV。
  - 调用现有 `chart_bundle` 只读图表/回测输出。
  - 默认策略：`TOTAL`。
  - 默认窗口：`1` 年。
  - 提取：
    - `metrics.trades`
    - `metrics.win_rate`
    - `metrics.total_return`
    - `metrics.bad_audits`
    - 最近一个 entry marker 作为 `latest_signal`
- `build_watchlist_runtime_snapshot()` 新增参数 `include_signal_preview`，默认 `False`。
- 默认仍保持轻量 CSV snapshot；只有调用方显式开启时才计算 preview。

### API

文件：`services/api/main.py`

`GET /api/v1/paper-watchlist/runtime` 新增 query：

```text
include_signal_preview=true|false
```

返回字段：

- `runtime_binding=csv_snapshot_only`：默认轻量快照。
- `runtime_binding=csv_snapshot_with_signal_preview`：显式开启只读信号预览。

### Web

文件：

- `web/js/app.js`
- `web/monitor.html`
- `web/css/apple.css`

改动：

- `fetchPaperWatchlistRuntime()` 支持 `includeSignalPreview`。
- 监测页刷新服务端 watchlist runtime 时显式开启 preview。
- Runtime 行根据 `signal_preview.latest_signal` 显示：
  - `预览信号`
  - `观察中`
- 新增对应 CSS class。

### 设计同步

文件：

- `scripts/build_fjlhxm_ui_pen.py`
- `FJLHXM-UI.pen`

03 Monitor 样例同步为“预览信号 / 观察中”，并重新生成、finalize 设计文件。

## 验证

已执行：

```powershell
python -m py_compile services\watchlist_runtime.py services\api\main.py
python -m pytest tests\test_custom_instruments.py -q
node --check web\js\app.js
node -e "const fs=require('fs'); const html=fs.readFileSync('web/monitor.html','utf8'); const blocks=[...html.matchAll(/<script>([\s\S]*?)<\/script>/g)].map(m=>m[1]); new Function(blocks.join('\n')); console.log('MONITOR_INLINE_SCRIPT_PARSE_OK=1');"
python -m pytest tests\test_custom_instruments.py tests\test_monitor_quotes.py tests\test_monitor_domestic.py -q
python scripts\build_fjlhxm_ui_pen.py
python scripts\finalize_fjlhxm_ui_pen.py
python -m pytest tests\test_custom_instruments.py tests\test_backtest_jobs.py tests\test_chart_bundle.py tests\test_context_queries.py tests\test_smoke_pg_api_consistency.py -q
python -m pytest tests\test_custom_instruments.py tests\test_monitor_quotes.py tests\test_monitor_domestic.py tests\test_backtest_jobs.py tests\test_chart_bundle.py tests\test_context_queries.py tests\test_smoke_pg_api_consistency.py -q
```

结果：

- `tests/test_custom_instruments.py`：25 passed
- monitor 相关回归：29 passed
- W18/W11 相关回归：34 passed
- 最终相关回归：38 passed
- `MONITOR_INLINE_SCRIPT_PARSE_OK=1`
- `FJLHXM-UI.pen finalized`
- 真实 XRPUSDT smoke：`W18_SIGNAL_PREVIEW_SMOKE ready True TOTAL 1178 ...`

## 限制

- 当前 preview 仅针对 crypto D1 CSV，使用 `TOTAL` 只读 chart-bundle 输出。
- Preview 不是实时挂单信号，不代表可以开仓。
- Preview 仍不是正式监测 Job，也未接 WebSocket。
- 正式生产化仍需设计：缓存、异步计算、engine_version/data_version、不同市场数据源、权限限制、任务状态和错误重试。

## 下一步

1. 设计 W18 正式 runtime Job：把重型 preview 从页面请求中拆到后台 worker/cache。
2. 扩展 watchlist 市场范围：A股、国内期货、更多 crypto 数据源。
3. 与 W16-WS 对齐：监测页从轮询升级为 WebSocket/准实时推送。
