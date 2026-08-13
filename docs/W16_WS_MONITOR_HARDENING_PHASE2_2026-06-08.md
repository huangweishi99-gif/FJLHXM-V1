# W16-WS Monitor WebSocket 生产化加固第二段

日期：2026-06-08

## 范围

在 W16-WS 第一段（演示鉴权、连接限流、前端 fallback）基础上，补服务端连接指标、审计日志、payload 未变 heartbeat，以及 REST 指标端点。

本轮不修改峰极OS最高宪法、阵营转换、DS01-DS09、风控参数、挂单器、模拟盘成交逻辑；不写 `paper_state`、不触发挂单、不真实下单。

## 已完成

- **新增 `services/monitor_ws_telemetry.py`**：
  - 进程内 lifetime 计数：connect / disconnect / auth_reject / limit_exceed / snapshot / heartbeat。
  - 审计 JSONL：`runtime/logs/monitor_ws_audit.jsonl`（可通过 `MONITOR_WS_AUDIT_LOG` 覆盖路径）。
  - 最近 50 条事件 ring buffer，供 stats API 返回。
- **WS 推送优化**：payload fingerprint 未变时发送 `monitor.heartbeat.v1`，避免重复全量 snapshot。
- **REST 指标**：`GET /api/v1/monitor/ws/stats` 返回活跃连接、lifetime 计数、最近事件、审计日志路径。
- **WS 生命周期审计**：connected / disconnected / auth_rejected / limit_exceeded / snapshot_sent / heartbeat_sent / push_error。
- **前端**：`web/monitor.html` 识别 heartbeat，仅更新 footer「WS心跳 · 数据未变」，不重绘表格。

## 安全边界

- 审计日志不写 API Key、Token、密码、完整 webhook。
- stats/WS 仍只读；演示身份仍来自 query/localStorage（`user_id` + `plan=pro`）。
- 未同步或重启国内/海外服务器。

## 验证

- `python -m py_compile services/monitor_ws_telemetry.py services/api/main.py`：通过。
- `python -m pytest tests/test_monitor_websocket.py tests/test_monitor_quotes.py tests/test_monitor_domestic.py -q`：**13 passed**。
- heartbeat 回归：`snapshot.v1` 首帧 + 同 payload 第二帧为 `heartbeat.v1`。

## 仍待后续（不算本轮完成）

- **正式 Auth/JWT** 落地后替换 query/localStorage 演示身份（依赖 W17-prod）。
- **频道拆分** 或更细粒度 delta（positions / quotes / runtime 分频道）。
- **浏览器级 Playwright WS smoke**（需 `@playwright/test` 或本机 Chrome channel）。
- Pencil 画布级验收：本轮仅 footer 文案微调，未改页面结构，`.pen` 文件级待确认。
