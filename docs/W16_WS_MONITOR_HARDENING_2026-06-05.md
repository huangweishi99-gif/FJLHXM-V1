# W16-WS Monitor WebSocket 生产化加固第一段

日期：2026-06-05

## 范围

本轮在 W16-WS 最小闭环基础上补服务端档位边界、连接限流和前端连接状态，不改变交易逻辑。

本轮不修改峰极OS最高宪法、阵营转换、DS01-DS09、风控参数、挂单器、模拟盘成交逻辑、国内/海外服务器运行态。

## 已完成

- `services/api/main.py` 新增 WS 演示鉴权边界：
  - `WS /api/v1/ws/monitor` 必须带 `user_id`。
  - 仅允许 `plan=pro`。
  - 缺用户或非专业档返回 `monitor.auth_error.v1`，并以 `1008` 关闭连接。
- 新增连接限流：
  - `MONITOR_WS_ACTIVE_CONNECTIONS` 记录当前活跃连接数。
  - `MONITOR_WS_MAX_CONNECTIONS_PER_USER` 默认 `3`，可通过环境变量覆盖。
  - 超限返回 `monitor.error.v1`，并以 `1013` 关闭连接。
- 新增推送间隔 clamp：
  - `pro` 最短 5 秒。
  - 非 pro 即使绕过客户端也无法获得高频推送。
- 修正断开处理：
  - `send_json()` 期间发生 `WebSocketDisconnect` 时直接退出。
  - `finally` 释放连接计数，避免 stale active count。
- `web/monitor.html` 细化前端状态：
  - 未登录不盲连 WS。
  - 权限关闭不重连，保留轮询 fallback。
  - 普通断线启用轮询备用，并 5 秒后重连。
  - footer 文案区分“WS已连接 · 专业档准实时”“WS权限不足”“WS断开，轮询备用”。

## 安全边界

- 不写 `paper_state`。
- 不触发挂单。
- 不创建模拟成交。
- 不真实下单。
- 不修改峰极OS最高宪法、阵营转换、DS01-DS09、风控参数。
- 不同步或重启国内/海外服务器。
- 不写入 API Key、Token、服务器密码或完整 webhook。

## 验证

- `python -m py_compile services\api\main.py services\watchlist_runtime.py services\monitor_domestic.py`：通过。
- `node --check web\js\app.js`：通过。
- `MONITOR_INLINE_SCRIPT_PARSE_OK=1`：通过。
- `python -m pytest tests\test_monitor_websocket.py -q`：6 passed。
- `python -m pytest tests\test_monitor_websocket.py tests\test_monitor_quotes.py tests\test_monitor_domestic.py tests\test_custom_instruments.py -q`：42 passed。
- `python -m pytest tests\test_custom_instruments.py tests\test_monitor_quotes.py tests\test_monitor_domestic.py tests\test_monitor_websocket.py tests\test_backtest_jobs.py tests\test_chart_bundle.py tests\test_context_queries.py tests\test_smoke_pg_api_consistency.py -q`：51 passed。

## 限制与下一步

- 当前仍是 Web 演示身份边界：`user_id/plan` 来自前端 demo 状态，不等于正式 Auth/JWT。
- 当前没有服务端连接指标持久化、审计日志或后台监控面板。
- 当前仍使用全量 `monitor.snapshot.v1`，未拆分频道或 delta 消息。
- 下一步应在正式 Auth/JWT 落地后替换 query/localStorage 演示身份，并补连接指标、频道拆分或 delta 消息、浏览器级 WS smoke。
