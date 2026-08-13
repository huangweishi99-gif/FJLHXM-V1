# W16-WS 浏览器级 WebSocket Smoke — 2026-06-08

## 范围

对齐 `FJLHXM-V1.md` **P1-W16-WS**：在真实 Chrome 中打开 `monitor.html`，验证 JWT 专业档用户能建立只读监测 WebSocket 并收到 `monitor.snapshot.v1`。

## 脚本

`scripts/smoke_w16_monitor_browser.py`

### 依赖（可选，不入 `requirements.txt`）

```powershell
pip install playwright
python -m playwright install chrome
```

### 用法

```powershell
docker compose up -d
alembic upgrade head
python scripts/smoke_w16_monitor_browser.py --auto-server
python scripts/smoke_w16_monitor_browser.py --base-url http://127.0.0.1:8000
python scripts/smoke_w16_monitor_browser.py --offline-skip-browser   # 仅 HTTP 开通 pro，不启浏览器
```

## 流程

1. 临时 uvicorn（或连接已有 API）
2. 注册用户 → `manual-confirm` 开通 **pro**（须 `FENGJI_ALLOW_MANUAL_SUBSCRIPTION_CONFIRM=1`）
3. Playwright + **Chrome channel** 注入 `localStorage` JWT
4. 打开 `/web/monitor.html`，等待 WS 首帧或 footer `#refreshMeta` 显示 WS 状态
5. **（默认）** 注入 hook 主动 `close()` 当前 WS → 等待「WS断开，轮询备用，5秒后重连」→ 等待再次「WS已连接」
6. 截图：`runtime/web_validation/w16_monitor_ws_reconnect_smoke.png`（或 `--skip-reconnect` 时用 `w16_monitor_ws_browser_smoke.png`）

### 参数

- `--skip-reconnect` — 仅验首连，不做断线重连
- `--offline-skip-browser` — 仅 HTTP 开通 pro

## 本地验证（2026-06-09 断线重连）

```json
{
  "ok": true,
  "ws_message_types": ["monitor.snapshot.v1"],
  "snapshot_before": 1,
  "snapshot_after": 2,
  "reconnect_disconnect_seen": true,
  "reconnect_ok": true,
  "refresh_meta": "WS更新 … · 实盘同步",
  "page_errors": []
}
```

## 仍待 W16-WS

- ~~频道拆分 / delta 推送~~（2026-06-09 已完成）
- ~~断线重连浏览器自动化~~（2026-06-09 默认 smoke 已覆盖）
- 可选：按频道独立 WS 连接

## 边界

- 只读监测；不写 `paper_state`、不触发挂单
- 未修改峰极OS / DS / 风控
