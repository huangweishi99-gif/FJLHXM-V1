# W16-WS Monitor WebSocket 第一段最小闭环

日期：2026-06-05

## 范围

本轮只把 Web 监测页现有轮询能力升级为只读 WebSocket 最小闭环，并保留轮询 fallback。

本轮不修改峰极OS最高宪法、阵营转换、DS01-DS09、风控参数、挂单器、模拟盘成交逻辑、国内/海外服务器运行态。

## 已完成

- `services/api/main.py` 新增 `build_monitor_snapshot()`：
  - 读取国内模拟持仓：`load_latest_opens()`。
  - 读取用户 watchlist runtime/cache：复用 `paper_watchlist` runtime helper。
  - 读取本地 CSV 最新价：复用 `latest_quote_from_csv()`。
  - 输出统一 `monitor.snapshot.v1`。
- `services/api/main.py` 新增 `WS /api/v1/ws/monitor`：
  - 连接后立即发送首帧 snapshot。
  - 后续按档位/请求间隔推送 snapshot。
  - 异常返回 `monitor.error.v1`，客户端可回退轮询。
- `GET /api/v1/paper-watchlist/runtime` 收敛为复用同一 runtime helper，避免 REST 与 WS 两套 runtime 口径。
- `web/js/app.js` 新增 `monitorWebSocketUrl()`，根据 `API_BASE` 自动生成 `ws://` 或 `wss://` 地址。
- `web/monitor.html` 接入 WS：
  - 专业档启用 WS。
  - 免费/标准继续原轮询。
  - WS 断开、异常或消息解析失败时启用原 `refreshLive()` 轮询 fallback。
  - WS 恢复后停止 fallback 轮询。

## 消息 Schema

首版采用全量 snapshot，避免 delta 合并错误。

```json
{
  "type": "monitor.snapshot.v1",
  "version": 1,
  "seq": 1,
  "generated_at": "2026-06-05 19:30:00",
  "mode": "read_only_monitor",
  "user_id": "demo-user",
  "plan": "pro",
  "sources": {
    "domestic_positions": "paper_state",
    "watchlist_runtime": "file_cache_signal_preview",
    "quotes": "local_csv_latest_close"
  },
  "payload": {
    "positions": [],
    "runtime": {
      "mode": "read_only_observation",
      "runtime_cache": {},
      "items": []
    },
    "quotes": []
  },
  "status": {
    "ok": true,
    "fallback_polling_allowed": true
  }
}
```

异常帧：

```json
{
  "type": "monitor.error.v1",
  "version": 1,
  "mode": "read_only_monitor",
  "status": {
    "ok": false,
    "fallback_polling_allowed": true
  },
  "error": "..."
}
```

## 安全边界

- 不写 `paper_state`。
- 不触发挂单。
- 不创建模拟成交。
- 不真实下单。
- 不修改峰极OS最高宪法、阵营转换、DS01-DS09、风控参数。
- 不同步或重启国内/海外服务器。
- 不写入 API Key、Token、服务器密码或完整 webhook。

## 设计同步裁定

本轮复用现有 `monitor.html` footer 的 `refreshMeta` 状态位显示 WS 状态，没有新增页面结构、表格列、按钮或订阅入口，因此暂不修改 `FJLHXM-UI.pen` 和 `scripts/build_fjlhxm_ui_pen.py`。

如后续新增独立连接状态控件、频道选择、推送日志面板或订阅档位可视化，应同步设计生成脚本和 `.pen`。

## 验证

- `python -m py_compile services\api\main.py services\watchlist_runtime.py services\monitor_domestic.py`：通过。
- `node --check web\js\app.js`：通过。
- `MONITOR_INLINE_SCRIPT_PARSE_OK=1`：通过。
- `python -m pytest tests\test_monitor_websocket.py tests\test_monitor_quotes.py tests\test_monitor_domestic.py tests\test_custom_instruments.py -q`：38 passed。
- `python -m pytest tests\test_custom_instruments.py tests\test_monitor_quotes.py tests\test_monitor_domestic.py tests\test_monitor_websocket.py tests\test_backtest_jobs.py tests\test_chart_bundle.py tests\test_context_queries.py tests\test_smoke_pg_api_consistency.py -q`：47 passed。

## 限制与下一步

- 当前是只读 snapshot MVP，不是正式交易推送。
- 当前鉴权仍沿用 Web 演示态的 `localStorage` 用户/档位，不是正式 Auth/JWT。
- 当前未做服务端连接数限流、用户级限速和频道权限表。
- 下一步进入 W16-WS 生产化加固：补正式鉴权/演示鉴权边界、服务端连接限流、客户端连接状态细化、必要时拆分频道或 delta 消息。
