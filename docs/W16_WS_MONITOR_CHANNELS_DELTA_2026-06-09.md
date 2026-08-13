# W16-WS 频道拆分 / Delta 推送（2026-06-09）

## 范围

- 只读监测 WebSocket 仍不写 `paper_state`、不触发挂单、不真实下单。
- 在既有 `monitor.snapshot.v1` + `monitor.heartbeat.v1` 之上增加 **频道粒度 fingerprint** 与 **增量 delta**。

## 频道

| 频道 | 内容 |
|------|------|
| `positions` | 国内模拟持仓只读快照 |
| `runtime` | 用户 watchlist runtime + signal preview |
| `quotes` | 表格涉及品种的最新价摘要 |

订阅：`WS /api/v1/ws/monitor?...&channels=positions,runtime,quotes`（默认全选）。

## 消息类型

1. **首帧**：`monitor.snapshot.v1`（含 `channels` 字段，payload 仅含订阅频道）
2. **无变化**：`monitor.heartbeat.v1`（含 `channels`）
3. **部分变化**：`monitor.delta.v1`，字段 `changed: ["quotes"]`，`payload` 仅含变化频道

## 代码

- `services/monitor_ws_channels.py` — 频道解析、fingerprint、delta 构造
- `services/api/main.py` — WS 推送逻辑
- `web/monitor.html` — `applyMonitorDelta()` 合并增量
- `web/js/app.js` — WS URL 默认带 `channels`

## 验证

```powershell
python -m pytest tests\test_monitor_ws_channels.py tests\test_monitor_websocket.py -q
node --check web\js\app.js
```

## 待后续

- Playwright 验证 delta 合并后表格仍正确
- 可选：按频道拆成多条 WS 连接（当前为单连接多频道）
