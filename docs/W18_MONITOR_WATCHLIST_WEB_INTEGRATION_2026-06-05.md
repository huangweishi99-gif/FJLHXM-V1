# W18 Web 监测页接入用户 Watchlist Runtime

日期：2026-06-05

## 范围

本次把用户自选品种 `paper_watchlist` 的只读 runtime 快照接入 Web 监测页。页面展示“观察候选”和“数据待补”，并继续与实际模拟持仓分离。本轮不修改峰极OS、阵营转换、DS01-DS09、现有挂单器、现有模拟盘进程或服务器脚本。

## 已完成

- `web/js/app.js`
  - 新增 `fetchPaperWatchlistRuntime()`，调用 `GET /api/v1/paper-watchlist/runtime`。
- `web/monitor.html`
  - 新增 `runtimeWatchItems`。
  - `refreshLive()` 同步拉取国内实际模拟持仓和用户 watchlist runtime。
  - 表格合并三类来源：
    - 本地自选
    - 国内实际模拟持仓
    - 用户自选品种 watchlist runtime
  - 状态区分：
    - `持仓`
    - `观察`
    - `观察候选`
    - `数据待补`
  - runtime 行优先使用 M15/H1/D1 快照返回的 `current_price/latest_time`。
- `web/css/apple.css`
  - 增加 `.monitor-status.status-pending`，用于“数据待补”。
- `scripts/build_fjlhxm_ui_pen.py`
  - 03 Monitor 设计稿样例同步为“持仓 / 观察候选 / 数据待补”三类。
- `FJLHXM-UI.pen`
  - 已重新生成并 finalize。

## 安全边界

- watchlist runtime 只作为“观察候选”显示。
- 不写现有 `paper_state`。
- 不触发挂单。
- 不创建模拟成交。
- 不把 watchlist 候选伪装成实际持仓。

## 验证

```powershell
node --check web\js\app.js
MONITOR_INLINE_SCRIPT_PARSE_OK=1
python -m pytest tests\test_custom_instruments.py tests\test_monitor_quotes.py tests\test_monitor_domestic.py -q
python -m pytest tests\test_custom_instruments.py tests\test_backtest_jobs.py tests\test_chart_bundle.py tests\test_context_queries.py tests\test_smoke_pg_api_consistency.py -q
python scripts\finalize_fjlhxm_ui_pen.py
```

结果：

- `node --check web\js\app.js` 通过。
- `MONITOR_INLINE_SCRIPT_PARSE_OK=1`。
- 监测相关测试：25 passed。
- W18/W11 相关回归：30 passed。
- `FJLHXM-UI.pen finalized` 通过。

HTTP smoke：

```text
W18_MONITOR_WATCHLIST_HTTP_SMOKE_OK count=1 status=ready symbol=XRPUSDT
```

## 当前限制

- 当前页面尚未提供暂停/取消观察按钮。
- watchlist runtime 仍是 CSV snapshot，不是峰极总定式实时信号。
- 如果用户未登录，页面不会请求服务端 watchlist runtime。
- 画布级 Pencil MCP 截图验收仍待 MCP 与 Pencil app 连通。

## 下一步

1. 增加暂停/取消观察接口。
2. Web 监测页为服务端 watchlist 行增加“取消观察”操作。
3. 后续接入只读峰极总定式信号引擎。
